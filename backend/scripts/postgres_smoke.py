"""Synthetic PostgreSQL integration smoke test; never fetches live employer data.

Requires DWI_TEST_DATABASE_URL pointing at a migrated, disposable test DB.
Uses a fresh synthetic source for each invocation, so rerunning is safe.
"""

import os
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.postings import get_postings_session
from app.main import app

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

# Add two more explicitly synthetic titles to exercise *positive* keyword
# matches in PostgreSQL. These are invented fixtures, not real source data.
signal_board = "synthetic_" + uuid4().hex[:16]
signal_employer = "Synthetic CI Employer " + signal_board
signal_fixture = [
    {
        "id": 9090001,
        "title": "Synthetic Python / AWS Platform Engineer",
        "absolute_url": "https://example.org/synthetic/title-signals/9090001",
        "location": {"name": "Synthetic Test City"},
        "updated_at": "2026-11-08T08:00:00-05:00",
    },
    {
        "id": 9090002,
        "title": "Synthetic K8s and React.js Developer",
        "absolute_url": "https://example.org/synthetic/title-signals/9090002",
        "location": None,
        "updated_at": "2026-11-08T08:00:00-05:00",
    },
]
signal_ingestion = ingest_board(
    factory, board_token=signal_board, employer_name=signal_employer,
    fetcher=lambda _: signal_fixture,
)
assert signal_ingestion.inserted == 2 and signal_ingestion.errors == 0, signal_ingestion

# Validate the new FastAPI contract against the actual PostgreSQL schema,
# without querying real employers or changing stored ingestion data.
def test_session():
    with factory() as session:
        yield session


original_enabled = os.environ.get("DWI_POSTINGS_API_ENABLED")
app.dependency_overrides[get_postings_session] = test_session
os.environ["DWI_POSTINGS_API_ENABLED"] = "1"
try:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/postings",
            params={"employer": employer_name, "limit": 2},
        )
        coverage_response = client.get(
            "/api/v1/coverage",
            params={"employer": employer_name, "limit": 2},
        )
        title_signal_response = client.get(
            "/api/v1/title-signals",
            params={"employer": signal_employer},
        )
    assert title_signal_response.status_code == 200, title_signal_response.text
    signals = title_signal_response.json()
    assert signals["data_scope"] == "synthetic_only", signals
    assert signals["source_field"] == "title_raw", signals
    assert signals["method_version"] == "title_keywords_v1", signals
    assert signals["postings_scanned"] == 2, signals
    assert signals["postings_with_any_term"] == 2, signals
    assert signals["title_mention_rate_pct"] == 100.0, signals
    counts = {term["term"]: term["postings_with_title_mention"] for term in signals["terms"]}
    assert counts == {
        "Python": 1, "Kubernetes": 1, "AWS": 1, "Azure": 0,
        "Docker": 0, "PostgreSQL": 0, "React": 1,
    }, counts
    assert all(
        evidence["title"][evidence["match_start"]:evidence["match_end"]]
        == evidence["evidence"]
        for term in signals["terms"] for evidence in term["examples"]
    ), signals
    assert coverage_response.status_code == 200, coverage_response.text
    coverage = coverage_response.json()
    assert coverage["data_scope"] == "synthetic_only", coverage
    assert coverage["total_sources"] == 1 and coverage["total_employers"] == 1, coverage
    assert coverage["totals"]["posting_count"] == 1, coverage
    assert coverage["totals"]["location_present"] == 1, coverage
    assert coverage["totals"]["location_coverage_pct"] == 100.0, coverage
    assert coverage["totals"]["first_published_at_present"] == 0, coverage
    assert coverage["totals"]["published_date_coverage_pct"] == 0.0, coverage
    assert coverage["totals"]["source_updated_at_present"] == 1, coverage
    assert coverage["sources"][0]["board_token"] == board_token, coverage
    assert coverage["sources"][0]["metrics"]["posting_count"] == 1, coverage
    assert coverage["sources"][0]["latest_observed_at"] == coverage["latest_observed_at"], coverage
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["data_scope"] == "synthetic_only", page
    assert page["counting_rule"] == "distinct_source_postings", page
    assert page["total"] == 1 and len(page["items"]) == 1, page
    assert page["page_sources"] == [{
        "platform": "greenhouse",
        "board_token": board_token,
        "employer": employer_name,
    }], page
    item = page["items"][0]
    assert item["title"] == "Synthetic Senior Systems Engineer", item
    assert item["source"]["board_token"] == board_token, item
    assert item["source"]["external_posting_id"] == "8080001", item
    assert item["first_seen_at"] <= item["last_seen_at"], item
    assert page["latest_observed_at"] == item["last_seen_at"], page
finally:
    app.dependency_overrides.pop(get_postings_session, None)
    if original_enabled is None:
        os.environ.pop("DWI_POSTINGS_API_ENABLED", None)
    else:
        os.environ["DWI_POSTINGS_API_ENABLED"] = original_enabled

print("Synthetic PostgreSQL ingestion: insert/repeat/update/history/metrics PASS")
print("Synthetic PostgreSQL API: filtered source-attributed GET /api/v1/postings PASS")
print("Synthetic PostgreSQL API: source coverage completeness GET /api/v1/coverage PASS")
print("Synthetic PostgreSQL API: explicit title keyword GET /api/v1/title-signals PASS")

