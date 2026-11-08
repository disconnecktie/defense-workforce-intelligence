"""Offline contract tests for the first synthetic-only read API.

The in-memory app uses a disposable local SQLite DB populated via the real
ingestion pipeline with synthetic objects. It never contacts a real employer.
"""

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.postings import get_postings_session
from app.ingestion.pipeline import ingest_board
from app.main import app
from app.models import Base, IngestionRun, Posting, PostingObservation


def synthetic_job(posting_id, *, title=None, location="Synthetic Test City, GA"):
    return {
        "id": posting_id,
        "title": title or f"Synthetic Software Engineer {posting_id}",
        "absolute_url": f"https://example.org/synthetic/jobs/{posting_id}",
        "location": {"name": location},
        "updated_at": "2026-11-06T11:15:00-05:00",
    }


@pytest.fixture()
def api(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'postings_api.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def ingest(board, employer, records):
        return ingest_board(
            factory, board_token=board, employer_name=employer,
            fetcher=lambda _: records,
        )

    ingest("synthetic_alpha", "Synthetic CI Employer Alpha", [
        synthetic_job(101), synthetic_job(102), synthetic_job(103),
    ])
    ingest("synthetic_beta", "Synthetic CI Employer Beta", [
        synthetic_job(101, title="Synthetic Defense Analyst"),
    ])
    # Same schema and ingestion code, but these are NOT approved/synthetic
    # smoke-source identities and must never be returned by the API.
    ingest("other_board", "Example Employer", [
        synthetic_job(999, title="Not eligible for API exposure"),
    ])
    ingest("synthetic_spoof", "Example Employer", [
        synthetic_job(888, title="Token prefix alone is not sufficient"),
    ])
    ingest("real_board", "Synthetic CI Employer Rogue", [
        synthetic_job(777, title="Employer prefix alone is not sufficient"),
    ])

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


def test_api_is_disabled_by_default_and_does_not_open_database(monkeypatch):
    monkeypatch.delenv("DWI_POSTINGS_API_ENABLED", raising=False)
    monkeypatch.setenv("DWI_SOURCE_USE_APPROVED", "1")  # An unrelated flag.
    with TestClient(app) as client:
        response = client.get("/api/v1/postings")
    assert response.status_code == 503
    assert "disabled" in response.json()["detail"].lower()


def test_total_page_metadata_and_per_item_source_provenance(api):
    client, _ = api
    response = client.get("/api/v1/postings")
    assert response.status_code == 200
    data = response.json()
    assert data["data_scope"] == "synthetic_only"
    assert data["counting_rule"] == "distinct_source_postings"
    assert (data["total"], data["limit"], data["offset"]) == (4, 25, 0)
    assert data["next_offset"] is None
    assert len(data["items"]) == 4
    assert data["latest_observed_at"].endswith(("Z", "+00:00"))
    assert len(data["page_sources"]) == 2
    assert {source["board_token"] for source in data["page_sources"]} == {
        "synthetic_alpha", "synthetic_beta",
    }
    for item in data["items"]:
        assert item["employer"]["name"].startswith("Synthetic CI Employer ")
        assert item["source"]["platform"] == "greenhouse"
        assert item["source"]["board_token"].startswith("synthetic_")
        assert item["source"]["external_posting_id"].isdigit()
        assert item["source"]["url"].startswith("https://example.org/")
        assert item["first_seen_at"].endswith(("Z", "+00:00"))
        assert item["last_seen_at"].endswith(("Z", "+00:00"))
        assert item["source_updated_at"].endswith(("Z", "+00:00"))
        assert item["location_raw"] == "Synthetic Test City, GA"
        assert item["first_published_at"] is None
    # Same numeric posting ID from two different boards is two source postings.
    assert sum(item["source"]["external_posting_id"] == "101" for item in data["items"]) == 2


def test_stable_bounded_pagination_and_empty_out_of_range_page(api):
    client, _ = api
    page1 = client.get("/api/v1/postings", params={"limit": 2, "offset": 0}).json()
    page2 = client.get("/api/v1/postings", params={"limit": 2, "offset": 2}).json()
    empty = client.get("/api/v1/postings", params={"limit": 2, "offset": 100}).json()

    assert [page1["next_offset"], page2["next_offset"]] == [2, None]
    assert page1["total"] == page2["total"] == empty["total"] == 4
    ids1 = {item["id"] for item in page1["items"]}
    ids2 = {item["id"] for item in page2["items"]}
    assert len(ids1) == len(ids2) == 2
    assert ids1.isdisjoint(ids2)
    # The next page returns only its own source set, not the full filtered set.
    assert empty["items"] == []
    assert empty["page_sources"] == []
    assert empty["latest_observed_at"] is not None
    assert empty["next_offset"] is None
    assert page1["items"][0]["id"] > page1["items"][1]["id"]


def test_employer_filter_is_exact_case_insensitive_and_affects_total(api):
    client, _ = api
    result = client.get(
        "/api/v1/postings", params={"employer": "synthetic ci employer alpha"}
    )
    assert result.status_code == 200
    data = result.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert all(item["employer"]["name"] == "Synthetic CI Employer Alpha" for item in data["items"])
    assert [s["board_token"] for s in data["page_sources"]] == ["synthetic_alpha"]

    none = client.get(
        "/api/v1/postings", params={"employer": "Synthetic CI Employer"}
    ).json()
    assert none["total"] == 0
    assert none["latest_observed_at"] is None
    assert none["page_sources"] == []
    assert none["items"] == []


def test_unreviewed_sources_are_excluded_even_if_only_one_synthetic_marker_matches(api):
    client, _ = api
    data = client.get("/api/v1/postings").json()
    combined_text = str(data)
    for forbidden in ["other_board", "real_board", "synthetic_spoof",
                      "Not eligible", "not sufficient"]:
        assert forbidden not in combined_text


@pytest.mark.parametrize("query", [
    {"limit": 0}, {"limit": 101}, {"limit": -1},
    {"offset": -1}, {"offset": 100001}, {"limit": "foo"},
    {"employer": ""}, {"employer": " "},
    {"employer": "x" * 201},
])
def test_rejects_invalid_pagination_or_employer_queries(api, query):
    client, _ = api
    response = client.get("/api/v1/postings", params=query)
    assert response.status_code == 422


def test_get_is_read_only_and_leaks_no_ingestion_metadata(api):
    client, factory = api
    with factory() as session:
        before = (
            session.scalar(select(func.count()).select_from(Posting)),
            session.scalar(select(func.count()).select_from(IngestionRun)),
            session.scalar(select(func.count()).select_from(PostingObservation)),
        )
    result = client.get("/api/v1/postings", params={"limit": 100})
    assert result.status_code == 200
    body = result.json()
    forbidden = ["error_message", "rejection_reasons", "snapshot", "description_html",
                 "salary_min", "clearance_required", "source_internal_job_id"]
    for key in forbidden:
        assert key not in str(body)
    with factory() as session:
        after = (
            session.scalar(select(func.count()).select_from(Posting)),
            session.scalar(select(func.count()).select_from(IngestionRun)),
            session.scalar(select(func.count()).select_from(PostingObservation)),
        )
    assert before == after
    assert client.post("/api/v1/postings", json={}).status_code == 405


def test_openapi_declares_versioned_postings_route_and_model(api):
    client, _ = api
    spec = client.get("/openapi.json").json()
    route = spec["paths"]["/api/v1/postings"]
    assert "get" in route
    assert "post" not in route
    assert route["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("PostingsPageRead")
