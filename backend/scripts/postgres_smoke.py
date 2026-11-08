"""Synthetic PostgreSQL integration smoke test; no external HTTP access.

Run only against an isolated test database with migrations already applied.
"""

import os

from sqlalchemy import func, select

from app.db import make_session_factory
from app.ingestion.pipeline import ingest_board
from app.models import Posting, PostingObservation

url = os.environ.get("DWI_TEST_DATABASE_URL")
if not url:
    raise SystemExit("Refusing to execute without an explicit DWI_TEST_DATABASE_URL")

factory = make_session_factory(url)
record = {
    "id": 8080001,
    "title": "Synthetic Systems Engineer",
    "absolute_url": "https://example.org/jobs/8080001",
    "location": {"name": "Synthetic Test City"},
    "updated_at": "2026-11-08T08:00:00-05:00",
}
first = ingest_board(
    factory, board_token="synthetic_ci_only", employer_name="Synthetic CI Employer",
    fetcher=lambda _: [record],
)
second = ingest_board(
    factory, board_token="synthetic_ci_only", employer_name="Synthetic CI Employer",
    fetcher=lambda _: [record],
)
assert (first.inserted, first.unchanged, first.updated) == (1, 0, 0), first
assert (second.inserted, second.unchanged, second.updated) == (0, 1, 0), second
with factory() as session:
    assert session.scalar(select(func.count()).select_from(Posting)) == 1
    assert session.scalar(select(func.count()).select_from(PostingObservation)) == 2
print("Synthetic PostgreSQL ingestion: insert/repeat/observations PASS")
