"""Offline Greenhouse-to-database contract tests with synthetic public-job metadata.

These tests use HTTPX MockTransport and a disposable SQLite database; no
employer API, live data, or production data is accessed.
"""

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.ingestion.greenhouse import fetch_jobs
from app.ingestion.pipeline import ingest_board
from app.models import Base, IngestionRun, Posting, PostingObservation, Source


@pytest.fixture()
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'greenhouse_integration.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


def job(post_id=101, *, title="Synthetic Software Engineer", **changes):
    value = {
        "id": post_id,
        "title": title,
        "absolute_url": f"https://example.org/synthetic/jobs/{post_id}",
        "location": {"name": "Test City, GA"},
        "internal_job_id": 9001,
        "requisition_id": "SYN-101",
        "updated_at": "2026-11-01T10:00:00Z",
    }
    return {**value, **changes}


def feed(*jobs, total=None):
    return {"jobs": list(jobs), "meta": {"total": len(jobs) if total is None else total}}


def client_with_feeds(responses):
    """Return a strictly local mock client and an observable request log."""
    requests = []
    queue = list(responses)

    def handler(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.url.scheme == "https"
        assert request.url.host == "boards-api.greenhouse.io"
        assert request.url.path == "/v1/boards/syntheticboard/jobs"
        assert request.url.query == b""  # Never fetch descriptions/content=true.
        if not queue:
            raise AssertionError("Unexpected extra Greenhouse request")
        response = queue.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    return httpx.Client(transport=httpx.MockTransport(handler)), requests


def ingest(factory, client):
    return ingest_board(
        factory,
        board_token="syntheticboard",
        employer_name="Synthetic Test Employer",
        fetcher=lambda token: fetch_jobs(token, client=client, sleep=lambda _: None),
    )


def test_mocked_http_feed_runs_insert_repeat_update_and_missing_post_without_deletion(factory):
    initial = feed(job(101), job(102, title="Synthetic Technician"))
    updated = feed(job(101, title="Synthetic Senior Software Engineer"), job(102, title="Synthetic Technician"))
    missing = feed(job(101, title="Synthetic Senior Software Engineer"))
    responses = [httpx.Response(200, json=body) for body in (initial, initial, updated, missing)]

    client, requests = client_with_feeds(responses)
    with client:
        first = ingest(factory, client)
        with factory() as session:
            original = session.scalar(select(Posting).where(Posting.external_posting_id == "101"))
            original_first_seen = original.first_seen_at
            original_posting_id = original.id
        repeat = ingest(factory, client)
        change = ingest(factory, client)
        absent = ingest(factory, client)

    assert len(requests) == 4
    assert (first.inserted, first.updated, first.unchanged, first.rejected) == (2, 0, 0, 0)
    assert (repeat.inserted, repeat.updated, repeat.unchanged, repeat.rejected) == (0, 0, 2, 0)
    assert (change.inserted, change.updated, change.unchanged, change.rejected) == (0, 1, 1, 0)
    assert (absent.inserted, absent.updated, absent.unchanged, absent.rejected) == (0, 0, 1, 0)

    with factory() as session:
        source = session.scalar(select(Source))
        assert source.platform == "greenhouse"
        assert source.board_token == "syntheticboard"
        assert session.scalar(select(func.count()).select_from(Posting)) == 2
        posts = session.scalars(select(Posting).order_by(Posting.external_posting_id)).all()
        assert [post.external_posting_id for post in posts] == ["101", "102"]
        assert posts[0].id == original_posting_id
        assert posts[0].first_seen_at == original_first_seen
        assert posts[0].last_seen_at >= posts[0].first_seen_at
        assert posts[0].title_raw == "Synthetic Senior Software Engineer"
        # Missing from a complete later feed does not imply hiring/closure.
        assert posts[1].title_raw == "Synthetic Technician"
        assert session.scalar(select(func.count()).select_from(IngestionRun)) == 4

        events = session.scalars(
            select(PostingObservation)
            .where(PostingObservation.posting_id == posts[0].id)
            .order_by(PostingObservation.id)
        ).all()
        assert [event.event for event in events] == [
            "inserted", "unchanged", "updated", "unchanged"
        ]
        assert [event.snapshot is not None for event in events] == [
            True, False, True, False
        ]
        assert events[0].snapshot["title_raw"] == "Synthetic Software Engineer"
        assert events[2].snapshot["title_raw"] == "Synthetic Senior Software Engineer"
        assert len({event.ingestion_run_id for event in events}) == 4


def test_http_503_retries_then_records_failure_without_touching_previous_postings(factory):
    responses = [
        httpx.Response(200, json=feed(job())),
        httpx.Response(503),
        httpx.Response(503),
        httpx.Response(503),
    ]
    client, requests = client_with_feeds(responses)
    with client:
        first = ingest(factory, client)
        with pytest.raises(httpx.HTTPStatusError):
            ingest(factory, client)

    assert len(requests) == 4  # One successful read and exactly three failed attempts.
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Posting)) == 1
        assert session.scalar(select(func.count()).select_from(PostingObservation)) == 1
        runs = session.scalars(select(IngestionRun).order_by(IngestionRun.id)).all()
        assert [run.status for run in runs] == ["succeeded", "failed"]
        assert runs[0].id == first.run_id
        assert runs[1].errors == 1
        assert runs[1].fetched == 0
        assert runs[1].error_message == "HTTPStatusError: ingestion failed"
        assert runs[1].duration_ms >= 0


def test_incomplete_reported_count_aborts_without_overwriting_prior_snapshot(factory):
    responses = [
        httpx.Response(200, json=feed(job())),
        httpx.Response(200, json=feed(job(title="Updated title"), total=2)),
    ]
    client, requests = client_with_feeds(responses)
    with client:
        ingest(factory, client)
        with pytest.raises(ValueError, match="reported count"):
            ingest(factory, client)

    assert len(requests) == 2  # Structural failures must not silently retry.
    with factory() as session:
        post = session.scalar(select(Posting))
        assert post.title_raw == "Synthetic Software Engineer"
        assert session.scalar(select(func.count()).select_from(PostingObservation)) == 1
        runs = session.scalars(select(IngestionRun).order_by(IngestionRun.id)).all()
        assert [run.status for run in runs] == ["succeeded", "failed"]
        assert runs[1].fetched == 0
        assert runs[1].errors == 1


def test_invalid_and_duplicate_records_have_reconciled_metrics_and_safe_source_data(factory):
    records = [
        job(101),
        job(101),
        job(102, title=" "),
        job(103, absolute_url="http://invalid.example/synthetic/103"),
        job(104, location=["invalid"]),
        job(105),
    ]
    client, requests = client_with_feeds([httpx.Response(200, json=feed(*records))])
    with client:
        summary = ingest(factory, client)

    assert len(requests) == 1
    assert (summary.fetched, summary.inserted, summary.updated) == (6, 2, 0)
    assert (summary.unchanged, summary.rejected, summary.errors) == (0, 4, 0)
    assert summary.rejection_reasons == {
        "duplicate_in_feed": 1,
        "invalid_title": 1,
        "invalid_url": 1,
        "invalid_location": 1,
    }
    assert summary.fetched == sum((
        summary.inserted, summary.updated, summary.unchanged, summary.rejected,
    ))

    with factory() as session:
        run = session.get(IngestionRun, summary.run_id)
        assert run.status == "succeeded"
        assert run.rejection_reasons == summary.rejection_reasons
        assert run.duration_ms >= 0
        assert session.scalar(select(func.count()).select_from(Posting)) == 2
        assert session.scalar(select(func.count()).select_from(PostingObservation)) == 2
