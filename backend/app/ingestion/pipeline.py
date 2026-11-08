"""Ingest one Greenhouse snapshot with safe structured run logs and metrics."""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from time import perf_counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.ingestion.greenhouse import fetch_jobs, validated_token
from app.ingestion.normalize import InvalidPosting, NormalizedPosting, normalize_job
from app.models import Employer, IngestionRun, Posting, PostingObservation, Source


LOGGER = logging.getLogger("dwi.ingestion")


@dataclass(frozen=True)
class RunSummary:
    run_id: int
    status: str
    fetched: int
    inserted: int
    updated: int
    unchanged: int
    rejected: int
    errors: int
    duration_ms: int
    rejection_reasons: dict[str, int]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _elapsed_ms(started: float) -> int:
    """Use a monotonic clock, not wall-clock timestamps, for elapsed time."""
    return max(0, round((perf_counter() - started) * 1000))


def _log_run(level: int, event: str, **fields: str | int | dict[str, int]) -> None:
    """Emit one machine-readable JSON record without raw source/error content."""
    LOGGER.log(level, json.dumps({"event": event, **fields}, sort_keys=True))


def _rejection_code(error: Exception) -> str:
    """Map known validation failures into bounded, non-sensitive categories."""
    if not isinstance(error, InvalidPosting):
        return "malformed_record"
    message = str(error).lower()
    if "posting id" in message:
        return "invalid_posting_id"
    if "title" in message:
        return "invalid_title"
    if "url" in message:
        return "invalid_url"
    if "location" in message:
        return "invalid_location"
    if "date" in message or "timezone" in message:
        return "invalid_timestamp"
    if "internal_job_id" in message or "requisition_id" in message:
        return "invalid_optional_id"
    return "malformed_record"


def _safe_error_message(error: Exception) -> str:
    """Do not persist network exception text, URLs, tokens, or posting bodies."""
    if isinstance(error, ValueError) and str(error).startswith("Conflicting records for posting ID"):
        return "ValueError: Conflicting records for posting ID"
    return f"{type(error).__name__}: ingestion failed"


def _get_source(session: Session, board_token: str, employer_name: str) -> Source:
    employer = session.scalar(select(Employer).where(Employer.name == employer_name))
    if employer is None:
        employer = Employer(name=employer_name)
        session.add(employer)
        session.flush()
    source = session.scalar(
        select(Source).where(Source.platform == "greenhouse", Source.board_token == board_token)
    )
    if source is None:
        source = Source(platform="greenhouse", board_token=board_token, employer_id=employer.id)
        session.add(source)
        session.flush()
    elif source.employer_id != employer.id:
        raise ValueError("Board token already belongs to a different employer.")
    return source


def _metadata_snapshot(value: NormalizedPosting) -> dict[str, str | int | None]:
    """Versioned public metadata only; no HTML, applicant data or inferred fields."""
    return {
        "snapshot_schema_version": 1,
        "external_posting_id": value.external_posting_id,
        "title_raw": value.title_raw,
        "source_url": value.source_url,
        "location_raw": value.location_raw,
        "source_internal_job_id": value.source_internal_job_id,
        "requisition_id": value.requisition_id,
        "first_published_at": (
            value.first_published_at.isoformat() if value.first_published_at else None
        ),
        "source_updated_at": (
            value.source_updated_at.isoformat() if value.source_updated_at else None
        ),
    }


def _update_posting(post: Posting, value: NormalizedPosting) -> None:
    post.title_raw = value.title_raw
    post.location_raw = value.location_raw
    post.source_url = value.source_url
    post.source_internal_job_id = value.source_internal_job_id
    post.requisition_id = value.requisition_id
    post.first_published_at = value.first_published_at
    post.source_updated_at = value.source_updated_at
    post.content_hash = value.content_hash


def ingest_board(
    factory: sessionmaker[Session],
    *,
    board_token: str,
    employer_name: str,
    fetcher: Callable[[str], list[dict[str, Any]]] = fetch_jobs,
) -> RunSummary:
    """Persist an atomic observation batch, keeping reliable run diagnostics.

    A failed fetch/storage step never changes existing postings or observations.
    Fetched count survives a failed processing transaction when the fetch succeeded.
    Concurrent ingestion runs on the same board remain unsupported.
    """
    token = validated_token(board_token)
    if not employer_name.strip():
        raise ValueError("Employer name is required.")
    started_clock = perf_counter()

    with factory() as session:
        source = _get_source(session, token, employer_name.strip())
        run = IngestionRun(
            source_id=source.id, started_at=utcnow(), status="running",
            fetched=0, inserted=0, updated=0, unchanged=0, rejected=0,
            errors=0, rejection_reasons={},
        )
        session.add(run)
        session.commit()
        run_id = run.id
        source_id = source.id

    _log_run(logging.INFO, "ingestion_started", run_id=run_id, source_id=source_id,
             board_token=token)
    phase = "fetch"
    try:
        jobs = fetcher(token)
        if not isinstance(jobs, list):
            raise ValueError("Fetcher must return an array of jobs.")

        # Store how many records arrived *outside* the atomic posting transaction.
        # A later rollback must not make it appear that zero jobs were retrieved.
        with factory() as session:
            run = session.get(IngestionRun, run_id)
            if run is None:
                raise RuntimeError("Ingestion run was not found.")
            run.fetched = len(jobs)
            session.commit()

        phase = "processing"
        rejected_reasons: Counter[str] = Counter()
        with factory() as session:
            run = session.get(IngestionRun, run_id)
            if run is None:
                raise RuntimeError("Ingestion run was not found.")
            now = utcnow()
            seen: dict[str, str] = {}
            for raw in jobs:
                try:
                    job = normalize_job(raw)
                except (InvalidPosting, TypeError, AttributeError) as invalid:
                    run.rejected += 1
                    rejected_reasons[_rejection_code(invalid)] += 1
                    continue
                previous_hash = seen.get(job.external_posting_id)
                if previous_hash is not None:
                    if previous_hash != job.content_hash:
                        # An ambiguous feed rolls back the entire observation batch.
                        raise ValueError(
                            f"Conflicting records for posting ID {job.external_posting_id}"
                        )
                    run.rejected += 1
                    rejected_reasons["duplicate_in_feed"] += 1
                    continue
                seen[job.external_posting_id] = job.content_hash
                existing = session.scalar(
                    select(Posting).where(
                        Posting.source_id == source_id,
                        Posting.external_posting_id == job.external_posting_id,
                    )
                )
                if existing is None:
                    existing = Posting(
                        source_id=source_id, external_posting_id=job.external_posting_id,
                        first_seen_at=now, last_seen_at=now, content_hash=job.content_hash,
                        title_raw=job.title_raw, location_raw=job.location_raw,
                        source_url=job.source_url,
                        source_internal_job_id=job.source_internal_job_id,
                        requisition_id=job.requisition_id,
                        first_published_at=job.first_published_at,
                        source_updated_at=job.source_updated_at,
                    )
                    session.add(existing)
                    session.flush()
                    run.inserted += 1
                    event = "inserted"
                else:
                    existing.last_seen_at = now
                    if existing.content_hash != job.content_hash:
                        _update_posting(existing, job)
                        run.updated += 1
                        event = "updated"
                    else:
                        run.unchanged += 1
                        event = "unchanged"
                session.add(PostingObservation(
                    posting_id=existing.id, ingestion_run_id=run_id,
                    observed_at=now, content_hash=job.content_hash, event=event,
                    snapshot=_metadata_snapshot(job) if event in ("inserted", "updated") else None,
                ))
            run.rejection_reasons = dict(rejected_reasons)
            run.status = "succeeded"
            run.finished_at = utcnow()
            run.duration_ms = _elapsed_ms(started_clock)
            summary = RunSummary(
                run_id=run_id, status=run.status, fetched=run.fetched,
                inserted=run.inserted, updated=run.updated,
                unchanged=run.unchanged, rejected=run.rejected, errors=run.errors,
                duration_ms=run.duration_ms,
                rejection_reasons=dict(rejected_reasons),
            )
            assert summary.fetched == (
                summary.inserted + summary.updated + summary.unchanged + summary.rejected
            )
            phase = "commit"
            session.commit()
        _log_run(
            logging.INFO, "ingestion_succeeded", run_id=run_id, source_id=source_id,
            board_token=token, fetched=summary.fetched, inserted=summary.inserted,
            updated=summary.updated, unchanged=summary.unchanged,
            rejected=summary.rejected, errors=summary.errors,
            rejection_reasons=summary.rejection_reasons,
            duration_ms=summary.duration_ms,
        )
        return summary
    except Exception as exc:
        # Keep a failure record and duration, but not rolled-back partial counts,
        # raw exception text, job IDs, URLs, applicant data, or tokens.
        duration_ms = _elapsed_ms(started_clock)
        try:
            with factory() as session:
                run = session.get(IngestionRun, run_id)
                if run is not None:
                    run.status = "failed"
                    run.errors = 1
                    run.error_message = _safe_error_message(exc)
                    run.duration_ms = duration_ms
                    run.finished_at = utcnow()
                    session.commit()
        except Exception as record_failure:
            _log_run(logging.ERROR, "ingestion_failure_record_error",
                     run_id=run_id, source_id=source_id,
                     error_type=type(record_failure).__name__)
        _log_run(
            logging.ERROR, "ingestion_failed", run_id=run_id, source_id=source_id,
            board_token=token, phase=phase, error_type=type(exc).__name__,
            errors=1, duration_ms=duration_ms,
        )
        raise
