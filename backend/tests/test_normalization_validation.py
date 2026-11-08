"""Focused edge-case validation for the DWI public posting metadata contract.

Only synthetic sample records are used; no employer data or network calls.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.ingestion.normalize import InvalidPosting, normalize_job, parse_date
from app.ingestion.pipeline import ingest_board
from app.models import Base, IngestionRun, Posting


def sample_job(**changes):
    value = {
        "id": 4802172007,
        "title": "  Data Engineer – Python  ",
        "absolute_url": "https://job-boards.greenhouse.io/sample/jobs/4802172007",
        "location": {"name": "  Augusta, GA / Remote  "},
        "updated_at": "2026-11-02T16:27:19-05:00",
        "internal_job_id": None,
        "requisition_id": " R-77 ",
    }
    return {**value, **changes}


def test_nullable_fields_remain_null_and_source_text_is_preserved():
    job = normalize_job(sample_job(
        location=None, updated_at=None, first_published=None,
        internal_job_id=None, requisition_id="  ",
    ))
    assert job.location_raw is None
    assert job.source_updated_at is None
    assert job.first_published_at is None
    assert job.source_internal_job_id is None
    assert job.requisition_id is None
    assert job.title_raw == "  Data Engineer – Python  "


def test_multiple_locations_preserved_not_guessed():
    result = normalize_job(sample_job())
    assert result.location_raw == "  Augusta, GA / Remote  "
    assert result.requisition_id == "R-77"
    assert result.source_updated_at == datetime(2026, 11, 2, 21, 27, 19, tzinfo=timezone.utc)


@pytest.mark.parametrize("identifier", [
    None, True, False, 0, -2, 1.0, "0", "00000", "", " ", "-42",
    "abc123", "１２３", "١٢٣", "1" * 101, [], {"id": 1},
])
def test_invalid_external_posting_ids_rejected(identifier):
    with pytest.raises(InvalidPosting, match="Posting ID"):
        normalize_job(sample_job(id=identifier))


@pytest.mark.parametrize("source_url", [
    None, "", "http://example.com/jobs/1", "file:///etc/passwd",
    "https://localhost/jobs/1", "https://localhost.localdomain/jobs/1",
    "https://private.internal/jobs/1", "https://example.local/jobs/1",
    "https://127.0.0.1/jobs/1", "https://[::1]/jobs/1",
    "https://user:pass@example.com/jobs/1", "https://example.com:badport/jobs/1",
    "https://example..com/jobs/1", "https://example.com\\evil/jobs/1",
    "https://example.com/jobs/1\nother", "https://example.com/" + "x" * 4096,
])
def test_invalid_urls_rejected(source_url):
    with pytest.raises(InvalidPosting, match="URL"):
        normalize_job(sample_job(absolute_url=source_url))


@pytest.mark.parametrize("change", [
    {"title": None}, {"title": ""}, {"title": "  "},
    {"title": True}, {"title": "X" * 4001},
    {"location": "Augusta"}, {"location": {"name": 9}},
    {"location": {"name": "X" * 4001}},
    {"internal_job_id": False}, {"internal_job_id": []},
    {"internal_job_id": "a" * 101}, {"requisition_id": {}},
    {"requisition_id": 3.5}, {"requisition_id": "a" * 101},
    {"updated_at": 123}, {"updated_at": "2026-11-02"},
    {"updated_at": "garbage"}, {"first_published": "2026-11-02T12:00:00"},
])
def test_malformed_source_fields_rejected(change):
    with pytest.raises(InvalidPosting):
        normalize_job(sample_job(**change))


def test_non_dict_source_record_rejected():
    with pytest.raises(InvalidPosting):
        normalize_job(["not", "a", "job"])


def test_equivalent_timezone_offsets_do_not_create_false_change():
    first = normalize_job(sample_job(updated_at="2026-11-02T16:27:19-05:00"))
    second = normalize_job(sample_job(updated_at="2026-11-02T21:27:19Z"))
    assert first.source_updated_at == second.source_updated_at
    assert first.content_hash == second.content_hash


def test_timestamp_without_offset_rejected_but_absent_allowed():
    assert parse_date(None) is None
    assert parse_date("") is None
    with pytest.raises(InvalidPosting, match="offset"):
        parse_date("2026-11-02T21:27:19")


def test_optional_ids_accept_numeric_and_null_values():
    job = normalize_job(sample_job(internal_job_id=567, requisition_id=0))
    assert job.source_internal_job_id == "567"
    assert job.requisition_id == "0"


def test_bounded_ids_align_with_database_column_limit():
    job = normalize_job(sample_job(id="9" * 100, requisition_id="R" * 100))
    assert len(job.external_posting_id) == 100
    assert len(job.requisition_id) == 100


def test_valid_records_survive_malformed_neighbors_without_duplicates(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'edge_cases.sqlite'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    valid = sample_job(id=123)
    invalid = sample_job(id="１２３")
    wrong_shape = ["wrong", "shape"]
    summary = ingest_board(
        factory, board_token="synthetic_board", employer_name="Synthetic Employer",
        fetcher=lambda _: [invalid, valid, wrong_shape],
    )
    assert summary.status == "succeeded"
    assert summary.fetched == 3
    assert summary.inserted == 1
    assert summary.rejected == 2
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Posting)) == 1
        run = session.scalar(select(IngestionRun))
        assert run.rejected == 2
    engine.dispose()
