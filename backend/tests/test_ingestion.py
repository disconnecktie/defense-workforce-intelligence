"""Offline TKT-003 unit tests. Never contact a live employer or mutate production data."""

from datetime import datetime
import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.ingestion.greenhouse import fetch_jobs, validated_token
from app.ingestion.normalize import InvalidPosting, normalize_job
from app.ingestion.pipeline import ingest_board
from app.models import Base, Employer, IngestionRun, Posting, PostingObservation, Source


def sample_job(
    post_id: int = 4802172007,
    title: str = "2026 Early Career Electrical Engineer",
) -> dict:
    return {
        "id": post_id, "internal_job_id": 2345, "requisition_id": "REQ-1",
        "title": title, "absolute_url": f"https://job-boards.greenhouse.io/test/jobs/{post_id}",
        "location": {"name": "Costa Mesa, CA"},
        "updated_at": "2026-11-02T16:27:19-05:00",
    }


@pytest.fixture()
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ingestion.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


def test_normalization_retains_provenance_and_timezone():
    job = normalize_job(sample_job())
    assert job.external_posting_id == "4802172007"
    assert job.location_raw == "Costa Mesa, CA"
    assert job.source_updated_at == datetime.fromisoformat("2026-11-02T16:27:19-05:00")
    assert len(job.content_hash) == 64


@pytest.mark.parametrize("change", [
    {"id": None},
    {"title": "  "},
    {"absolute_url": "file:///etc/passwd"},
    {"updated_at": "not a date"},
    {"location": []},
])
def test_bad_source_records_rejected(change):
    with pytest.raises(InvalidPosting):
        normalize_job({**sample_job(), **change})


def test_client_uses_only_documented_public_get():
    requested = []
    def handler(request):
        requested.append(request)
        return httpx.Response(200, json={"jobs": [sample_job()], "meta": {"total": 1}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        jobs = fetch_jobs("test_board", client=client)
    assert len(jobs) == 1
    assert requested[0].method == "GET"
    assert requested[0].url.path == "/v1/boards/test_board/jobs"
    assert requested[0].url.query == b""


def test_client_transient_error_retries():
    calls = []
    def handler(_):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"jobs": [], "meta": {"total": 0}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert fetch_jobs("test_board", client=client, sleep=lambda _: None) == []
    assert len(calls) == 2


def test_client_refuses_incomplete_feed():
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(
            200, json={"jobs": [sample_job()], "meta": {"total": 2}}
        ))
    ) as client:
        with pytest.raises(ValueError, match="reported count"):
            fetch_jobs("test_board", client=client)


def test_board_token_cannot_be_url_or_localhost():
    with pytest.raises(ValueError):
        validated_token("http://localhost:8000")


def test_insert_repeat_update_and_source_scoped_identity(factory):
    first = sample_job()
    summary = ingest_board(factory, board_token="test_board", employer_name="Test Employer", fetcher=lambda _: [first])
    assert (summary.inserted, summary.updated, summary.unchanged, summary.fetched) == (1, 0, 0, 1)
    second = ingest_board(factory, board_token="test_board", employer_name="Test Employer", fetcher=lambda _: [first])
    assert (second.inserted, second.updated, second.unchanged) == (0, 0, 1)
    altered = sample_job(title="Electrical Engineer II")
    third = ingest_board(factory, board_token="test_board", employer_name="Test Employer", fetcher=lambda _: [altered])
    assert (third.inserted, third.updated, third.unchanged) == (0, 1, 0)

    # Identical numeric IDs on separate boards must not collapse.
    fourth = ingest_board(factory, board_token="other_board", employer_name="Another Employer", fetcher=lambda _: [first])
    assert fourth.inserted == 1

    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Posting)) == 2
        assert db.scalar(select(func.count()).select_from(PostingObservation)) == 4
        assert db.scalar(select(func.count()).select_from(IngestionRun)) == 4
        stored = db.scalar(select(Posting).where(Posting.source_id == 1))
        assert stored.title_raw == "Electrical Engineer II"
        assert stored.first_seen_at <= stored.last_seen_at
        assert [row.event for row in db.scalars(
            select(PostingObservation).where(PostingObservation.posting_id == stored.id).order_by(PostingObservation.id)
        )] == ["inserted", "unchanged", "updated"]


def test_bad_record_only_rejected_no_duplicates(factory):
    first = sample_job()
    bad = {**first, "id": None}
    result = ingest_board(factory, board_token="test_board", employer_name="Test Employer", fetcher=lambda _: [first, first, bad])
    assert (result.fetched, result.inserted, result.rejected) == (3, 1, 2)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Posting)) == 1


def test_failed_fetch_preserves_data_and_reports_failed_run(factory):
    job = sample_job()
    ingest_board(factory, board_token="test_board", employer_name="Test Employer", fetcher=lambda _: [job])
    def failing(_):
        raise httpx.ConnectError("network unavailable")
    with pytest.raises(httpx.ConnectError):
        ingest_board(factory, board_token="test_board", employer_name="Test Employer", fetcher=failing)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Posting)) == 1
        assert db.scalar(select(func.count()).select_from(PostingObservation)) == 1
        runs = db.scalars(select(IngestionRun).order_by(IngestionRun.id)).all()
        assert [run.status for run in runs] == ["succeeded", "failed"]
        assert runs[-1].errors == 1
        assert "ConnectError" in runs[-1].error_message


def test_no_inactivation_on_missing_post_in_successful_snapshot(factory):
    ingest_board(factory, board_token="test_board", employer_name="Test Employer", fetcher=lambda _: [sample_job()])
    result = ingest_board(factory, board_token="test_board", employer_name="Test Employer", fetcher=lambda _: [])
    assert result.status == "succeeded"
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Posting)) == 1
