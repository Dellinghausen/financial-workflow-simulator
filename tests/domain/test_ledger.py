from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from financial_workflow.domain import (
    Currency,
    DomainInvariantError,
    EntryDirection,
    LedgerAccountCode,
    LedgerEntry,
    LedgerTransaction,
    Money,
)

TRANSACTION_ID = UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a130")
PAYMENT_ID = UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a121")
DEBIT_ID = UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a131")
CREDIT_ID = UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a132")
NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def test_successful_payment_creates_a_balanced_ledger_transaction() -> None:
    transaction = LedgerTransaction.for_successful_payment(
        transaction_id=TRANSACTION_ID,
        debit_entry_id=DEBIT_ID,
        credit_entry_id=CREDIT_ID,
        payment_id=PAYMENT_ID,
        money=Money(12_345, Currency.USD),
        occurred_at=NOW,
        created_at=NOW,
    )

    assert transaction.reference_type == "PAYMENT"
    assert transaction.reference_id == PAYMENT_ID
    assert transaction.entries == (
        LedgerEntry(
            DEBIT_ID,
            LedgerAccountCode.PROVIDER_RECEIVABLE,
            EntryDirection.DEBIT,
            Money(12_345, Currency.USD),
        ),
        LedgerEntry(
            CREDIT_ID,
            LedgerAccountCode.MERCHANT_PAYABLE,
            EntryDirection.CREDIT,
            Money(12_345, Currency.USD),
        ),
    )


def test_ledger_rejects_an_unbalanced_transaction() -> None:
    entries = (
        LedgerEntry(
            DEBIT_ID,
            LedgerAccountCode.PROVIDER_RECEIVABLE,
            EntryDirection.DEBIT,
            Money(500, Currency.BRL),
        ),
        LedgerEntry(
            CREDIT_ID,
            LedgerAccountCode.MERCHANT_PAYABLE,
            EntryDirection.CREDIT,
            Money(499, Currency.BRL),
        ),
    )

    with pytest.raises(DomainInvariantError, match="must balance"):
        LedgerTransaction(
            TRANSACTION_ID,
            "PAYMENT",
            PAYMENT_ID,
            Currency.BRL,
            entries,
            NOW,
            NOW,
        )


def test_ledger_rejects_mixed_currencies() -> None:
    entries = (
        LedgerEntry(
            DEBIT_ID,
            LedgerAccountCode.PROVIDER_RECEIVABLE,
            EntryDirection.DEBIT,
            Money(500, Currency.USD),
        ),
        LedgerEntry(
            CREDIT_ID,
            LedgerAccountCode.MERCHANT_PAYABLE,
            EntryDirection.CREDIT,
            Money(500, Currency.USD),
        ),
    )

    with pytest.raises(DomainInvariantError, match="transaction currency"):
        LedgerTransaction(
            TRANSACTION_ID,
            "PAYMENT",
            PAYMENT_ID,
            Currency.EUR,
            entries,
            NOW,
            NOW,
        )


@pytest.mark.parametrize(
    "occurred_at",
    [
        datetime(2026, 10, 13, 12, 0),
        datetime(2026, 10, 13, 9, 0, tzinfo=timezone(timedelta(hours=-3))),
    ],
)
def test_ledger_requires_utc_timestamps(occurred_at: datetime) -> None:
    with pytest.raises(DomainInvariantError, match="occurred_at must be timezone-aware UTC"):
        LedgerTransaction.for_successful_payment(
            transaction_id=TRANSACTION_ID,
            debit_entry_id=DEBIT_ID,
            credit_entry_id=CREDIT_ID,
            payment_id=PAYMENT_ID,
            money=Money(100, Currency.EUR),
            occurred_at=occurred_at,
            created_at=NOW,
        )


def test_ledger_rejects_creation_before_occurrence() -> None:
    with pytest.raises(DomainInvariantError, match="cannot precede"):
        LedgerTransaction.for_successful_payment(
            transaction_id=TRANSACTION_ID,
            debit_entry_id=DEBIT_ID,
            credit_entry_id=CREDIT_ID,
            payment_id=PAYMENT_ID,
            money=Money(100, Currency.EUR),
            occurred_at=NOW,
            created_at=NOW - timedelta(seconds=1),
        )
