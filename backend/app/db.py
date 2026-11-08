"""Database configuration for the local DWI ingestion pipeline."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

LOCAL_DATABASE_URL = "postgresql+psycopg://dwi:dwi_local_only@127.0.0.1:5432/dwi"


def database_url() -> str:
    """Require an explicit URL for non-local installations."""
    value = os.environ.get("DATABASE_URL", LOCAL_DATABASE_URL)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


def make_session_factory(url: str | None = None) -> sessionmaker[Session]:
    engine = create_engine(url or database_url(), pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False)
