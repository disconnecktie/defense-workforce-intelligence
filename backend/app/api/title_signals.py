"""Read-only synthetic title-keyword evidence API.

This API counts literal technology mentions in the currently stored title_raw
field only. It never estimates skills mentioned in missing descriptions or
the real labor market. It inherits the local-only gate and synthetic-source
predicates from the postings API.
"""

from collections import Counter
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.title_signals import (
    CANONICAL_TERMS, RULE_VERSION, extract_title_signals,
)
from app.api.postings import (
    COUNTING_RULE, _synthetic_scope, _utc, get_postings_session,
    require_postings_api_enabled,
)
from app.models import Employer, Posting, Source


router = APIRouter(prefix="/api/v1", tags=["title-signals"])
MAX_EXAMPLES_PER_TERM = 3


class SignalExample(BaseModel):
    posting_id: int
    platform: str
    board_token: str
    external_posting_id: str
    title: str
    evidence: str
    match_start: int
    match_end: int


class TermSignalCount(BaseModel):
    term: str
    postings_with_title_mention: int
    examples: list[SignalExample]


class TitleSignalsReport(BaseModel):
    data_scope: Literal["synthetic_only"]
    counting_rule: Literal["distinct_source_postings"]
    source_field: Literal["title_raw"]
    interpretation: Literal["explicit_title_mentions_not_verified_skill_requirements"]
    method_version: Literal["title_keywords_v1"]
    postings_scanned: int
    postings_with_any_term: int
    postings_without_any_term: int
    title_mention_rate_pct: float | None
    latest_observed_at: datetime | None
    terms: list[TermSignalCount]


@router.get("/title-signals", response_model=TitleSignalsReport)
def list_title_signals(
    _: Annotated[None, Depends(require_postings_api_enabled)],
    session: Annotated[Session, Depends(get_postings_session)],
    employer: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
) -> TitleSignalsReport:
    """Report literal technology title mentions over eligible synthetic records.

    The endpoint is read-only and doesn't normalize job descriptions or
    store extracted data. The same source-posting ID may occur on multiple
    boards; each board-specific posting is counted separately.
    """
    if employer is not None and not employer.strip():
        raise HTTPException(status_code=422, detail="Employer filter cannot be blank.")

    filters = list(_synthetic_scope())
    if employer is not None:
        filters.append(func.lower(Employer.name) == employer.strip().lower())

    # No pagination on an aggregate; iterate rows instead of holding titles
    # and full historical snapshots in memory. The dataset is local and
    # synthetic-only. Results include all seven canonical terms, even at zero.
    stmt = (
        select(
            Posting.id,
            Posting.external_posting_id,
            Posting.title_raw,
            Posting.last_seen_at,
            Source.platform,
            Source.board_token,
        )
        .join(Source, Posting.source_id == Source.id)
        .join(Employer, Source.employer_id == Employer.id)
        .where(*filters)
        .order_by(Posting.id)
        .execution_options(yield_per=256)
    )

    counts: Counter[str] = Counter()
    examples: dict[str, list[SignalExample]] = {term: [] for term in CANONICAL_TERMS}
    scanned = 0
    matched = 0
    latest: datetime | None = None

    for posting_id, external_id, title, last_seen, platform, board in session.execute(stmt):
        scanned += 1
        last_seen_utc = _utc(last_seen)
        if last_seen_utc is not None and (latest is None or last_seen_utc > latest):
            latest = last_seen_utc

        signals = extract_title_signals(title)
        if signals:
            matched += 1
        for signal in signals:
            counts[signal.term] += 1
            if len(examples[signal.term]) < MAX_EXAMPLES_PER_TERM:
                examples[signal.term].append(SignalExample(
                    posting_id=posting_id,
                    platform=platform,
                    board_token=board,
                    external_posting_id=external_id,
                    title=title,
                    evidence=signal.evidence,
                    match_start=signal.start,
                    match_end=signal.end,
                ))

    return TitleSignalsReport(
        data_scope="synthetic_only",
        counting_rule=COUNTING_RULE,
        source_field="title_raw",
        interpretation="explicit_title_mentions_not_verified_skill_requirements",
        method_version=RULE_VERSION,
        postings_scanned=scanned,
        postings_with_any_term=matched,
        postings_without_any_term=scanned - matched,
        title_mention_rate_pct=round(100.0 * matched / scanned, 1) if scanned else None,
        latest_observed_at=latest,
        terms=[
            TermSignalCount(
                term=term,
                postings_with_title_mention=counts[term],
                examples=examples[term],
            )
            for term in CANONICAL_TERMS
        ],
    )
