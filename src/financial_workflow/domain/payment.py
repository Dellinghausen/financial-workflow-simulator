"""Payment aggregate and state machine."""

from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from financial_workflow.domain.errors import (
    DomainInvariantError,
    InvalidPaymentTransitionError,
)
from financial_workflow.domain.money import Money


class PaymentStatus(StrEnum):
    """Lifecycle states of a payment in the MVP."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


_ALLOWED_TRANSITIONS: dict[PaymentStatus, frozenset[PaymentStatus]] = {
    PaymentStatus.PENDING: frozenset({PaymentStatus.PROCESSING}),
    PaymentStatus.PROCESSING: frozenset(
        {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED}
    ),
    PaymentStatus.SUCCEEDED: frozenset(),
    PaymentStatus.FAILED: frozenset(),
}


class Payment:
    """Aggregate root that exclusively controls payment state changes."""

    __slots__ = (
        "_created_at",
        "_id",
        "_money",
        "_status",
        "_updated_at",
        "_version",
    )

    def __init__(
        self,
        *,
        payment_id: UUID,
        money: Money,
        status: PaymentStatus,
        created_at: datetime,
        updated_at: datetime,
        version: int,
    ) -> None:
        self._validate_timestamp(created_at, "created_at")
        self._validate_timestamp(updated_at, "updated_at")
        if updated_at < created_at:
            raise DomainInvariantError("updated_at cannot precede created_at")
        if version < 0:
            raise DomainInvariantError("Payment version cannot be negative")

        self._id = payment_id
        self._money = money
        self._status = status
        self._created_at = created_at
        self._updated_at = updated_at
        self._version = version

    @classmethod
    def create(cls, *, payment_id: UUID, money: Money, now: datetime) -> "Payment":
        """Create a new pending payment with deterministic identity and time."""
        return cls(
            payment_id=payment_id,
            money=money,
            status=PaymentStatus.PENDING,
            created_at=now,
            updated_at=now,
            version=0,
        )

    @classmethod
    def rehydrate(
        cls,
        *,
        payment_id: UUID,
        money: Money,
        status: PaymentStatus,
        created_at: datetime,
        updated_at: datetime,
        version: int,
    ) -> "Payment":
        """Reconstruct a persisted aggregate while rechecking its invariants."""
        return cls(
            payment_id=payment_id,
            money=money,
            status=status,
            created_at=created_at,
            updated_at=updated_at,
            version=version,
        )

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def money(self) -> Money:
        return self._money

    @property
    def status(self) -> PaymentStatus:
        return self._status

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def version(self) -> int:
        return self._version

    def start_processing(self, *, now: datetime) -> None:
        self._transition_to(PaymentStatus.PROCESSING, now=now)

    def mark_succeeded(self, *, now: datetime) -> None:
        self._transition_to(PaymentStatus.SUCCEEDED, now=now)

    def mark_failed(self, *, now: datetime) -> None:
        self._transition_to(PaymentStatus.FAILED, now=now)

    def _transition_to(self, target: PaymentStatus, *, now: datetime) -> None:
        self._validate_timestamp(now, "transition timestamp")
        if target not in _ALLOWED_TRANSITIONS[self._status]:
            raise InvalidPaymentTransitionError(
                payment_id=self._id,
                current=self._status,
                target=target,
            )
        if now < self._updated_at:
            raise DomainInvariantError(
                "Payment transition timestamp cannot move backwards"
            )

        self._status = target
        self._updated_at = now
        self._version += 1

    @staticmethod
    def _validate_timestamp(timestamp: datetime, field_name: str) -> None:
        if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
            raise DomainInvariantError(f"{field_name} must be timezone-aware UTC")

