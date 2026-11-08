"""Run: python -m app.ingestion --board andurilindustries [--persist]."""

import argparse
import json
import logging
import os

from app.db import make_session_factory
from app.ingestion.greenhouse import fetch_jobs, validated_token
from app.ingestion.pipeline import ingest_board


def main() -> int:
    parser = argparse.ArgumentParser(description="DWI read-only Greenhouse collector")
    parser.add_argument("--board", default="andurilindustries", help="Public Greenhouse board token")
    parser.add_argument("--employer", default="Anduril Industries", help="Employer name for source attribution")
    parser.add_argument("--persist", action="store_true", help="Write postings/observations to PostgreSQL")
    args = parser.parse_args()
    board = validated_token(args.board)
    if args.persist:
        if os.environ.get("DWI_SOURCE_USE_APPROVED") != "1":
            parser.error(
                "Persistence disabled until source-use and retention review is completed. "
                "Set DWI_SOURCE_USE_APPROVED=1 only after approval."
            )
        # JSONL event records go to stderr; the final run summary remains stdout.
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        result = ingest_board(make_session_factory(), board_token=board, employer_name=args.employer)
        print(json.dumps(result.__dict__, indent=2))
    else:
        jobs = fetch_jobs(board)
        print(json.dumps({
            "mode": "read-only preview (no database writes)",
            "board": board, "fetched": len(jobs),
            "sample": [
                {"id": job.get("id"), "title": job.get("title")}
                for job in jobs[:5]
            ],
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
