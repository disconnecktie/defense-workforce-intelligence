"""Synthetic-only source coverage API contract and data-quality metrics.

All tests use a disposable SQLite DB, synthetic records, and the existing
ingestion pipeline; there are no external HTTP calls or live employer data.
"""

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.postings import get_postings_session
from app.ingestion.pipeline import ingest_board
from app.main import app
from app.models import Base, IngestionRun, Posting, PostingObservation


def job(posting_id, *, location=None, updated_at=None, first_published=None):
    return {
        "id": posting_id,
        "title": f"Synthetic Engineer {posting_id}",
        "absolute_url": f"https://example.org/synthetic/jobs/{posting_id}",
        "location": {"name": location} if location else None,
        "updated_at": updated_at,
        "first_published": first_published,
    }


@pytest.fixture()
def coverage_api(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'coverage.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def ingest(board, employer, data):
        return ingest_board(
            factory,
            board_token=board,
            employer_name=employer,
            fetcher=lambda _: data,
        )

    alpha_rows = [
        job(101, location="Synthetic City, GA", updated_at="2026-11-08T08:00:00-05:00"),
        job(102, first_published="2026-11-07T10:00:00Z"),
    ]
    ingest("synthetic_alpha", "Synthetic CI Employer Alpha", alpha_rows)
    ingest("synthetic_alpha", "Synthetic CI Employer Alpha", alpha_rows)
    ingest("synthetic_beta", "Synthetic CI Employer Beta", [
        job(101, updated_at="2026-11-08T08:00:00-05:00"),
    ])
    # Deliberately include an eligible empty source to test null percentages.
    ingest("synthetic_gamma", "Synthetic CI Employer Gamma", [])

    # These three sources each match only some predicates, not all.
    ingest("real_employer", "Real Employer", [job(999, location="Real City")])
    ingest("synthetic_spoof", "Real Employer", [job(998, location="Real City")])
    ingest("real_board", "Synthetic CI Employer Rogue", [job(997)])

    def override_session():
        with factory() as session:
            yield session

    monkeypatch.setenv("DWI_POSTINGS_API_ENABLED", "1")
    app.dependency_overrides[get_postings_session] = override_session
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.pop(get_postings_session, None)
        engine.dispose()


def test_coverage_requires_opt_in_and_does_not_depend_on_ingestion_approval(monkeypatch):
    monkeypatch.delenv("DWI_POSTINGS_API_ENABLED", raising=False)
    monkeypatch.setenv("DWI_SOURCE_USE_APPROVED", "1")
    with TestClient(app) as client:
        result = client.get("/api/v1/coverage")
    assert result.status_code == 503
    assert "disabled" in result.json()["detail"].lower()


def test_global_and_source_completeness_are_correct_and_distinct(coverage_api):
    client, _ = coverage_api
    result = client.get("/api/v1/coverage")
    assert result.status_code == 200
    body = result.json()
    assert body["data_scope"] == "synthetic_only"
    assert body["counting_rule"] == "distinct_source_postings"
    assert (body["total_sources"], body["total_employers"]) == (3, 3)
    assert (body["limit"], body["offset"], body["next_offset"]) == (25, 0, None)
    assert body["latest_observed_at"].endswith(("Z", "+00:00"))
    assert body["totals"] == {
        "posting_count": 3,
        "location_present": 1,
        "first_published_at_present": 1,
        "source_updated_at_present": 2,
        "location_coverage_pct": 33.3,
        "published_date_coverage_pct": 33.3,
        "source_update_coverage_pct": 66.7,
    }
    assert len(body["sources"]) == 3
    alpha, beta, gamma = body["sources"]
    assert [s["employer"] for s in body["sources"]] == [
        "Synthetic CI Employer Alpha",
        "Synthetic CI Employer Beta",
        "Synthetic CI Employer Gamma",
    ]
    assert (alpha["platform"], alpha["board_token"]) == ("greenhouse", "synthetic_alpha")
    assert alpha["metrics"]["posting_count"] == 2
    assert alpha["metrics"]["location_coverage_pct"] == 50.0
    assert alpha["metrics"]["published_date_coverage_pct"] == 50.0
    assert alpha["metrics"]["source_update_coverage_pct"] == 50.0
    assert alpha["latest_observed_at"] is not None
    assert beta["metrics"]["posting_count"] == 1
    assert beta["metrics"]["location_coverage_pct"] == 0.0
    assert beta["metrics"]["source_update_coverage_pct"] == 100.0
    assert gamma["metrics"]["posting_count"] == 0
    assert gamma["metrics"]["location_present"] == 0
    assert gamma["metrics"]["location_coverage_pct"] is None
    assert gamma["metrics"]["published_date_coverage_pct"] is None
    assert gamma["metrics"]["source_update_coverage_pct"] is None
    assert gamma["latest_observed_at"] is None


def test_sources_are_paginated_but_global_metrics_are_not(coverage_api):
    client, _ = coverage_api
    first = client.get("/api/v1/coverage", params={"limit": 2, "offset": 0}).json()
    second = client.get("/api/v1/coverage", params={"limit": 2, "offset": 2}).json()
    past_end = client.get("/api/v1/coverage", params={"limit": 2, "offset": 99}).json()
    assert first["next_offset"] == 2
    assert [s["board_token"] for s in first["sources"]] == ["synthetic_alpha", "synthetic_beta"]
    assert second["next_offset"] is None
    assert [s["board_token"] for s in second["sources"]] == ["synthetic_gamma"]
    assert past_end["sources"] == []
    assert past_end["next_offset"] is None
    for page in (first, second, past_end):
        assert page["totals"]["posting_count"] == 3
        assert page["total_sources"] == 3
        assert page["total_employers"] == 3
        assert page["latest_observed_at"] is not None


def test_exact_case_insensitive_employer_filter(coverage_api):
    client, _ = coverage_api
    result = client.get(
        "/api/v1/coverage", params={"employer": "synthetic ci employer beta"}
    ).json()
    assert result["total_sources"] == 1
    assert result["total_employers"] == 1
    assert result["totals"]["posting_count"] == 1
    assert result["totals"]["location_coverage_pct"] == 0.0
    assert result["sources"][0]["board_token"] == "synthetic_beta"

    missing = client.get(
        "/api/v1/coverage", params={"employer": "Synthetic CI Employer"}
    ).json()
    assert missing["total_sources"] == 0
    assert missing["total_employers"] == 0
    assert missing["totals"]["posting_count"] == 0
    assert missing["totals"]["location_coverage_pct"] is None
    assert missing["latest_observed_at"] is None
    assert missing["sources"] == []


@pytest.mark.parametrize("query", [
    {"limit": 0}, {"limit": 101}, {"limit": "n/a"},
    {"offset": -1}, {"offset": 100001},
    {"employer": ""}, {"employer": " "}, {"employer": "x" * 201},
])
def test_rejects_invalid_queries(coverage_api, query):
    client, _ = coverage_api
    assert client.get("/api/v1/coverage", params=query).status_code == 422


def test_excludes_real_sources_and_does_not_modify_db(coverage_api):
    client, factory = coverage_api
    with factory() as session:
        before = (
            session.scalar(select(func.count()).select_from(Posting)),
            session.scalar(select(func.count()).select_from(PostingObservation)),
            session.scalar(select(func.count()).select_from(IngestionRun)),
        )
    result = client.get("/api/v1/coverage")
    assert result.status_code == 200
    text = str(result.json())
    for forbidden in ("real_board", "real_employer", "synthetic_spoof", "Real Employer", "Rogue"):
        assert forbidden not in text
    with factory() as session:
        after = (
            session.scalar(select(func.count()).select_from(Posting)),
            session.scalar(select(func.count()).select_from(PostingObservation)),
            session.scalar(select(func.count()).select_from(IngestionRun)),
        )
    assert before == after
    assert client.post("/api/v1/coverage", json={}).status_code == 405


def test_openapi_describes_coverage_as_get_only(coverage_api):
    client, _ = coverage_api
    methods = client.get("/openapi.json").json()["paths"]["/api/v1/coverage"]
    assert "get" in methods and "post" not in methods
    assert methods["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("CoverageReport")
