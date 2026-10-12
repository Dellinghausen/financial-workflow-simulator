"""Add fictional provider events.

Revision ID: 20261012_01
Revises: 20261009_01
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261012_01"
down_revision: str | None = "20261009_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_status", sa.String(length=16), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_status IN ('SUCCEEDED', 'FAILED')",
            name="ck_provider_events_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name="fk_provider_events_payment_id_payments",
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_provider_events"),
    )
    op.create_index(
        "ix_provider_events_payment_id", "provider_events", ["payment_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_provider_events_payment_id", table_name="provider_events")
    op.drop_table("provider_events")
