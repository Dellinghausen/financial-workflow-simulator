"""Create the payments table.

Revision ID: 20261006_01
Revises:
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261006_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_minor > 0", name="ck_payments_amount_positive"),
        sa.CheckConstraint(
            "currency IN ('BRL', 'EUR', 'GBP', 'USD')",
            name="ck_payments_currency_supported",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'FAILED')",
            name="ck_payments_status_valid",
        ),
        sa.CheckConstraint("version >= 0", name="ck_payments_version_non_negative"),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name="ck_payments_timestamps_monotonic",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_payments"),
    )
    op.create_index(
        "ix_payments_status_created_at",
        "payments",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_payments_status_created_at", table_name="payments")
    op.drop_table("payments")

