"""Ensure local pilot never persists third-party extras from public API payloads."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.ingestion.normalize import normalize_job
from app.ingestion.pipeline import ingest_board
from app.ingestion.pilot_metadata import minimized_feed, pilot_metadata
from app.models import Base, Posting, PostingObservation


def example_job():
    return {
        "id": 1001,
        "title": "Synthetic Python Engineer",
        "absolute_url": "https://example.org/jobs/1001",
        "location": {"name": "Synthetic City", "address": "DO NOT STORE"},
        "updated_at": "2026-11-11T12:00:00Z",
        "internal_job_id": 2345,
        "requisition_id": "PRIVATE-REQ",
        "first_published": "2026-11-10T12:00:00Z",
        "content": "<p>DO NOT STORE</p>",
        "questions": [{"label": "DO NOT STORE"}],
        "departments": [{"name": "DO NOT STORE"}],
        "offices": [{"name": "DO NOT STORE"}],
    }


def test_pilot_field_allowlist_discards_nonessential_source_fields():
    minimal = pilot_metadata(example_job())
    assert set(minimal) == {"id", "title", "absolute_url", "location", "updated_at"}
    assert minimal["location"] == {"name": "Synthetic City"}
    assert "DO NOT STORE" not in repr(minimal)
    norm = normalize_job(minimal)
    assert norm.source_internal_job_id is None
    assert norm.requisition_id is None
    assert norm.first_published_at is None


def test_pilot_persistence_stores_only_minimal_metadata(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'minimized.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        summary = ingest_board(
            factory, board_token="syntheticminimal", employer_name="Synthetic Minimal",
            fetcher=lambda _: minimized_feed([example_job()]),
        )
        assert summary.inserted == 1
        with factory() as session:
            post = session.scalar(select(Posting))
            observation = session.scalar(select(PostingObservation))
            assert post.title_raw == "Synthetic Python Engineer"
            assert post.location_raw == "Synthetic City"
            assert post.source_internal_job_id is None
            assert post.requisition_id is None
            assert post.first_published_at is None
            assert observation.snapshot["source_internal_job_id"] is None
            assert observation.snapshot["requisition_id"] is None
            assert "DO NOT STORE" not in repr(observation.snapshot)
    finally:
        engine.dispose()
