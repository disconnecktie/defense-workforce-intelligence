"""Offline fail-closed pilot policy tests (no network or database)."""

import pytest

from app.ingestion.pilot_policy import (
    parse_allowlist, require_pilot_source, require_private_pilot_database,
)


def test_allowlist_normalization_and_exact_employer():
    env = {"DWI_PILOT_ENABLED": "1", "DWI_PILOT_ALLOWLIST": '{"Example_Board":"Example Employer"}'}
    source = require_pilot_source("EXAMPLE_BOARD", "Example Employer", environ=env)
    assert source.board_token == "example_board"
    with pytest.raises(ValueError, match="exactly match"):
        require_pilot_source("example_board", "Wrong Employer", environ=env)


@pytest.mark.parametrize("bad", ["[]", "null", "{}", '{"same":"One","SAME":"Two"}', '{"bad/token":"Employer"}', '{"ok":""}'])
def test_invalid_allowlists_fail_closed(bad):
    with pytest.raises(ValueError):
        parse_allowlist(bad)


def test_disabled_and_suspended_sources_are_blocked():
    base = {"DWI_PILOT_ALLOWLIST": '{"example":"Example Employer"}'}
    with pytest.raises(ValueError, match="disabled"):
        require_pilot_source("example", "Example Employer", environ=base)
    base.update(DWI_PILOT_ENABLED="1", DWI_PILOT_SUSPENDED_BOARDS="EXAMPLE")
    with pytest.raises(ValueError, match="suspended"):
        require_pilot_source("example", "Example Employer", environ=base)


def test_private_pilot_database_is_distinct_and_local(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://dwi:pw@localhost:5432/dwi")
    good = {"DWI_PILOT_DATABASE_URL": "postgresql://pilot:pw@localhost:5432/dwi_local_pilot"}
    assert require_private_pilot_database(environ=good).endswith("dwi_local_pilot")
    for bad in [
        "postgresql://pilot:pw@remote.example:5432/dwi_pilot",
        "postgresql://pilot:pw@localhost:5432/dwi",
        "postgresql://dwi:pw@localhost:5432/dwi",
        "sqlite:///dwi_pilot",
        "postgresql://pilot@localhost:5432/dwi_pilot",
    ]:
        with pytest.raises(ValueError):
            require_private_pilot_database(environ={"DWI_PILOT_DATABASE_URL": bad})


def test_no_pilot_database_url_fails():
    with pytest.raises(ValueError):
        require_private_pilot_database(environ={})
