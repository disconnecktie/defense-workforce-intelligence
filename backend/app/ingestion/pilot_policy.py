"""Opt-in local Greenhouse pilot configuration and preflight validation.

No network calls, database connections, or persistent side effects occur here.
This module deliberately does not authorize source access.
"""

import json
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.ingestion.greenhouse import validated_token


@dataclass(frozen=True)
class PilotSource:
    board_token: str
    employer: str


def parse_allowlist(raw: str | None) -> dict[str, PilotSource]:
    """Parse explicit JSON object mapping Greenhouse board tokens to employers.

    Example: {"example_board": "Example Employer"}.
    Reject duplicates after case normalization and invalid structures.
    """
    if not raw:
        raise ValueError("DWI_PILOT_ALLOWLIST is required.")
    class JsonPairs(list):
        pass

    try:
        pairs = json.loads(raw, object_pairs_hook=JsonPairs)
    except (ValueError, TypeError) as exc:
        raise ValueError("DWI_PILOT_ALLOWLIST must be valid JSON.") from exc
    if not isinstance(pairs, JsonPairs):
        raise ValueError("DWI_PILOT_ALLOWLIST must be a JSON object.")
    result: dict[str, PilotSource] = {}
    for pair in pairs:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ValueError("DWI_PILOT_ALLOWLIST must be a JSON object.")
        token, employer = pair
        if not isinstance(token, str) or not isinstance(employer, str):
            raise ValueError("Board tokens and employer names must be strings.")
        board = validated_token(token)
        name = employer.strip()
        if not name or len(name) > 200:
            raise ValueError("Employer name must contain 1-200 characters.")
        if board in result:
            raise ValueError("Duplicate board token in allowlist.")
        result[board] = PilotSource(board, name)
    if not result:
        raise ValueError("DWI_PILOT_ALLOWLIST cannot be empty.")
    return result


def require_pilot_source(board_token: str, employer: str, *, environ=None) -> PilotSource:
    env = os.environ if environ is None else environ
    if env.get("DWI_PILOT_ENABLED") != "1":
        raise ValueError("Local pilot is disabled; DWI_PILOT_ENABLED must be 1.")
    board = validated_token(board_token)
    source = parse_allowlist(env.get("DWI_PILOT_ALLOWLIST")).get(board)
    if source is None or source.employer != employer.strip():
        raise ValueError("Board and employer must exactly match an allowed source.")
    suspended = {validated_token(part) for part in env.get("DWI_PILOT_SUSPENDED_BOARDS", "").split(",") if part.strip()}
    if board in suspended:
        raise ValueError("Pilot source is suspended.")
    return source


def require_private_pilot_database(*, environ=None) -> str:
    """Fail closed unless a distinct localhost PostgreSQL DB was selected.

    This check is a configuration guard, not a network isolation guarantee.
    Database permissions and firewall rules remain separately necessary.
    """
    env = os.environ if environ is None else environ
    url = env.get("DWI_PILOT_DATABASE_URL", "")
    parsed = urlsplit(url)
    if parsed.scheme not in ("postgresql", "postgresql+psycopg"):
        raise ValueError("Pilot storage requires a PostgreSQL URL.")
    if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Pilot database must be local-only.")
    if not parsed.path.strip("/").endswith("_pilot"):
        raise ValueError("Pilot database name must end in _pilot.")
    if not parsed.username or not parsed.password:
        raise ValueError("Pilot database requires explicit credentials.")
    from app.db import database_url
    if url.replace("postgresql://", "postgresql+psycopg://", 1) == database_url():
        raise ValueError("Pilot database must be separate from application database.")
    return url
