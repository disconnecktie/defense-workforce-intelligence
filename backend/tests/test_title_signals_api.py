"""Read-only synthetic title keyword signal API integration tests."""

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.postings import get_postings_session
from app.ingestion.pipeline import ingest_board
from app.main import app
from app.models import Base, IngestionRun, Posting, PostingObservation


def synthetic_job(posting_id: int, title: str, *, description: str | None = None):
    return {
        "id": posting_id,
        "title": title,
        "absolute_url": f"https://example.org/synthetic/{posting_id}",
        "location": {"name": "Synthetic City, GA"},
        "updated_at": "2026-11-08T13:00:00Z",
        # Even if a description were supplied, it is NOT part of the
        # persisted metadata contract and MUST NOT be parsed as a title.
        "content": description,
    }


@pytest.fixture()
def api(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'title_signals.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def ingest(board, employer, jobs):
        return ingest_board(
            factory, board_token=board, employer_name=employer,
            fetcher=lambda _: jobs,
        )

    alpha = [
        synthetic_job(101, "Senior Python / AWS Engineer"),
        synthetic_job(102, "React.js and Kubernetes Developer"),
        synthetic_job(103, "Systems Engineer", description="<p>Python AWS Docker</p>"),
    ]
    beta = [
        synthetic_job(101, "AWS Cloud Architect"),
        synthetic_job(104, "K8s / Docker Platform Engineer"),
    ]
    ingest("synthetic_alpha", "Synthetic CI Employer Alpha", alpha)
    ingest("synthetic_alpha", "Synthetic CI Employer Alpha", alpha)  # repeat is not new posting
    ingest("synthetic_beta", "Synthetic CI Employer Beta", beta)
    ingest("real_employer", "Real Employer", [
        synthetic_job(999, "Python AWS Kubernetes Docker Engineer")
    ])
    ingest("synthetic_spoof", "Real Employer", [
        synthetic_job(998, "Python AWS Kubernetes Docker Engineer")
    ])
    ingest("real_board", "Synthetic CI Employer Rogue", [
        synthetic_job(997, "Python AWS Kubernetes Docker Engineer")
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


def test_disabled_by_default_even_if_source_use_flag_set(monkeypatch):
    monkeypatch.delenv("DWI_POSTINGS_API_ENABLED", raising=False)
    monkeypatch.setenv("DWI_SOURCE_USE_APPROVED", "1")
    with TestClient(app) as client:
        response = client.get("/api/v1/title-signals")
    assert response.status_code == 503


def test_synthetic_title_mention_counts_and_explainable_examples(api):
    client, _ = api
    response = client.get("/api/v1/title-signals")
    assert response.status_code == 200
    result = response.json()
    assert result["data_scope"] == "synthetic_only"
    assert result["source_field"] == "title_raw"
    assert result["counting_rule"] == "distinct_source_postings"
    assert result["interpretation"] == "explicit_title_mentions_not_verified_skill_requirements"
    assert result["method_version"] == "title_keywords_v1"
    assert result["postings_scanned"] == 5
    assert result["postings_with_any_term"] == 4
    assert result["postings_without_any_term"] == 1
    assert result["title_mention_rate_pct"] == 80.0
    assert result["latest_observed_at"].endswith(("Z", "+00:00"))
    counts = {entry["term"]: entry["postings_with_title_mention"] for entry in result["terms"]}
    assert counts == {
        "Python": 1,
        "Kubernetes": 2,
        "AWS": 2,
        "Azure": 0,
        "Docker": 1,
        "PostgreSQL": 0,
        "React": 1,
    }
    for entry in result["terms"]:
        assert len(entry["examples"]) <= 3
        for example in entry["examples"]:
            assert example["platform"] == "greenhouse"
            assert example["board_token"].startswith("synthetic_")
            assert example["title"][example["match_start"]:example["match_end"]] == example["evidence"]


def test_source_posting_identity_is_per_board_and_repeat_does_not_add_counts(api):
    client, factory = api
    body = client.get("/api/v1/title-signals").json()
    assert body["postings_scanned"] == 5
    # Both boards have external ID 101. Both are distinct source-posting rows.
    aws = next(item for item in body["terms"] if item["term"] == "AWS")
    assert aws["postings_with_title_mention"] == 2
    assert {example["external_posting_id"] for example in aws["examples"]} == {"101"}
    assert {example["board_token"] for example in aws["examples"]} == {
        "synthetic_alpha", "synthetic_beta",
    }
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Posting)) == 8


def test_exact_case_insensitive_employer_filter_and_zero_denominator(api):
    client, _ = api
    beta = client.get("/api/v1/title-signals", params={
        "employer": "synthetic ci employer beta",
    }).json()
    assert beta["postings_scanned"] == 2
    assert beta["postings_with_any_term"] == 2
    assert beta["title_mention_rate_pct"] == 100.0
    assert next(item for item in beta["terms"] if item["term"] == "AWS")["postings_with_title_mention"] == 1

    missing = client.get("/api/v1/title-signals", params={
        "employer": "Synthetic CI Employer",
    }).json()
    assert missing["postings_scanned"] == 0
    assert missing["postings_with_any_term"] == 0
    assert missing["postings_without_any_term"] == 0
    assert missing["title_mention_rate_pct"] is None
    assert missing["latest_observed_at"] is None
    assert all(item["postings_with_title_mention"] == 0 and not item["examples"]
               for item in missing["terms"])


@pytest.mark.parametrize("query", [
    {"employer": ""}, {"employer": " "}, {"employer": "x" * 201},
])
def test_invalid_employer_filters_are_rejected(api, query):
    client, _ = api
    assert client.get("/api/v1/title-signals", params=query).status_code == 422


def test_source_filter_excludes_real_employers_and_is_read_only(api):
    client, factory = api
    with factory() as session:
        before = (
            session.scalar(select(func.count()).select_from(Posting)),
            session.scalar(select(func.count()).select_from(PostingObservation)),
            session.scalar(select(func.count()).select_from(IngestionRun)),
        )
    result = client.get("/api/v1/title-signals")
    assert result.status_code == 200
    text = str(result.json())
    for invalid in ("real_board", "real_employer", "synthetic_spoof", "Real Employer", "Rogue"):
        assert invalid not in text
    with factory() as session:
        after = (
            session.scalar(select(func.count()).select_from(Posting)),
            session.scalar(select(func.count()).select_from(PostingObservation)),
            session.scalar(select(func.count()).select_from(IngestionRun)),
        )
    assert before == after
    assert client.post("/api/v1/title-signals", json={}).status_code == 405


def test_openapi_declares_read_only_title_signals(api):
    client, _ = api
    path = client.get("/openapi.json").json()["paths"]["/api/v1/title-signals"]
    assert "get" in path
    assert "post" not in path
    assert path["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("TitleSignalsReport")
