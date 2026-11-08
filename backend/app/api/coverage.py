"""Read-only completeness and source coverage analytics for synthetic test records.

This endpoint deliberately reuses the existing local-only postings API gate
and exact synthetic-source predicates. Counts are observations, not active
vacancies, hiring outcomes, or representative labor-market coverage.
"""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.postings import (
    COUNTING_RULE, _synthetic_scope, _utc, get_postings_session,
    require_postings_api_enabled,
)
from app.models import Employer, Posting, Source


router = APIRouter(prefix="/api/v1", tags=["coverage"])


class CoverageCounts(BaseModel):
    posting_count: int
    location_present: int
    first_published_at_present: int
    source_updated_at_present: int
    location_coverage_pct: float | None
    published_date_coverage_pct: float | None
    source_update_coverage_pct: float | None


class CoverageSource(BaseModel):
    platform: str
    board_token: str
    employer: str
    metrics: CoverageCounts
    latest_observed_at: datetime | None


class CoverageReport(BaseModel):
    data_scope: Literal["synthetic_only"]
    counting_rule: Literal["distinct_source_postings"]
    total_sources: int
    total_employers: int
    totals: CoverageCounts
    latest_observed_at: datetime | None
    limit: int
    offset: int
    next_offset: int | None
    sources: list[CoverageSource]


def _present_metrics(count: int, location: int, published: int, updated: int) -> CoverageCounts:
    """Report completeness over distinct current source postings.

    Percentages are undefined (null) if no postings exist in that slice.
    They do not measure whether missing values were available upstream.
    """
    def percentage(numerator: int) -> float | None:
        return round(100.0 * numerator / count, 1) if count else None

    return CoverageCounts(
        posting_count=count,
        location_present=location,
        first_published_at_present=published,
        source_updated_at_present=updated,
        location_coverage_pct=percentage(location),
        published_date_coverage_pct=percentage(published),
        source_update_coverage_pct=percentage(updated),
    )


def _metrics_expressions():
    """Shared SQL aggregates for global and per-source counts (SQLite + PostgreSQL)."""
    return (
        func.count(Posting.id),
        func.coalesce(func.sum(case((
            func.length(func.trim(Posting.location_raw)) > 0, 1,
        ), else_=0)), 0),
        func.coalesce(func.sum(case((Posting.first_published_at.is_not(None), 1), else_=0)), 0),
        func.coalesce(func.sum(case((Posting.source_updated_at.is_not(None), 1), else_=0)), 0),
        func.max(Posting.last_seen_at),
    )


@router.get("/coverage", response_model=CoverageReport)
def source_coverage(
    _: Annotated[None, Depends(require_postings_api_enabled)],
    session: Annotated[Session, Depends(get_postings_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
    employer: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
) -> CoverageReport:
    """Summarize stored synthetic-source field completeness.

    Filters and global counts apply before pagination; only sources are paged.
    A synthetic source without postings is still included with null percentages.
    """
    if employer is not None and not employer.strip():
        raise HTTPException(status_code=422, detail="Employer filter cannot be blank.")
    filters = list(_synthetic_scope())
    if employer is not None:
        filters.append(func.lower(Employer.name) == employer.strip().lower())

    total_sources, total_employers, *all_metrics = session.execute(
        select(
            func.count(func.distinct(Source.id)),
            func.count(func.distinct(Employer.id)),
            *_metrics_expressions(),
        )
        .select_from(Source)
        .join(Employer, Source.employer_id == Employer.id)
        .outerjoin(Posting, Posting.source_id == Source.id)
        .where(*filters)
    ).one()

    rows = session.execute(
        select(
            Source.platform,
            Source.board_token,
            Employer.name,
            *_metrics_expressions(),
        )
        .select_from(Source)
        .join(Employer, Source.employer_id == Employer.id)
        .outerjoin(Posting, Posting.source_id == Source.id)
        .where(*filters)
        .group_by(Source.id, Source.platform, Source.board_token, Employer.id, Employer.name)
        .order_by(Employer.name.asc(), Source.platform.asc(), Source.board_token.asc(), Source.id.asc())
        .limit(limit)
        .offset(offset)
    ).all()

    sources = [
        CoverageSource(
            platform=platform,
            board_token=token,
            employer=name,
            metrics=_present_metrics(int(count), int(loc), int(published), int(updated)),
            latest_observed_at=_utc(latest_seen),
        )
        for platform, token, name, count, loc, published, updated, latest_seen in rows
    ]

    count, loc, published, updated, latest_seen = all_metrics
    return CoverageReport(
        data_scope="synthetic_only",
        counting_rule=COUNTING_RULE,
        total_sources=int(total_sources),
        total_employers=int(total_employers),
        totals=_present_metrics(int(count), int(loc), int(published), int(updated)),
        latest_observed_at=_utc(latest_seen),
        limit=limit,
        offset=offset,
        next_offset=offset + limit if offset + limit < total_sources else None,
        sources=sources,
    )
