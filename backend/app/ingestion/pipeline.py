"""Ingest one successful Greenhouse snapshot into an auditable relational model."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.ingestion.greenhouse import fetch_jobs, validated_token
from app.ingestion.normalize import InvalidPosting, NormalizedPosting, normalize_job
from app.models import Employer, IngestionRun, Posting, PostingObservation, Source


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


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
    """Create a run, fetch the entire feed, then persist one atomic observation batch.

    A failed fetch or storage transaction never marks existing postings inactive.
    Concurrent ingestion runs for the same board are not supported in this MVP.
    """
    token = validated_token(board_token)
    if not employer_name.strip():
        raise ValueError("Employer name is required.")
    with factory() as session:
        source = _get_source(session, token, employer_name.strip())
        run = IngestionRun(
            source_id=source.id, started_at=utcnow(), status="running",
            fetched=0, inserted=0, updated=0, unchanged=0, rejected=0, errors=0,
        )
        session.add(run)
        session.commit()
        run_id = run.id
        source_id = source.id

    try:
        jobs = fetcher(token)
        if not isinstance(jobs, list):
            raise ValueError("Fetcher must return an array of jobs.")
        with factory() as session:
            run = session.get(IngestionRun, run_id)
            if run is None:
                raise RuntimeError("Ingestion run was not found.")
            run.fetched = len(jobs)
            now = utcnow()
            seen: dict[str, str] = {}
            for raw in jobs:
                try:
                    job = normalize_job(raw)
                except (InvalidPosting, TypeError, AttributeError):
                    run.rejected += 1
                    continue
                previous_hash = seen.get(job.external_posting_id)
                if previous_hash is not None:
                    if previous_hash != job.content_hash:
                        # An internally inconsistent feed cannot safely establish
                        # a current version. Roll back the entire observation batch.
                        raise ValueError(
                            f"Conflicting records for posting ID {job.external_posting_id}"
                        )
                    run.rejected += 1
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
            run.status = "succeeded"
            run.finished_at = utcnow()
            summary = RunSummary(
                run_id=run_id, status="succeeded", fetched=run.fetched,
                inserted=run.inserted, updated=run.updated,
                unchanged=run.unchanged, rejected=run.rejected, errors=run.errors,
            )
            session.commit()
            return summary
    except Exception as exc:
        # An interrupted/invalid fetch is not evidence of vacancy closure.
        with factory() as session:
            run = session.get(IngestionRun, run_id)
            if run is not None:
                run.status = "failed"
                run.errors = 1
                run.error_message = f"{type(exc).__name__}: {exc}"[:1000]
                run.finished_at = utcnow()
                session.commit()
        raise
