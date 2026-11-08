"""Synthetic-only current-posting read API (no ingestion, analytics inference, or writes).

An explicit opt-in and a strict synthetic source convention prevent unreviewed
third-party employer records from being exposed by this first API slice.
The source convention is a development control, not a replacement for licensing.
"""

from collections.abc import Iterator
from datetime import datetime, timezone
from functools import lru_cache
import os
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db import database_url, make_session_factory
from app.models import Employer, Posting, Source


router = APIRouter(prefix="/api/v1", tags=["postings"])

COUNTING_RULE = "distinct_source_postings"


class EmployerRead(BaseModel):
    id: int
    name: str


class PostingSourceRead(BaseModel):
    platform: str
    board_token: str
    external_posting_id: str
    url: str


class PostingRead(BaseModel):
    id: int
    employer: EmployerRead
    title: str
    location_raw: str | None
    source: PostingSourceRead
    first_published_at: datetime | None
    source_updated_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime


class PageSourceRead(BaseModel):
    platform: str
    board_token: str
    employer: str


class PostingsPageRead(BaseModel):
    data_scope: Literal["synthetic_only"]
    counting_rule: Literal["distinct_source_postings"]
    total: int
    limit: int
    offset: int
    next_offset: int | None
    latest_observed_at: datetime | None
    page_sources: list[PageSourceRead]
    items: list[PostingRead]


@lru_cache(maxsize=4)
def _session_factory(url: str) -> sessionmaker[Session]:
    """Reuse a DB engine; tests override the dependency with a disposable DB."""
    return make_session_factory(url)


def get_postings_session() -> Iterator[Session]:
    with _session_factory(database_url())() as session:
        yield session


def require_postings_api_enabled() -> None:
    if os.environ.get("DWI_POSTINGS_API_ENABLED") != "1":
        raise HTTPException(
            status_code=503,
            detail="Postings API disabled until enabled for local synthetic-data validation.",
        )


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    # PostgreSQL returns aware UTC datetimes. SQLite in local tests may strip
    # the tzinfo from a DateTime(timezone=True) column on round-trip.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _synthetic_scope():
    """Only allow synthetic CI smoke sources, never real employer boards.

    Ingestion synthetic tests create greenhouse sources with a unique
    'synthetic_' board token and 'Synthetic CI Employer ' name. The two
    independent predicates exclude ordinary Greenhouse employer data.
    """
    return (
        Source.platform == "greenhouse",
        Source.board_token.startswith("synthetic_", autoescape=True),
        Employer.name.startswith("Synthetic CI Employer ", autoescape=True),
    )


@router.get("/postings", response_model=PostingsPageRead)
def list_postings(
    _: Annotated[None, Depends(require_postings_api_enabled)],
    session: Annotated[Session, Depends(get_postings_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
    employer: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
) -> PostingsPageRead:
    """List current synthetic posting records with stable, bounded pagination.

    This is an observation listing, not a vacancy/openings assertion.
    No live data can be selected in this initial unapproved-source phase.
    """
    if employer is not None and not employer.strip():
        raise HTTPException(status_code=422, detail="Employer filter cannot be blank.")

    filters = list(_synthetic_scope())
    if employer is not None:
        filters.append(func.lower(Employer.name) == employer.strip().lower())

    # Count and latest observation cover ALL filtered postings, not just this
    # page; the separate page_sources property covers only returned rows.
    base = (
        select(Posting)
        .join(Source, Posting.source_id == Source.id)
        .join(Employer, Source.employer_id == Employer.id)
        .where(*filters)
    )
    total = session.scalar(
        select(func.count(Posting.id))
        .select_from(Posting)
        .join(Source, Posting.source_id == Source.id)
        .join(Employer, Source.employer_id == Employer.id)
        .where(*filters)
    ) or 0
    latest_observed_at = session.scalar(
        select(func.max(Posting.last_seen_at))
        .select_from(Posting)
        .join(Source, Posting.source_id == Source.id)
        .join(Employer, Source.employer_id == Employer.id)
        .where(*filters)
    )

    rows = session.execute(
        select(Posting, Source, Employer)
        .join(Source, Posting.source_id == Source.id)
        .join(Employer, Source.employer_id == Employer.id)
        .where(*filters)
        .order_by(Posting.last_seen_at.desc(), Posting.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    items = [
        PostingRead(
            id=post.id,
            employer=EmployerRead(id=org.id, name=org.name),
            title=post.title_raw,
            location_raw=post.location_raw,
            source=PostingSourceRead(
                platform=source.platform,
                board_token=source.board_token,
                external_posting_id=post.external_posting_id,
                url=post.source_url,
            ),
            first_published_at=_utc(post.first_published_at),
            source_updated_at=_utc(post.source_updated_at),
            first_seen_at=_utc(post.first_seen_at),
            last_seen_at=_utc(post.last_seen_at),
        )
        for post, source, org in rows
    ]

    page_source_keys = {
        (source.platform, source.board_token, org.name)
        for _, source, org in rows
    }
    page_sources = [
        PageSourceRead(platform=platform, board_token=board, employer=org_name)
        for platform, board, org_name in sorted(page_source_keys)
    ]

    return PostingsPageRead(
        data_scope="synthetic_only",
        counting_rule=COUNTING_RULE,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=(offset + limit if offset + limit < total else None),
        latest_observed_at=_utc(latest_observed_at),
        page_sources=page_sources,
        items=items,
    )
