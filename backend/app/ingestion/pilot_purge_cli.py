"""Local pilot source purge CLI; no Greenhouse network activity.

Examples:
  python -m app.ingestion.pilot_purge_cli --board example --employer "Example"
  python -m app.ingestion.pilot_purge_cli --board example --employer "Example" --confirm example
"""

import argparse
import json
import os

from app.db import make_session_factory
from app.ingestion.greenhouse import validated_token
from app.ingestion.pilot_policy import parse_allowlist, require_private_pilot_database
from app.ingestion.pilot_purge import purge_source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview or purge one private pilot source")
    parser.add_argument("--board", required=True)
    parser.add_argument("--employer", required=True)
    parser.add_argument("--confirm", help="Exact board token required to commit irreversible purge")
    args = parser.parse_args(argv)
    try:
        token = validated_token(args.board)
        allowed = parse_allowlist(os.environ.get("DWI_PILOT_ALLOWLIST"))
        source = allowed.get(token)
        if source is None or source.employer != args.employer.strip():
            raise ValueError("Source must match the configured board/employer allowlist.")
        url = require_private_pilot_database()
        if args.confirm is not None and args.confirm != token:
            raise ValueError("--confirm must match the normalized board token exactly.")
    except ValueError as exc:
        parser.error(str(exc))

    counts = purge_source(
        make_session_factory(url),
        board_token=token,
        employer_name=source.employer,
        commit=args.confirm is not None,
    )
    print(json.dumps({
        "board": token,
        "mode": "purged" if args.confirm is not None else "preview (no writes)",
        **counts.__dict__,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
