"""Synthetic, offline tests for TKT-003 deduplication and version history."""

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.ingestion.pipeline import ingest_board
from app.models import Base, IngestionRun, Posting, PostingObservation, Source


@pytest.fixture()
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'history.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


def job(post_id=101, **changes):
    record = {
        "id": post_id,
        "title": "Systems Engineer I",
        "absolute_url": f"https://example.org/careers/{post_id}",
        "location": {"name": "Augusta, GA"},
        "internal_job_id": 9001,
        "requisition_id": "REQ-22",
        "updated_at": "2026-11-01T10:00:00-05:00",
    }
    return {**record, **changes}


def ingest(factory, *records, board="example"):
    return ingest_board(
        factory, board_token=board, employer_name=f"Synthetic {board}",
        fetcher=lambda _: list(records),
    )


def test_insert_unchanged_update_and_metadata_version_snapshots(factory):
    first = ingest(factory, job())
    with factory() as db:
        before = db.scalar(select(Posting))
        first_seen = before.first_seen_at
        first_hash = before.content_hash
        source_id = before.source_id
        first_posting_id = before.id

    # Equivalent timestamp representation is not an update.
    unchanged = ingest(factory, job(updated_at="2026-11-01T15:00:00Z"))
    changed = ingest(factory, job(
        title="Systems Engineer II",
        location={"name": "Remote / Augusta, GA"},
        updated_at="2026-11-03T12:00:00Z",
    ))
    after_repeat = ingest(factory, job(
        title="Systems Engineer II",
        location={"name": "Remote / Augusta, GA"},
        updated_at="2026-11-03T12:00:00Z",
    ))

    assert (first.inserted, first.updated, first.unchanged) == (1, 0, 0)
    assert (unchanged.inserted, unchanged.updated, unchanged.unchanged) == (0, 0, 1)
    assert (changed.inserted, changed.updated, changed.unchanged) == (0, 1, 0)
    assert (after_repeat.inserted, after_repeat.updated, after_repeat.unchanged) == (0, 0, 1)
    with factory() as db:
        posts = db.scalars(select(Posting)).all()
        assert len(posts) == 1
        current = posts[0]
        assert (current.id, current.source_id) == (first_posting_id, source_id)
        assert current.first_seen_at == first_seen
        assert current.last_seen_at >= current.first_seen_at
        assert current.title_raw == "Systems Engineer II"
        assert current.location_raw == "Remote / Augusta, GA"
        assert current.content_hash != first_hash

        observations = db.scalars(
            select(PostingObservation).order_by(PostingObservation.id)
        ).all()
        assert [item.event for item in observations] == [
            "inserted", "unchanged", "updated", "unchanged"
        ]
        assert all(item.posting_id == current.id for item in observations)
        assert len({item.ingestion_run_id for item in observations}) == 4
        assert [item.snapshot is not None for item in observations] == [
            True, False, True, False
        ]
        assert observations[0].snapshot["snapshot_schema_version"] == 1
        assert observations[0].snapshot["title_raw"] == "Systems Engineer I"
        assert observations[0].snapshot["location_raw"] == "Augusta, GA"
        assert observations[2].snapshot["title_raw"] == "Systems Engineer II"
        assert observations[2].snapshot["location_raw"] == "Remote / Augusta, GA"
        assert "description_html" not in observations[0].snapshot
        assert observations[0].content_hash == observations[1].content_hash
        assert observations[2].content_hash == observations[3].content_hash
        assert observations[0].content_hash != observations[2].content_hash


def test_same_id_on_other_boards_is_not_merged(factory):
    a = ingest(factory, job(), board="alpha")
    b = ingest(factory, job(title="Different job"), board="beta")
    assert a.inserted == b.inserted == 1
    with factory() as db:
        posts = db.scalars(select(Posting).order_by(Posting.id)).all()
        assert len(posts) == 2
        assert posts[0].external_posting_id == posts[1].external_posting_id == "101"
        assert posts[0].source_id != posts[1].source_id
        assert db.scalar(select(func.count()).select_from(Source)) == 2


def test_identical_duplicate_within_feed_counts_once(factory):
    summary = ingest(factory, job(), job(), job(102))
    assert (summary.fetched, summary.inserted, summary.rejected) == (3, 2, 1)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Posting)) == 2
        assert db.scalar(select(func.count()).select_from(PostingObservation)) == 2


def test_conflicting_same_id_rolls_back_entire_feed(factory):
    base = ingest(factory, job())
    with pytest.raises(ValueError, match="Conflicting records for posting ID"):
        # A new valid row appears before the ambiguous record. None may commit.
        ingest(factory, job(202), job(title="Changed"), job(title="Another"))
    with factory() as db:
        posts = db.scalars(select(Posting)).all()
        assert len(posts) == 1
        assert posts[0].title_raw == "Systems Engineer I"
        assert db.scalar(select(func.count()).select_from(PostingObservation)) == 1
        runs = db.scalars(select(IngestionRun).order_by(IngestionRun.id)).all()
        assert [run.status for run in runs] == ["succeeded", "failed"]
        assert runs[-1].errors == 1
        assert runs[-1].inserted == 0  # rolled-back transaction
        assert "Conflicting records" in runs[-1].error_message
        assert base.run_id == runs[0].id


def test_missing_post_is_not_silently_marked_closed(factory):
    ingest(factory, job(101), job(102))
    with factory() as db:
        missing = db.scalar(select(Posting).where(Posting.external_posting_id == "102"))
        previous_seen = missing.last_seen_at
    result = ingest(factory, job(101))
    assert result.fetched == 1
    with factory() as db:
        missing = db.scalar(select(Posting).where(Posting.external_posting_id == "102"))
        assert missing is not None
        assert missing.last_seen_at == previous_seen
        assert db.scalar(
            select(func.count()).select_from(PostingObservation).where(
                PostingObservation.posting_id == missing.id
            )
        ) == 1
