"""Synthetic tests for safe TKT-003 ingestion logs and persisted run metrics."""

import json
import logging

import httpx
import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from app.ingestion.pipeline import ingest_board
from app.models import Base, IngestionRun, Posting, PostingObservation


@pytest.fixture()
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ingestion_metrics.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


def job(post_id=101, **changes):
    value = {
        "id": post_id,
        "title": "Synthetic engineer",
        "absolute_url": f"https://example.org/jobs/{post_id}",
        "location": {"name": "Augusta, GA"},
        "updated_at": "2026-11-01T10:00:00Z",
    }
    return {**value, **changes}


def ingest(factory, *jobs):
    return ingest_board(
        factory, board_token="syntheticmetrics",
        employer_name="Synthetic Metrics Employer", fetcher=lambda _: list(jobs),
    )


def log_lines(caplog):
    return [
        json.loads(record.message)
        for record in caplog.records if record.name == "dwi.ingestion"
    ]


def test_metrics_reconcile_and_rejected_reasons_have_no_raw_record_data(factory, caplog):
    secret_title = "Sensitive-looking source title 1234"
    invalid_title = job(201, title=" ")
    invalid_url = job(202, absolute_url="file:///private/internal")
    with caplog.at_level(logging.INFO, logger="dwi.ingestion"):
        summary = ingest(
            factory, job(101), job(101), invalid_title, invalid_url,
            job(103, title=secret_title),
        )

    assert summary.status == "succeeded"
    assert (summary.fetched, summary.inserted, summary.updated) == (5, 2, 0)
    assert (summary.unchanged, summary.rejected, summary.errors) == (0, 3, 0)
    assert summary.rejection_reasons == {
        "duplicate_in_feed": 1, "invalid_title": 1, "invalid_url": 1,
    }
    assert summary.duration_ms >= 0
    assert summary.fetched == (
        summary.inserted + summary.updated + summary.unchanged + summary.rejected
    )
    with factory() as session:
        run = session.get(IngestionRun, summary.run_id)
        assert run.status == "succeeded"
        assert run.started_at is not None and run.finished_at is not None
        assert run.fetched == summary.fetched
        assert run.duration_ms == summary.duration_ms
        assert run.rejection_reasons == summary.rejection_reasons
        assert session.scalar(select(func.count()).select_from(Posting)) == 2
        assert session.scalar(select(func.count()).select_from(PostingObservation)) == 2

    logs = log_lines(caplog)
    assert [line["event"] for line in logs] == ["ingestion_started", "ingestion_succeeded"]
    assert logs[0]["run_id"] == summary.run_id
    assert logs[1]["fetched"] == 5
    assert logs[1]["rejection_reasons"] == summary.rejection_reasons
    serialized = json.dumps(logs)
    assert secret_title not in serialized
    assert "file:///private/internal" not in serialized
    assert "https://example.org/jobs" not in serialized


def test_change_metrics_distinguish_insert_update_unchanged(factory):
    ingest(factory, job(101))
    repeat = ingest(factory, job(101))
    change = ingest(factory, job(101, title="New synthetic title"), job(102))
    assert (repeat.inserted, repeat.updated, repeat.unchanged) == (0, 0, 1)
    assert (change.inserted, change.updated, change.unchanged) == (1, 1, 0)
    for summary in (repeat, change):
        assert summary.rejection_reasons == {}
        with factory() as session:
            run = session.get(IngestionRun, summary.run_id)
            assert run.rejection_reasons == {}
            assert run.duration_ms is not None


def test_failed_fetch_keeps_safe_failure_record_without_leaking_exception_text(factory, caplog):
    marker = "NEVER_LOG_SECRET_EXAMPLE_123"
    def bad_fetch(_):
        raise httpx.ConnectError(f"Gateway failed; token={marker}")

    with caplog.at_level(logging.INFO, logger="dwi.ingestion"):
        with pytest.raises(httpx.ConnectError, match="Gateway failed"):
            ingest_board(
                factory, board_token="syntheticmetrics",
                employer_name="Synthetic Metrics Employer", fetcher=bad_fetch,
            )

    with factory() as session:
        run = session.scalar(select(IngestionRun))
        assert run.status == "failed"
        assert run.errors == 1
        assert run.fetched == 0
        assert run.inserted == run.updated == run.unchanged == run.rejected == 0
        assert run.duration_ms is not None
        assert run.error_message == "ConnectError: ingestion failed"
    logs = log_lines(caplog)
    assert [line["event"] for line in logs] == ["ingestion_started", "ingestion_failed"]
    assert logs[-1]["phase"] == "fetch"
    assert logs[-1]["error_type"] == "ConnectError"
    assert marker not in json.dumps(logs)


def test_partial_batch_rolls_back_but_fetched_count_survives(factory, caplog):
    initial = ingest(factory, job(101))
    with caplog.at_level(logging.INFO, logger="dwi.ingestion"):
        with pytest.raises(ValueError, match="Conflicting records for posting ID"):
            ingest(factory, job(202), job(101, title="new"), job(101, title="conflict"))

    with factory() as session:
        runs = session.scalars(select(IngestionRun).order_by(IngestionRun.id)).all()
        assert len(runs) == 2
        failed = runs[-1]
        assert failed.fetched == 3
        assert failed.inserted == failed.updated == failed.unchanged == failed.rejected == 0
        assert failed.errors == 1
        assert failed.status == "failed"
        assert failed.rejection_reasons == {}
        assert failed.duration_ms >= 0
        assert failed.error_message == "ValueError: Conflicting records for posting ID"
        assert session.scalar(select(func.count()).select_from(Posting)) == 1
        assert session.scalar(select(func.count()).select_from(PostingObservation)) == 1
        assert session.get(IngestionRun, initial.run_id).status == "succeeded"
    logs = log_lines(caplog)
    assert logs[-1]["event"] == "ingestion_failed"
    assert logs[-1]["phase"] == "processing"
    assert "202" not in json.dumps(logs)
    assert "conflict" not in json.dumps(logs)


def test_storage_failure_is_reported_without_job_content(factory, caplog):
    marker = "NEVER_STORE_THIS_INTERNAL_BACKEND_DETAIL"
    def break_insert(_mapper, _connection, _target):
        raise RuntimeError(marker)

    event.listen(Posting, "before_insert", break_insert)
    try:
        with caplog.at_level(logging.INFO, logger="dwi.ingestion"):
            with pytest.raises(RuntimeError, match=marker):
                ingest(factory, job(301))
    finally:
        event.remove(Posting, "before_insert", break_insert)

    with factory() as session:
        run = session.scalar(select(IngestionRun))
        assert run.status == "failed"
        assert run.fetched == 1
        assert run.inserted == 0
        assert run.errors == 1
        assert run.duration_ms >= 0
        assert run.error_message == "RuntimeError: ingestion failed"
        assert session.scalar(select(func.count()).select_from(Posting)) == 0
        assert session.scalar(select(func.count()).select_from(PostingObservation)) == 0
    logs = log_lines(caplog)
    assert logs[-1]["event"] == "ingestion_failed"
    assert logs[-1]["phase"] == "processing"
    assert marker not in json.dumps(logs)


def test_empty_feed_has_successful_zero_metrics(factory):
    result = ingest(factory)
    assert result.status == "succeeded"
    assert result.fetched == result.rejected == result.errors == 0
    assert result.duration_ms >= 0
    assert result.rejection_reasons == {}
    with factory() as session:
        run = session.get(IngestionRun, result.run_id)
        assert run.status == "succeeded"
        assert run.rejection_reasons == {}
        assert run.finished_at is not None


def test_invalid_non_list_fetch_is_run_failure(factory):
    with pytest.raises(ValueError, match="Fetcher must return"):
        ingest_board(
            factory, board_token="syntheticmetrics",
            employer_name="Synthetic Metrics Employer", fetcher=lambda _: {"jobs": []},
        )
    with factory() as session:
        run = session.scalar(select(IngestionRun))
        assert run.status == "failed"
        assert run.errors == 1
        assert run.fetched == 0
        assert run.error_message == "ValueError: ingestion failed"
