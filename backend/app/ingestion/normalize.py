"""Validate and conservatively normalize public Greenhouse job metadata.

Required malformed records are rejected. Optional fields remain nullable rather
than being inferred. The content hash covers only fields actually persisted.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from ipaddress import ip_address
import json
import re
from typing import Any
from urllib.parse import urlsplit


MAX_POSTING_ID = 100  # Match the postings.external_posting_id column.
MAX_OPTIONAL_ID = 100  # Match the optional identifier columns.
MAX_TITLE = 4000
MAX_LOCATION = 4000
MAX_SOURCE_URL = 4096
_ASCII_DIGITS = re.compile(r"[0-9]+\Z")


class InvalidPosting(ValueError):
    """Missing or malformed source data; caller should count a rejected record."""


def parse_date(value: Any) -> datetime | None:
    """Return an aware UTC datetime, or None when the source omitted the field."""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise InvalidPosting("Invalid posting date type.")
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidPosting("Invalid posting date format.") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise InvalidPosting("Posting date has no timezone offset.")
    return result.astimezone(timezone.utc)


def _posting_id(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise InvalidPosting("Posting ID is missing or invalid.")
    identifier = str(value).strip()
    # ASCII-only, bounded, and nonzero: no Unicode lookalikes or giant integers.
    if (
        not identifier
        or len(identifier) > MAX_POSTING_ID
        or _ASCII_DIGITS.fullmatch(identifier) is None
        or all(char == "0" for char in identifier)
    ):
        raise InvalidPosting("Posting ID is missing or invalid.")
    return identifier


def _optional_identifier(value: Any, *, field: str) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise InvalidPosting(f"Invalid {field} type.")
    text = str(value).strip()
    if not text:
        return None
    if len(text) > MAX_OPTIONAL_ID:
        raise InvalidPosting(f"{field} exceeds {MAX_OPTIONAL_ID} characters.")
    return text


def _public_url(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidPosting("Posting URL is required.")
    url = value.strip()
    if len(url) > MAX_SOURCE_URL or "\\" in url or any(ord(ch) < 32 or ord(ch) == 127 for ch in url):
        raise InvalidPosting("Posting URL contains invalid characters or is too long.")
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        # Accessing .port detects malformed ports (e.g. :not-a-number).
        _ = parsed.port
    except ValueError as exc:
        raise InvalidPosting("Posting URL is malformed.") from exc
    if parsed.scheme != "https" or not parsed.netloc or not host or parsed.username or parsed.password:
        raise InvalidPosting("Posting URL must be a public HTTPS URL without credentials.")
    if (
        "." not in host
        or host.startswith(".")
        or host.endswith(".")
        or ".." in host
        or host in {"localhost", "localhost.localdomain"}
        or host.endswith((".localhost", ".local", ".internal"))
        or any(ch.isspace() for ch in host)
    ):
        raise InvalidPosting("Posting URL hostname is not a public DNS name.")
    try:
        ip_address(host)
    except ValueError:
        pass
    else:
        raise InvalidPosting("Posting URL must not contain an IP address.")
    return url


@dataclass(frozen=True)
class NormalizedPosting:
    external_posting_id: str
    title_raw: str
    source_url: str
    location_raw: str | None
    source_internal_job_id: str | None
    requisition_id: str | None
    first_published_at: datetime | None
    source_updated_at: datetime | None
    content_hash: str


def normalize_job(data: dict[str, Any]) -> NormalizedPosting:
    if not isinstance(data, dict):
        raise InvalidPosting("Posting must be a JSON object.")

    post_id = _posting_id(data.get("id"))

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        raise InvalidPosting("Posting title is required.")
    if len(title) > MAX_TITLE:
        raise InvalidPosting("Posting title exceeds maximum length.")

    url = _public_url(data.get("absolute_url"))

    location = data.get("location")
    if location is not None and not isinstance(location, dict):
        raise InvalidPosting("Posting location must be an object.")
    raw_location = (location or {}).get("name")
    if raw_location is not None and not isinstance(raw_location, str):
        raise InvalidPosting("Location name must be text.")
    if raw_location is not None and len(raw_location) > MAX_LOCATION:
        raise InvalidPosting("Location name exceeds maximum length.")
    # Preserve actual source labels, including multiple locations in one label.
    loc = raw_location if raw_location and raw_location.strip() else None

    internal = _optional_identifier(data.get("internal_job_id"), field="internal_job_id")
    requisition = _optional_identifier(data.get("requisition_id"), field="requisition_id")
    first_published = parse_date(data.get("first_published"))
    source_updated = parse_date(data.get("updated_at"))

    chosen = {
        "id": post_id,
        "title": title,
        "absolute_url": url,
        "location": loc,
        "internal_job_id": internal,
        "requisition_id": requisition,
        "first_published": first_published.isoformat() if first_published else None,
        "updated_at": source_updated.isoformat() if source_updated else None,
    }
    digest = sha256(
        json.dumps(chosen, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    return NormalizedPosting(
        external_posting_id=post_id,
        title_raw=title,
        source_url=url,
        location_raw=loc,
        source_internal_job_id=internal,
        requisition_id=requisition,
        first_published_at=first_published,
        source_updated_at=source_updated,
        content_hash=digest,
    )
