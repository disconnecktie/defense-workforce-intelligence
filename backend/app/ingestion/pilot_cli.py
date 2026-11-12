"""Manually initiated, fail-closed local-only Greenhouse pilot.

Usage:
  python -m app.ingestion.pilot_cli --board demo --employer "Demo" --dry-run --execute

This command never runs on import or on a schedule. Live requests require
explicit source opt-in; persistence requires a separate approval gate.
"""

import argparse
import json
import logging
import os

from app.db import make_session_factory
from app.ingestion.greenhouse import fetch_jobs
from app.ingestion.normalize import InvalidPosting, normalize_job
from app.ingestion.pipeline import ingest_board
from app.ingestion.pilot_metadata import minimized_feed
from app.ingestion.pilot_policy import require_pilot_source, require_private_pilot_database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DWI controlled local metadata pilot")
    parser.add_argument("--board", required=True, help="Exact allowlisted Greenhouse board token")
    parser.add_argument("--employer", required=True, help="Exact allowlisted employer name")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Fetch and validate metadata without any database writes")
    mode.add_argument("--persist", action="store_true", help="Write only to a dedicated private pilot PostgreSQL database")
    parser.add_argument("--execute", action="store_true", help="Acknowledge this will contact the configured public source")
    args = parser.parse_args(argv)

    if not args.execute:
        parser.error("Explicit --execute required before any source requests.")
    try:
        source = require_pilot_source(args.board, args.employer)
    except ValueError as exc:
        parser.error(str(exc))

    if args.persist:
        # Check every condition BEFORE opening the database or sending HTTP requests.
        if os.environ.get("DWI_SOURCE_USE_APPROVED") != "1":
            parser.error("Persistence remains disabled until applicable source-use conditions have been reviewed (DWI_SOURCE_USE_APPROVED=1).")
        try:
            url = require_private_pilot_database()
        except ValueError as exc:
            parser.error(str(exc))
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        result = ingest_board(
            make_session_factory(url),
            board_token=source.board_token,
            employer_name=source.employer,
            fetcher=lambda token: minimized_feed(fetch_jobs(token)),
        )
        print(json.dumps({"mode": "private-local-pilot", **result.__dict__}, indent=2))
    else:
        jobs = minimized_feed(fetch_jobs(source.board_token))
        accepted = 0
        rejected = 0
        for raw in jobs:
            try:
                normalize_job(raw)
                accepted += 1
            except (InvalidPosting, TypeError, AttributeError):
                rejected += 1
        # Never print live job titles, URLs, raw source objects or other records.
        print(json.dumps({
            "mode": "dry-run (no database writes)",
            "board": source.board_token,
            "fetched": len(jobs),
            "validated": accepted,
            "rejected": rejected,
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
