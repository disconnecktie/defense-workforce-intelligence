"""Synthetic PostgreSQL integration check for source-scoped purge.

Requires DWI_TEST_DATABASE_URL pointing at an already migrated disposable DB.
Never calls Greenhouse or selects real employer sources. Adds unique synthetic
fixtures and only deletes the synthetic sources it created.
"""

import os
from uuid import uuid4

from sqlalchemy import func, select

from app.db import make_session_factory
from app.ingestion.pipeline import ingest_board
from app.ingestion.pilot_purge import purge_source
from app.models import Employer, IngestionRun, Posting, PostingObservation, Source


url = os.environ.get("DWI_TEST_DATABASE_URL")
if not url:
    raise SystemExit("Refusing to execute without explicit DWI_TEST_DATABASE_URL")
if not url.startswith(("postgresql://", "postgresql+psycopg://")):
    raise SystemExit("Refusing non-PostgreSQL test database")

factory = make_session_factory(url)
prefix = "synthetic_" + uuid4().hex[:16]
source_a = prefix + "_a"
source_b = prefix + "_b"
employer_a = "Synthetic CI Employer " + source_a
employer_b = "Synthetic CI Employer " + source_b


def record(job_id: int):
    return {
        "id": job_id,
        "title": "Synthetic Pilot PostgreSQL Engineer",
        "absolute_url": f"https://example.org/synthetic/jobs/{job_id}",
        "location": {"name": "Synthetic City"},
    }


def add(board: str, employer: str, title_id: int):
    return ingest_board(
        factory, board_token=board, employer_name=employer,
        fetcher=lambda _: [record(title_id)],
    )


try:
    a1 = add(source_a, employer_a, 101)
    a2 = add(source_a, employer_a, 101)
    b1 = add(source_b, employer_b, 202)
    assert (a1.inserted, a2.unchanged, b1.inserted) == (1, 1, 1)

    with factory() as session:
        other = session.scalar(select(Source).where(Source.board_token == source_b))
        assert other is not None
        other_id = other.id

    expected = purge_source(factory, board_token=source_a, employer_name=employer_a)
    assert (expected.sources, expected.postings, expected.observations, expected.runs) == (1, 1, 2, 2)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Posting).join(Source).where(Source.board_token == source_a)) == 1
    try:
        purge_source(factory, board_token=source_a, employer_name="Wrong Employer", commit=True)
    except ValueError:
        pass
    else:
        raise AssertionError("Wrong employer must not be purged")

    assert purge_source(factory, board_token=source_a, employer_name=employer_a, commit=True) == expected
    with factory() as session:
        assert session.scalar(select(Source).where(Source.board_token == source_a)) is None
        assert session.get(Source, other_id) is not None
        assert session.scalar(select(func.count()).select_from(Posting).where(Posting.source_id == other_id)) == 1
        assert session.scalar(select(func.count()).select_from(IngestionRun).where(IngestionRun.source_id == other_id)) == 1
        assert session.scalar(
            select(func.count()).select_from(PostingObservation).join(Posting).where(Posting.source_id == other_id)
        ) == 1
        assert session.scalar(select(Employer).where(Employer.name == employer_a)) is None
        assert session.scalar(select(Employer).where(Employer.name == employer_b)) is not None
    assert purge_source(factory, board_token=source_a, employer_name=employer_a, commit=True).sources == 0
    print("Synthetic PostgreSQL pilot purge: preview, mismatch, isolation, repeat deletion PASS")
finally:
    # Cleanup the other synthetic fixture even when assertions fail.
    for board, employer in ((source_a, employer_a), (source_b, employer_b)):
        purge_source(factory, board_token=board, employer_name=employer, commit=True)
