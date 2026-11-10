"""Contract tests: synthetic-only ingestion run history, not vacancy trends."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.postings import get_postings_session
from app.ingestion.pipeline import ingest_board
from app.main import app
from app.models import Base, IngestionRun


def job(job_id):
    return {
        "id": job_id, "title": f"Synthetic Engineer {job_id}",
        "absolute_url": f"https://example.org/synthetic/{job_id}",
        "location": {"name": "Synthetic Test City"},
        "updated_at": "2026-11-08T13:00:00Z",
    }


@pytest.fixture()
def api(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'history.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def ingest(board, employer, jobs):
        ingest_board(factory, board_token=board, employer_name=employer,
                     fetcher=lambda _: jobs)

    ingest("synthetic_alpha", "Synthetic CI Employer Alpha", [job(101), job(102)])
    ingest("synthetic_alpha", "Synthetic CI Employer Alpha", [job(101), job(102)])
    ingest("synthetic_beta", "Synthetic CI Employer Beta", [job(103)])
    ingest("synthetic_spoof", "Real Employer", [job(104)])
    ingest("real_board", "Synthetic CI Employer Rogue", [job(105)])

    def session_override():
        with factory() as session:
            yield session

    monkeypatch.setenv("DWI_POSTINGS_API_ENABLED", "1")
    app.dependency_overrides[get_postings_session] = session_override
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.pop(get_postings_session, None)
        engine.dispose()


def test_default_off_even_with_unrelated_source_flag(monkeypatch):
    monkeypatch.delenv("DWI_POSTINGS_API_ENABLED", raising=False)
    monkeypatch.setenv("DWI_SOURCE_USE_APPROVED", "1")
    with TestClient(app) as client:
        assert client.get("/api/v1/ingestion-history").status_code == 503


def test_history_counts_runs_not_postings_and_excludes_real_sources(api):
    client, _ = api
    response = client.get("/api/v1/ingestion-history")
    assert response.status_code == 200
    body = response.json()
    assert body["data_scope"] == "synthetic_only"
    assert body["counting_rule"] == "ingestion_runs_not_vacancies"
    assert body["total"] == 3
    assert body["next_offset"] is None
    assert len(body["items"]) == 3
    assert {item["board_token"] for item in body["items"]} == {
        "synthetic_alpha", "synthetic_beta",
    }
    assert all(item["platform"] == "greenhouse" for item in body["items"])
    assert sorted(item["inserted"] for item in body["items"]) == [0, 1, 2]
    assert sorted(item["unchanged"] for item in body["items"]) == [0, 0, 2]
    assert all(item["started_at"].endswith(("Z", "+00:00")) for item in body["items"])
    assert all("error_message" not in item and "rejection_reasons" not in item
               for item in body["items"])


def test_pagination_global_total_and_exact_employer_filter(api):
    client, _ = api
    first = client.get("/api/v1/ingestion-history", params={"limit": 2}).json()
    second = client.get("/api/v1/ingestion-history",
                        params={"limit": 2, "offset": 2}).json()
    assert first["total"] == second["total"] == 3
    assert first["next_offset"] == 2
    assert second["next_offset"] is None
    assert len(first["items"]) == 2 and len(second["items"]) == 1
    assert len({item["run_id"] for item in first["items"] + second["items"]}) == 3

    alpha = client.get("/api/v1/ingestion-history",
                       params={"employer": "synthetic ci employer alpha"}).json()
    assert alpha["total"] == 2
    assert all(item["employer"] == "Synthetic CI Employer Alpha"
               for item in alpha["items"])
    missing = client.get("/api/v1/ingestion-history",
                         params={"employer": "Synthetic CI Employer"}).json()
    assert missing["total"] == 0
    assert missing["items"] == []


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": 101}, {"offset": -1},
    {"employer": ""}, {"employer": " "},
])
def test_invalid_queries_are_rejected(api, params):
    client, _ = api
    assert client.get("/api/v1/ingestion-history", params=params).status_code == 422


def test_history_is_read_only(api):
    client, factory = api
    with factory() as session:
        before = [r.id for r in session.scalars(select(IngestionRun)).all()]
    assert client.get("/api/v1/ingestion-history").status_code == 200
    with factory() as session:
        after = [r.id for r in session.scalars(select(IngestionRun)).all()]
    assert after == before
