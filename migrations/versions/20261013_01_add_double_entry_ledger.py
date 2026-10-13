"""Add the double-entry ledger.

Revision ID: 20261013_01
Revises: 20261012_01
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261013_01"
down_revision: str | None = "20261012_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    accounts = op.create_table(
        "ledger_accounts",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("account_type", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "account_type IN ('ASSET', 'LIABILITY')",
            name="ck_ledger_accounts_type_valid",
        ),
        sa.PrimaryKeyConstraint("code", name="pk_ledger_accounts"),
        sa.UniqueConstraint("name", name="uq_ledger_accounts_name"),
    )
    op.bulk_insert(
        accounts,
        [
            {
                "code": "PROVIDER_RECEIVABLE",
                "name": "Provider Receivable",
                "account_type": "ASSET",
            },
            {
                "code": "MERCHANT_PAYABLE",
                "name": "Merchant Payable",
                "account_type": "LIABILITY",
            },
        ],
    )

    op.create_table(
        "ledger_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reference_type", sa.String(length=32), nullable=False),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "currency IN ('BRL', 'EUR', 'GBP', 'USD')",
            name="ck_ledger_transactions_currency_supported",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ledger_transactions"),
        sa.UniqueConstraint(
            "reference_type",
            "reference_id",
            name="uq_ledger_transactions_reference",
        ),
    )
    op.create_index(
        "ix_ledger_transactions_occurred_at",
        "ledger_transactions",
        ["occurred_at"],
        unique=False,
    )

    op.create_table(
        "ledger_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_code", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "amount_minor > 0",
            name="ck_ledger_entries_amount_positive",
        ),
        sa.CheckConstraint(
            "direction IN ('DEBIT', 'CREDIT')",
            name="ck_ledger_entries_direction_valid",
        ),
        sa.ForeignKeyConstraint(
            ["account_code"],
            ["ledger_accounts.code"],
            name="fk_ledger_entries_account_code_ledger_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["ledger_transactions.id"],
            name="fk_ledger_entries_transaction_id_ledger_transactions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ledger_entries"),
        sa.UniqueConstraint(
            "transaction_id",
            "account_code",
            "direction",
            name="uq_ledger_entries_transaction_account_direction",
        ),
    )
    op.create_index(
        "ix_ledger_entries_account_code",
        "ledger_entries",
        ["account_code"],
        unique=False,
    )
    op.execute(
        """
        CREATE FUNCTION enforce_ledger_transaction_balanced()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_id uuid;
            entry_count bigint;
            debit_total bigint;
            credit_total bigint;
        BEGIN
            IF TG_TABLE_NAME = 'ledger_transactions' THEN
                target_id := NEW.id;
            ELSIF TG_OP = 'DELETE' THEN
                target_id := OLD.transaction_id;
            ELSE
                target_id := NEW.transaction_id;
            END IF;

            IF EXISTS (SELECT 1 FROM ledger_transactions WHERE id = target_id) THEN
                SELECT
                    count(*),
                    coalesce(sum(amount_minor) FILTER (WHERE direction = 'DEBIT'), 0),
                    coalesce(sum(amount_minor) FILTER (WHERE direction = 'CREDIT'), 0)
                INTO entry_count, debit_total, credit_total
                FROM ledger_entries
                WHERE transaction_id = target_id;

                IF entry_count < 2 OR debit_total <> credit_total THEN
                    RAISE EXCEPTION 'ledger transaction % is not balanced', target_id
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ledger_transactions_balanced
        AFTER INSERT OR UPDATE ON ledger_transactions
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_ledger_transaction_balanced()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ledger_entries_balanced
        AFTER INSERT OR UPDATE OR DELETE ON ledger_entries
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_ledger_transaction_balanced()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER ledger_entries_balanced ON ledger_entries")
    op.execute("DROP TRIGGER ledger_transactions_balanced ON ledger_transactions")
    op.execute("DROP FUNCTION enforce_ledger_transaction_balanced()")
    op.drop_index("ix_ledger_entries_account_code", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index(
        "ix_ledger_transactions_occurred_at",
        table_name="ledger_transactions",
    )
    op.drop_table("ledger_transactions")
    op.drop_table("ledger_accounts")
