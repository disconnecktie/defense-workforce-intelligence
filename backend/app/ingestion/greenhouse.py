"""Read-only Greenhouse public Job Board client.

Uses the publicly documented GET endpoint only. This is *not* a scheduler.
Automated collection and redistribution are subject to source usage review.
"""

import re
import time
from collections.abc import Callable
from typing import Any

import httpx

BOARD_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{2,120}$")
BASE_URL = "https://boards-api.greenhouse.io/v1/boards"
TRANSIENT_STATUSES = {429, 500, 502, 503, 504}


def validated_token(board_token: str) -> str:
    token = board_token.strip().lower()
    if not BOARD_TOKEN_PATTERN.fullmatch(token):
        raise ValueError("Invalid Greenhouse board token.")
    return token


def fetch_jobs(
    board_token: str,
    *,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
    max_retries: int = 2,
) -> list[dict[str, Any]]:
    """Fetch the full public *metadata* feed; no descriptions or applicant data.

    A mismatched reported count aborts ingestion rather than treating a
    potentially partial feed as a complete successful snapshot.
    """
    token = validated_token(board_token)
    url = f"{BASE_URL}/{token}/jobs"
    owns_client = client is None
    if client is None:
        client = httpx.Client(
            timeout=httpx.Timeout(30.0),
            follow_redirects=False,
            headers={"User-Agent": "DWI-Research-Collector/0.1 (read-only public jobs)"},
        )
    try:
        for attempt in range(max_retries + 1):
            try:
                response = client.get(url)
                if response.status_code in TRANSIENT_STATUSES and attempt < max_retries:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = min(30.0, max(0.0, float(retry_after))) if retry_after else 2 ** attempt
                    except ValueError:
                        delay = 2 ** attempt
                    sleep(delay)
                    continue
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
                    raise ValueError("Unexpected Greenhouse jobs response shape.")
                jobs = data["jobs"]
                if not all(isinstance(job, dict) for job in jobs):
                    raise ValueError("Greenhouse jobs response contains non-object entries.")
                meta = data.get("meta")
                if isinstance(meta, dict) and isinstance(meta.get("total"), int):
                    if meta["total"] != len(jobs):
                        raise ValueError("Greenhouse reported count differs from returned jobs; refusing partial feed.")
                return jobs
            except (httpx.TransportError,) as exc:
                if attempt == max_retries:
                    raise
                sleep(2 ** attempt)
    finally:
        if owns_client:
            client.close()
    raise RuntimeError("Greenhouse retries exhausted.")
