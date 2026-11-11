"""Minimize Greenhouse metadata for the local pilot before persistence.

Only listed public job metadata is passed into the established normalizer.
Extra fields, description HTML and applicant information are discarded.
"""

from typing import Any


def pilot_metadata(job: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(job, dict):
        return {}  # Existing normalizer rejects malformed records.
    location = job.get("location")
    return {
        "id": job.get("id"),
        "title": job.get("title"),
        "absolute_url": job.get("absolute_url"),
        "location": {"name": location.get("name")} if isinstance(location, dict) else location,
        "updated_at": job.get("updated_at"),
    }


def minimized_feed(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return independently allocated, explicitly selected source fields."""
    return [pilot_metadata(job) for job in jobs]
