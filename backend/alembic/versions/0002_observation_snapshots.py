"""Retain metadata snapshots on insert/update observations.

Revision ID: 0002_observation_snapshots
Revises: 0001_initial_ingestion

Existing observations remain snapshot=NULL: their prior field values cannot
be reconstructed solely from their hashes.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_observation_snapshots"
down_revision = "0001_initial_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("posting_observations", sa.Column("snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("posting_observations", "snapshot")
