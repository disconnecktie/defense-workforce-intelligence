"""Conservative normalization of public job-post metadata, with no inference."""

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Any
from urllib.parse import urlsplit


class InvalidPosting(ValueError):
    """Missing or malformed required source fields."""


def parse_date(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise InvalidPosting("Invalid posting date type.")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidPosting("Invalid posting date format.") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise InvalidPosting("Posting date has no timezone offset.")
    return result


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
    raw_id = data.get("id")
    if isinstance(raw_id, bool) or not isinstance(raw_id, (int, str)):
        raise InvalidPosting("Posting ID is missing or invalid.")
    post_id = str(raw_id).strip()
    if not post_id or not post_id.isdigit() or int(post_id) <= 0:
        raise InvalidPosting("Posting ID is missing or invalid.")
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        raise InvalidPosting("Posting title is required.")
    url = data.get("absolute_url")
    if not isinstance(url, str) or not url.strip():
        raise InvalidPosting("Posting URL is required.")
    url = url.strip()
    parsed = urlsplit(url)
    if parsed.scheme not in ("https", "http") or not parsed.netloc or parsed.username or parsed.password:
        raise InvalidPosting("Posting URL must be a public HTTP(S) URL.")
    location = data.get("location")
    if location is not None and not isinstance(location, dict):
        raise InvalidPosting("Posting location must be an object.")
    raw_location = (location or {}).get("name")
    if raw_location is not None and not isinstance(raw_location, str):
        raise InvalidPosting("Location name must be text.")
    loc = raw_location.strip() if raw_location else None
    internal = data.get("internal_job_id")
    requisition = data.get("requisition_id")
    first_published = parse_date(data.get("first_published"))
    source_updated = parse_date(data.get("updated_at"))
    chosen = {
        "id": post_id,
        "title": title.strip(),
        "absolute_url": url,
        "location": loc,
        "internal_job_id": str(internal) if internal is not None else None,
        "requisition_id": str(requisition) if requisition is not None else None,
        "first_published": first_published.isoformat() if first_published else None,
        "updated_at": source_updated.isoformat() if source_updated else None,
    }
    digest = sha256(json.dumps(chosen, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return NormalizedPosting(
        external_posting_id=post_id,
        title_raw=title.strip(),
        source_url=url,
        location_raw=loc,
        source_internal_job_id=chosen["internal_job_id"],
        requisition_id=chosen["requisition_id"],
        first_published_at=first_published,
        source_updated_at=source_updated,
        content_hash=digest,
    )
