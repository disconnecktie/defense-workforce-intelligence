"""Record safe rejected-record summaries and elapsed ingestion time.

Revision ID: 0003_ingestion_run_metrics
Revises: 0002_observation_snapshots

Historical runs retain NULL for these new optional fields.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_ingestion_run_metrics"
down_revision = "0002_observation_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ingestion_runs", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column("ingestion_runs", sa.Column("rejection_reasons", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("ingestion_runs", "rejection_reasons")
    op.drop_column("ingestion_runs", "duration_ms")
