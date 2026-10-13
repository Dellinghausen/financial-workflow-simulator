"""Double-entry ledger domain model."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from financial_workflow.domain.errors import DomainInvariantError
from financial_workflow.domain.money import Currency, Money


class LedgerAccountCode(StrEnum):
    """Stable account identifiers used by the initial chart of accounts."""

    PROVIDER_RECEIVABLE = "PROVIDER_RECEIVABLE"
    MERCHANT_PAYABLE = "MERCHANT_PAYABLE"


class EntryDirection(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    id: UUID
    account_code: LedgerAccountCode
    direction: EntryDirection
    money: Money


@dataclass(frozen=True, slots=True)
class LedgerTransaction:
    """A balanced, immutable accounting transaction."""

    id: UUID
    reference_type: str
    reference_id: UUID
    currency: Currency
    entries: tuple[LedgerEntry, ...]
    occurred_at: datetime
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.reference_type:
            raise DomainInvariantError("Ledger reference type cannot be empty")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() != timedelta(0):
            raise DomainInvariantError("Ledger occurred_at must be timezone-aware UTC")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() != timedelta(0):
            raise DomainInvariantError("Ledger created_at must be timezone-aware UTC")
        if self.created_at < self.occurred_at:
            raise DomainInvariantError("Ledger creation cannot precede occurrence")
        if len(self.entries) < 2:
            raise DomainInvariantError("Ledger transaction requires at least two entries")
        if any(entry.money.currency is not self.currency for entry in self.entries):
            raise DomainInvariantError("Ledger entries must use the transaction currency")

        debit_total = sum(
            entry.money.amount_minor
            for entry in self.entries
            if entry.direction is EntryDirection.DEBIT
        )
        credit_total = sum(
            entry.money.amount_minor
            for entry in self.entries
            if entry.direction is EntryDirection.CREDIT
        )
        if debit_total != credit_total:
            raise DomainInvariantError("Ledger transaction must balance debits and credits")

    @classmethod
    def for_successful_payment(
        cls,
        *,
        transaction_id: UUID,
        debit_entry_id: UUID,
        credit_entry_id: UUID,
        payment_id: UUID,
        money: Money,
        occurred_at: datetime,
        created_at: datetime,
    ) -> "LedgerTransaction":
        return cls(
            id=transaction_id,
            reference_type="PAYMENT",
            reference_id=payment_id,
            currency=money.currency,
            entries=(
                LedgerEntry(
                    id=debit_entry_id,
                    account_code=LedgerAccountCode.PROVIDER_RECEIVABLE,
                    direction=EntryDirection.DEBIT,
                    money=money,
                ),
                LedgerEntry(
                    id=credit_entry_id,
                    account_code=LedgerAccountCode.MERCHANT_PAYABLE,
                    direction=EntryDirection.CREDIT,
                    money=money,
                ),
            ),
            occurred_at=occurred_at,
            created_at=created_at,
        )
