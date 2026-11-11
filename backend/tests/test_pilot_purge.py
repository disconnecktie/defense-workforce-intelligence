"""Offline transactional deletion tests using disposable synthetic SQLite data."""

import json
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.ingestion.pipeline import ingest_board
from app.ingestion.pilot_purge import purge_source
from app.ingestion import pilot_purge_cli
from app.models import Base, Employer, IngestionRun, Posting, PostingObservation, Source


@pytest.fixture
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'synthetic-purge.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


def ingest(factory, board, employer, title="Synthetic Engineer"):
    job = {
        "id": 123, "title": title,
        "absolute_url": "https://example.org/jobs/123",
        "location": {"name": "Example"},
    }
    return ingest_board(factory, board_token=board, employer_name=employer, fetcher=lambda _: [job])


def counts(factory):
    with factory() as session:
        return (
            session.scalar(select(func.count()).select_from(Source)),
            session.scalar(select(func.count()).select_from(Posting)),
            session.scalar(select(func.count()).select_from(IngestionRun)),
            session.scalar(select(func.count()).select_from(PostingObservation)),
            session.scalar(select(func.count()).select_from(Employer)),
        )


def test_preview_and_purge_only_one_source(factory):
    ingest(factory, "alpha", "Alpha LLC")
    ingest(factory, "alpha", "Alpha LLC", "Synthetic Engineer II")
    ingest(factory, "beta", "Beta LLC")
    assert counts(factory) == (2, 2, 3, 3, 2)
    preview = purge_source(factory, board_token="alpha", employer_name="Alpha LLC")
    assert (preview.sources, preview.postings, preview.runs, preview.observations) == (1, 1, 2, 2)
    assert counts(factory) == (2, 2, 3, 3, 2)
    assert purge_source(factory, board_token="alpha", employer_name="Alpha LLC", commit=True) == preview
    assert counts(factory) == (1, 1, 1, 1, 1)
    assert purge_source(factory, board_token="alpha", employer_name="Alpha LLC", commit=True).sources == 0


def test_mismatch_refuses_purge_without_changing_anything(factory):
    ingest(factory, "alpha", "Alpha LLC")
    with pytest.raises(ValueError, match="employer does not match"):
        purge_source(factory, board_token="alpha", employer_name="Wrong", commit=True)
    assert counts(factory) == (1, 1, 1, 1, 1)


def test_purge_preserves_shared_employer(factory):
    ingest(factory, "alpha", "Shared LLC")
    ingest(factory, "beta", "Shared LLC")
    purge_source(factory, board_token="alpha", employer_name="Shared LLC", commit=True)
    assert counts(factory) == (1, 1, 1, 1, 1)


def test_purge_cli_refuses_mismatch_before_db(monkeypatch):
    monkeypatch.setenv("DWI_PILOT_ALLOWLIST", '{"alpha":"Alpha LLC"}')
    monkeypatch.setenv("DWI_PILOT_DATABASE_URL", "postgresql://pilot:pw@localhost/isolated_pilot")
    factory = Mock(side_effect=AssertionError("database forbidden"))
    monkeypatch.setattr(pilot_purge_cli, "make_session_factory", factory)
    with pytest.raises(SystemExit) as error:
        pilot_purge_cli.main(["--board", "alpha", "--employer", "Alpha LLC", "--confirm", "wrong"])
    assert error.value.code == 2
    factory.assert_not_called()


def test_purge_cli_default_is_preview_and_confirm_is_required(monkeypatch, capsys):
    monkeypatch.setenv("DWI_PILOT_ALLOWLIST", '{"alpha":"Alpha LLC"}')
    monkeypatch.setenv("DWI_PILOT_DATABASE_URL", "postgresql://pilot:pw@localhost/isolated_pilot")
    monkeypatch.setenv("DATABASE_URL", "postgresql://dwi:pw@localhost/dwi")
    from app.ingestion.pilot_purge import PurgeCounts
    factory = object()
    ingest = Mock(return_value=PurgeCounts(1, 3, 7, 2))
    make_factory = Mock(return_value=factory)
    monkeypatch.setattr(pilot_purge_cli, "make_session_factory", make_factory)
    monkeypatch.setattr(pilot_purge_cli, "purge_source", ingest)
    assert pilot_purge_cli.main(["--board", "ALPHA", "--employer", "Alpha LLC"]) == 0
    ingest.assert_called_with(factory, board_token="alpha", employer_name="Alpha LLC", commit=False)
    assert json.loads(capsys.readouterr().out)["mode"] == "preview (no writes)"
    assert pilot_purge_cli.main(["--board", "alpha", "--employer", "Alpha LLC", "--confirm", "alpha"]) == 0
    ingest.assert_called_with(factory, board_token="alpha", employer_name="Alpha LLC", commit=True)
