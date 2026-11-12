"""Delete one local pilot source and all dependent observations in a transaction.

The caller MUST validate the private pilot database URL and source identity first.
This routine does not issue network requests or expose source record contents.
"""

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.ingestion.greenhouse import validated_token
from app.models import Employer, IngestionRun, Posting, PostingObservation, Source


@dataclass(frozen=True)
class PurgeCounts:
    sources: int
    postings: int
    observations: int
    runs: int


def _target(session: Session, board_token: str, employer_name: str) -> Source | None:
    board = validated_token(board_token)
    name = employer_name.strip()
    source = session.scalar(select(Source).where(
        Source.platform == "greenhouse", Source.board_token == board,
    ))
    if source is None:
        return None
    employer = session.get(Employer, source.employer_id)
    if employer is None or employer.name != name:
        raise ValueError("Board exists but employer does not match: refusing purge.")
    return source


def _counts(session: Session, source: Source | None) -> PurgeCounts:
    if source is None:
        return PurgeCounts(0, 0, 0, 0)
    post_ids = select(Posting.id).where(Posting.source_id == source.id)
    run_ids = select(IngestionRun.id).where(IngestionRun.source_id == source.id)
    return PurgeCounts(
        sources=1,
        postings=session.scalar(select(func.count()).select_from(Posting).where(
            Posting.source_id == source.id,
        )) or 0,
        observations=session.scalar(select(func.count()).select_from(PostingObservation).where(
            (PostingObservation.posting_id.in_(post_ids))
            | (PostingObservation.ingestion_run_id.in_(run_ids))
        )) or 0,
        runs=session.scalar(select(func.count()).select_from(IngestionRun).where(
            IngestionRun.source_id == source.id,
        )) or 0,
    )


def purge_source(
    factory: sessionmaker[Session], *, board_token: str, employer_name: str,
    commit: bool = False,
) -> PurgeCounts:
    """Preview counts or atomically erase one source, its postings/runs/history.

    Reject an employer mismatch. Never delete unrelated sources. Empty/absent
    sources return zero counts. Source deletion must not race ingestion.
    """
    with factory() as session:
        with session.begin():
            source = _target(session, board_token, employer_name)
            counts = _counts(session, source)
            if not commit or source is None:
                return counts
            source_id = source.id
            employer_id = source.employer_id
            post_ids = select(Posting.id).where(Posting.source_id == source_id)
            run_ids = select(IngestionRun.id).where(IngestionRun.source_id == source_id)
            # Delete children first; the schema does not define cascading deletes.
            session.execute(delete(PostingObservation).where(
                (PostingObservation.posting_id.in_(post_ids))
                | (PostingObservation.ingestion_run_id.in_(run_ids))
            ))
            session.execute(delete(Posting).where(Posting.source_id == source_id))
            session.execute(delete(IngestionRun).where(IngestionRun.source_id == source_id))
            session.execute(delete(Source).where(Source.id == source_id))
            # Avoid removing an employer still used by another board.
            still_used = session.scalar(select(Source.id).where(Source.employer_id == employer_id).limit(1))
            if still_used is None:
                session.execute(delete(Employer).where(Employer.id == employer_id))
        return counts
