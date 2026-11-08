"""Offline CLI safety tests for Greenhouse preview and explicit persistence approval."""

import json
import sys
from unittest.mock import Mock

import pytest

import app.ingestion.__main__ as cli
from app.ingestion.pipeline import RunSummary


@pytest.mark.parametrize("approval", [None, "0", "true", "yes"])
def test_persist_refused_without_explicit_exact_approval(
    monkeypatch, capsys, approval,
):
    if approval is None:
        monkeypatch.delenv("DWI_SOURCE_USE_APPROVED", raising=False)
    else:
        monkeypatch.setenv("DWI_SOURCE_USE_APPROVED", approval)
    monkeypatch.setattr(sys, "argv", [
        "python -m app.ingestion", "--board", "syntheticboard", "--persist",
    ])
    fetch = Mock(side_effect=AssertionError("No network should be called"))
    make_factory = Mock(side_effect=AssertionError("No database should be opened"))
    monkeypatch.setattr(cli, "fetch_jobs", fetch)
    monkeypatch.setattr(cli, "make_session_factory", make_factory)
    monkeypatch.setattr(
        cli, "ingest_board", Mock(side_effect=AssertionError("No ingestion permitted")),
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    assert "Persistence disabled until source-use" in capsys.readouterr().err
    fetch.assert_not_called()
    make_factory.assert_not_called()
    cli.ingest_board.assert_not_called()


def test_preview_does_not_persist_even_when_approval_flag_exists(monkeypatch, capsys):
    monkeypatch.setenv("DWI_SOURCE_USE_APPROVED", "1")
    monkeypatch.setattr(sys, "argv", [
        "python -m app.ingestion", "--board", "SYNTHETICBOARD",
    ])
    mocked_jobs = [
        {"id": item, "title": f"Synthetic Job {item}"} for item in range(7)
    ]
    fetch = Mock(return_value=mocked_jobs)
    monkeypatch.setattr(cli, "fetch_jobs", fetch)
    monkeypatch.setattr(
        cli, "make_session_factory",
        Mock(side_effect=AssertionError("Preview must not open database")),
    )
    monkeypatch.setattr(
        cli, "ingest_board",
        Mock(side_effect=AssertionError("Preview must not persist")),
    )

    assert cli.main() == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "read-only preview (no database writes)"
    assert payload["board"] == "syntheticboard"
    assert payload["fetched"] == 7
    assert payload["sample"] == mocked_jobs[:5]
    fetch.assert_called_once_with("syntheticboard")
    cli.make_session_factory.assert_not_called()
    cli.ingest_board.assert_not_called()


def test_approved_persist_requires_explicit_option_and_uses_given_source(monkeypatch, capsys):
    monkeypatch.setenv("DWI_SOURCE_USE_APPROVED", "1")
    monkeypatch.setattr(sys, "argv", [
        "python -m app.ingestion", "--board", "SYNTHETICBOARD",
        "--employer", "Synthetic Employer", "--persist",
    ])
    sentinel_factory = object()
    make_factory = Mock(return_value=sentinel_factory)
    summary = RunSummary(
        run_id=23, status="succeeded", fetched=2,
        inserted=2, updated=0, unchanged=0, rejected=0,
        errors=0, duration_ms=12, rejection_reasons={},
    )
    ingest = Mock(return_value=summary)
    monkeypatch.setattr(cli, "make_session_factory", make_factory)
    monkeypatch.setattr(cli, "ingest_board", ingest)
    monkeypatch.setattr(
        cli, "fetch_jobs",
        Mock(side_effect=AssertionError("Persist path must run through ingestion pipeline")),
    )

    assert cli.main() == 0

    make_factory.assert_called_once_with()
    ingest.assert_called_once_with(
        sentinel_factory, board_token="syntheticboard",
        employer_name="Synthetic Employer",
    )
    cli.fetch_jobs.assert_not_called()
    assert json.loads(capsys.readouterr().out) == summary.__dict__


def test_invalid_board_is_refused_before_read_or_database_access(monkeypatch):
    monkeypatch.setenv("DWI_SOURCE_USE_APPROVED", "1")
    monkeypatch.setattr(sys, "argv", [
        "python -m app.ingestion", "--board", "../unsafe", "--persist",
    ])
    fetch = Mock(side_effect=AssertionError("Must not fetch"))
    make_factory = Mock(side_effect=AssertionError("Must not access DB"))
    monkeypatch.setattr(cli, "fetch_jobs", fetch)
    monkeypatch.setattr(cli, "make_session_factory", make_factory)
    with pytest.raises(ValueError, match="Invalid Greenhouse board token"):
        cli.main()
    fetch.assert_not_called()
    make_factory.assert_not_called()
