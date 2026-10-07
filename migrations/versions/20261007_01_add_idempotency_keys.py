"""Add idempotency keys.

Revision ID: 20261007_01
Revises: 20261006_01
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261007_01"
down_revision: str | None = "20261006_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(request_fingerprint) = 64",
            name="ck_idempotency_keys_fingerprint_length",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name="fk_idempotency_keys_payment_id_payments",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.PrimaryKeyConstraint("key", name="pk_idempotency_keys"),
        sa.UniqueConstraint("payment_id", name="uq_idempotency_keys_payment_id"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")

