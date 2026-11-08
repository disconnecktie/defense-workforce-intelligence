"""Ingestion data model. Run 'alembic upgrade head' before writing data."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class Employer(Base):
    __tablename__ = "employers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)

class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("platform", "board_token", name="uq_source_platform_board"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employers.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    board_token: Mapped[str] = mapped_column(String(120), nullable=False)

class Posting(Base):
    __tablename__ = "postings"
    __table_args__ = (UniqueConstraint("source_id", "external_posting_id", name="uq_posting_source_external"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    external_posting_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_internal_job_id: Mapped[str | None] = mapped_column(String(100))
    requisition_id: Mapped[str | None] = mapped_column(String(100))
    title_raw: Mapped[str] = mapped_column(Text, nullable=False)
    location_raw: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    first_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="running")
    fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

class PostingObservation(Base):
    __tablename__ = "posting_observations"
    __table_args__ = (UniqueConstraint("posting_id", "ingestion_run_id", name="uq_posting_observation_run"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    posting_id: Mapped[int] = mapped_column(ForeignKey("postings.id"), nullable=False, index=True)
    ingestion_run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.id"), nullable=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event: Mapped[str] = mapped_column(String(20), nullable=False)
    # Immutable metadata snapshot on insert/update, absent on unchanged observations.
    # Existing pre-migration observations cannot be backfilled from hashes alone.
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
