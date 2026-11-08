"""Initial relational tables for Greenhouse ingestion.

Revision ID: 0001_initial_ingestion
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_ingestion"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "employers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employer_id", sa.Integer(), sa.ForeignKey("employers.id"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("board_token", sa.String(120), nullable=False),
        sa.UniqueConstraint("platform", "board_token", name="uq_source_platform_board"),
    )
    op.create_table(
        "postings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("external_posting_id", sa.String(100), nullable=False),
        sa.Column("source_internal_job_id", sa.String(100)),
        sa.Column("requisition_id", sa.String(100)),
        sa.Column("title_raw", sa.Text(), nullable=False),
        sa.Column("location_raw", sa.Text()),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("first_published_at", sa.DateTime(timezone=True)),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("source_id", "external_posting_id", name="uq_posting_source_external"),
    )
    op.create_index("ix_postings_source_id", "postings", ["source_id"])
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("fetched", sa.Integer(), nullable=False),
        sa.Column("inserted", sa.Integer(), nullable=False),
        sa.Column("updated", sa.Integer(), nullable=False),
        sa.Column("unchanged", sa.Integer(), nullable=False),
        sa.Column("rejected", sa.Integer(), nullable=False),
        sa.Column("errors", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text()),
    )
    op.create_index("ix_ingestion_runs_source_id", "ingestion_runs", ["source_id"])
    op.create_table(
        "posting_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("posting_id", sa.Integer(), sa.ForeignKey("postings.id"), nullable=False),
        sa.Column("ingestion_run_id", sa.Integer(), sa.ForeignKey("ingestion_runs.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("event", sa.String(20), nullable=False),
        sa.UniqueConstraint("posting_id", "ingestion_run_id", name="uq_posting_observation_run"),
    )
    op.create_index("ix_posting_observations_posting_id", "posting_observations", ["posting_id"])
    op.create_index("ix_posting_observations_ingestion_run_id", "posting_observations", ["ingestion_run_id"])

def downgrade() -> None:
    op.drop_table("posting_observations")
    op.drop_table("ingestion_runs")
    op.drop_table("postings")
    op.drop_table("sources")
    op.drop_table("employers")
