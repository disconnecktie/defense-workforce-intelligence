"""Offline tests for explicit opt-in and isolation of the pilot CLI."""

import json
from unittest.mock import Mock

import pytest

from app.ingestion import pilot_cli


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("DWI_PILOT_ENABLED", "1")
    monkeypatch.setenv("DWI_PILOT_ALLOWLIST", '{"syntheticboard":"Synthetic Employer"}')
    monkeypatch.delenv("DWI_PILOT_SUSPENDED_BOARDS", raising=False)
    monkeypatch.delenv("DWI_SOURCE_USE_APPROVED", raising=False)
    return monkeypatch


@pytest.mark.parametrize("args", [
    ["--board", "syntheticboard", "--employer", "Synthetic Employer", "--dry-run"],
    ["--board", "syntheticboard", "--employer", "Synthetic Employer", "--persist"],
])
def test_execute_flag_required_before_io(configured, args):
    fetch = Mock(side_effect=AssertionError("network forbidden"))
    factory = Mock(side_effect=AssertionError("database forbidden"))
    configured.setattr(pilot_cli, "fetch_jobs", fetch)
    configured.setattr(pilot_cli, "make_session_factory", factory)
    with pytest.raises(SystemExit) as result:
        pilot_cli.main(args)
    assert result.value.code == 2
    fetch.assert_not_called()
    factory.assert_not_called()


def test_allowlist_rejected_before_io(configured):
    fetch = Mock(side_effect=AssertionError("network forbidden"))
    configured.setattr(pilot_cli, "fetch_jobs", fetch)
    with pytest.raises(SystemExit) as result:
        pilot_cli.main([
            "--board", "unapproved", "--employer", "Synthetic Employer", "--dry-run", "--execute",
        ])
    assert result.value.code == 2
    fetch.assert_not_called()


def test_dry_run_validates_but_never_opens_database(configured, capsys):
    fetch = Mock(return_value=[
        {"id": 17, "title": "Test Analyst", "absolute_url": "https://example.org/jobs/17"},
        {"id": None, "title": "Malformed"},
    ])
    configured.setattr(pilot_cli, "fetch_jobs", fetch)
    factory = Mock(side_effect=AssertionError("database forbidden"))
    configured.setattr(pilot_cli, "make_session_factory", factory)
    assert pilot_cli.main([
        "--board", "syntheticboard", "--employer", "Synthetic Employer",
        "--dry-run", "--execute",
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {
        "mode": "dry-run (no database writes)", "board": "syntheticboard",
        "fetched": 2, "validated": 1, "rejected": 1,
    }
    factory.assert_not_called()
    fetch.assert_called_once_with("syntheticboard")


def test_persist_requires_source_review_and_private_database(configured):
    factory = Mock(side_effect=AssertionError("database forbidden"))
    configured.setattr(pilot_cli, "make_session_factory", factory)
    args = ["--board", "syntheticboard", "--employer", "Synthetic Employer", "--persist", "--execute"]
    with pytest.raises(SystemExit) as result:
        pilot_cli.main(args)
    assert result.value.code == 2
    configured.setenv("DWI_SOURCE_USE_APPROVED", "1")
    configured.setenv("DWI_PILOT_DATABASE_URL", "postgresql://u:p@remote.example/dwi_pilot")
    with pytest.raises(SystemExit) as result:
        pilot_cli.main(args)
    assert result.value.code == 2
    factory.assert_not_called()


def test_persist_routes_to_existing_pipeline_only_after_guards(configured, capsys):
    configured.setenv("DWI_SOURCE_USE_APPROVED", "1")
    configured.setenv("DWI_PILOT_DATABASE_URL", "postgresql://pilot:pw@localhost:5432/isolated_pilot")
    configured.setenv("DATABASE_URL", "postgresql://dwi:pw@localhost:5432/dwi")
    sentinel_factory = object()
    factory = Mock(return_value=sentinel_factory)
    from types import SimpleNamespace
    ingest = Mock(return_value=SimpleNamespace(run_id=1, status="succeeded"))
    configured.setattr(pilot_cli, "make_session_factory", factory)
    configured.setattr(pilot_cli, "ingest_board", ingest)
    configured.setattr(pilot_cli, "fetch_jobs", Mock(side_effect=AssertionError("wrong fetch path")))
    assert pilot_cli.main([
        "--board", "SYNTHETICBOARD", "--employer", "Synthetic Employer",
        "--persist", "--execute",
    ]) == 0
    factory.assert_called_once_with("postgresql://pilot:pw@localhost:5432/isolated_pilot")
    ingest.assert_called_once()
    args, kwargs = ingest.call_args
    assert args == (sentinel_factory,)
    assert kwargs["board_token"] == "syntheticboard"
    assert kwargs["employer_name"] == "Synthetic Employer"
    assert callable(kwargs["fetcher"])
    assert json.loads(capsys.readouterr().out)["mode"] == "private-local-pilot"
