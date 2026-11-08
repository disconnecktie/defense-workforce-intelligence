"""Synthetic PostgreSQL integration smoke test; never fetches live employer data.

Requires DWI_TEST_DATABASE_URL pointing at a migrated, disposable test DB.
Uses a fresh synthetic source for each invocation, so rerunning is safe.
"""

import os
from uuid import uuid4

from sqlalchemy import func, select

from app.db import make_session_factory
from app.ingestion.pipeline import ingest_board
from app.models import IngestionRun, Posting, PostingObservation, Source


url = os.environ.get("DWI_TEST_DATABASE_URL")
if not url:
    raise SystemExit("Refusing to execute without an explicit DWI_TEST_DATABASE_URL")

factory = make_session_factory(url)
# Make repeated developer smoke tests independent without deleting earlier test data.
board_token = "synthetic_" + uuid4().hex[:16]
employer_name = "Synthetic CI Employer " + board_token

record = {
    "id": 8080001,
    "title": "Synthetic Systems Engineer",
    "absolute_url": "https://example.org/jobs/8080001",
    "location": {"name": "Synthetic Test City"},
    "updated_at": "2026-11-08T08:00:00-05:00",
}
updated_record = {
    **record,
    "title": "Synthetic Senior Systems Engineer",
    "location": {"name": "Synthetic Remote Region"},
}
first = ingest_board(
    factory, board_token=board_token, employer_name=employer_name,
    fetcher=lambda _: [record],
)
second = ingest_board(
    factory, board_token=board_token, employer_name=employer_name,
    fetcher=lambda _: [record],
)
third = ingest_board(
    factory, board_token=board_token, employer_name=employer_name,
    fetcher=lambda _: [updated_record],
)
assert (first.inserted, first.unchanged, first.updated) == (1, 0, 0), first
assert (second.inserted, second.unchanged, second.updated) == (0, 1, 0), second
assert (third.inserted, third.unchanged, third.updated) == (0, 0, 1), third
fourth = ingest_board(
    factory, board_token=board_token, employer_name=employer_name,
    fetcher=lambda _: [
        updated_record, updated_record, {**record, "id": None},
    ],
)
assert (fourth.fetched, fourth.unchanged, fourth.rejected, fourth.errors) == (3, 1, 2, 0), fourth
assert fourth.rejection_reasons == {
    "duplicate_in_feed": 1, "invalid_posting_id": 1,
}
assert fourth.duration_ms >= 0

with factory() as session:
    source = session.scalar(select(Source).where(Source.board_token == board_token))
    assert source is not None
    post = session.scalar(select(Posting).where(Posting.source_id == source.id))
    assert post is not None
    assert session.scalar(
        select(func.count()).select_from(Posting).where(Posting.source_id == source.id)
    ) == 1
    history = session.scalars(
        select(PostingObservation).where(PostingObservation.posting_id == post.id)
        .order_by(PostingObservation.id)
    ).all()
    assert [event.event for event in history] == ["inserted", "unchanged", "updated", "unchanged"]
    assert history[0].snapshot["title_raw"] == "Synthetic Systems Engineer"
    assert history[1].snapshot is None
    assert history[2].snapshot["title_raw"] == "Synthetic Senior Systems Engineer"
    assert history[0].content_hash != history[2].content_hash
    assert post.title_raw == "Synthetic Senior Systems Engineer"
    assert post.first_seen_at <= post.last_seen_at
    run = session.get(IngestionRun, fourth.run_id)
    assert run.fetched == 3
    assert (run.inserted, run.updated, run.unchanged, run.rejected, run.errors) == (0, 0, 1, 2, 0)
    assert run.rejection_reasons == fourth.rejection_reasons
    assert run.duration_ms == fourth.duration_ms
    assert run.started_at is not None and run.finished_at is not None

print("Synthetic PostgreSQL ingestion: insert/repeat/update/history/metrics PASS")
