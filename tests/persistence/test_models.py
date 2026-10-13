from sqlalchemy import CheckConstraint, CreateTable
from sqlalchemy.dialects import postgresql

from financial_workflow.persistence import (
    LedgerAccountRecord,
    LedgerEntryRecord,
    LedgerTransactionRecord,
    PaymentRecord,
)


def test_payment_table_contains_named_financial_invariants() -> None:
    constraints = {
        constraint.name
        for constraint in PaymentRecord.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert constraints == {
        "ck_payments_amount_positive",
        "ck_payments_currency_supported",
        "ck_payments_status_valid",
        "ck_payments_timestamps_monotonic",
        "ck_payments_version_non_negative",
    }


def test_payment_table_uses_postgresql_types_and_expected_nullability() -> None:
    table = PaymentRecord.__table__
    compiled = str(CreateTable(table).compile(dialect=postgresql.dialect()))

    assert "UUID NOT NULL" in compiled
    assert "amount_minor BIGINT NOT NULL" in compiled
    assert "created_at TIMESTAMP WITH TIME ZONE NOT NULL" in compiled
    assert all(not column.nullable for column in table.columns)
    assert {index.name for index in table.indexes} == {"ix_payments_status_created_at"}


def test_ledger_tables_expose_structural_accounting_constraints() -> None:
    account_constraints = {
        constraint.name
        for constraint in LedgerAccountRecord.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    entry_constraints = {
        constraint.name
        for constraint in LedgerEntryRecord.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert account_constraints == {"ck_ledger_accounts_type_valid"}
    assert entry_constraints == {
        "ck_ledger_entries_amount_positive",
        "ck_ledger_entries_direction_valid",
    }
    assert {index.name for index in LedgerTransactionRecord.__table__.indexes} == {
        "ix_ledger_transactions_occurred_at"
    }
