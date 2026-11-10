"""Read-only history of ingestion run outcomes for synthetic CI sources.

Run counters describe *processing events*, not distinct active vacancies, hires,
or changes in market demand. No inference about job closures is made.
"""
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.postings import (
    _synthetic_scope, _utc, get_postings_session, require_postings_api_enabled,
)
from app.models import Employer, IngestionRun, Source

router = APIRouter(prefix="/api/v1", tags=["ingestion-history"])


class IngestionHistoryItem(BaseModel):
    run_id: int
    employer: str
    platform: str
    board_token: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    fetched: int
    inserted: int
    updated: int
    unchanged: int
    rejected: int
    errors: int
    duration_ms: int | None


class IngestionHistoryPage(BaseModel):
    data_scope: Literal["synthetic_only"]
    counting_rule: Literal["ingestion_runs_not_vacancies"]
    total: int
    limit: int
    offset: int
    next_offset: int | None
    items: list[IngestionHistoryItem]


@router.get("/ingestion-history", response_model=IngestionHistoryPage)
def ingestion_history(
    _: Annotated[None, Depends(require_postings_api_enabled)],
    session: Annotated[Session, Depends(get_postings_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
    employer: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
) -> IngestionHistoryPage:
    """Paginate completed and failed ingestion attempts for synthetic sources.

    Runs are ordered by start time, then stable ID; source-specific IDs are
    retained. The response deliberately excludes stored raw error messages
    and rejection details to avoid disclosing source content.
    """
    if employer is not None and not employer.strip():
        raise HTTPException(status_code=422, detail="Employer filter cannot be blank.")
    filters = list(_synthetic_scope())
    if employer is not None:
        filters.append(func.lower(Employer.name) == employer.strip().lower())

    total = session.scalar(
        select(func.count(IngestionRun.id))
        .select_from(IngestionRun)
        .join(Source, IngestionRun.source_id == Source.id)
        .join(Employer, Source.employer_id == Employer.id)
        .where(*filters)
    ) or 0
    rows = session.execute(
        select(IngestionRun, Source, Employer)
        .join(Source, IngestionRun.source_id == Source.id)
        .join(Employer, Source.employer_id == Employer.id)
        .where(*filters)
        .order_by(IngestionRun.started_at.desc(), IngestionRun.id.desc())
        .limit(limit).offset(offset)
    ).all()

    return IngestionHistoryPage(
        data_scope="synthetic_only",
        counting_rule="ingestion_runs_not_vacancies",
        total=total,
        limit=limit,
        offset=offset,
        next_offset=offset + limit if offset + limit < total else None,
        items=[
            IngestionHistoryItem(
                run_id=run.id,
                employer=org.name,
                platform=source.platform,
                board_token=source.board_token,
                started_at=_utc(run.started_at),
                finished_at=_utc(run.finished_at),
                status=run.status,
                fetched=run.fetched,
                inserted=run.inserted,
                updated=run.updated,
                unchanged=run.unchanged,
                rejected=run.rejected,
                errors=run.errors,
                duration_ms=run.duration_ms,
            )
            for run, source, org in rows
        ],
    )
