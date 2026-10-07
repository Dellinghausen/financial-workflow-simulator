"""Payment application services and persistence ports."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol
from uuid import UUID, uuid4

from financial_workflow.domain import Currency, Money, Payment


class IdempotencyConflictError(ValueError):
    """An idempotency key was reused with a different request."""


@dataclass(frozen=True, slots=True)
class CreatePaymentCommand:
    idempotency_key: str
    amount_minor: int
    currency: Currency


@dataclass(frozen=True, slots=True)
class CreatePaymentResult:
    payment: Payment
    replayed: bool


class PaymentRepository(Protocol):
    """Persistence operations required by payment use cases."""

    def create_idempotent(
        self,
        *,
        payment: Payment,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> CreatePaymentResult: ...


class CreatePaymentHandler(Protocol):
    def execute(self, command: CreatePaymentCommand) -> CreatePaymentResult: ...


class CreatePaymentService:
    """Create a payment through an idempotent repository transaction."""

    def __init__(
        self,
        repository: PaymentRepository,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._id_factory = id_factory
        self._clock = clock

    def execute(self, command: CreatePaymentCommand) -> CreatePaymentResult:
        fingerprint = sha256(
            f"{command.amount_minor}:{command.currency.value}".encode()
        ).hexdigest()
        payment = Payment.create(
            payment_id=self._id_factory(),
            money=Money(command.amount_minor, command.currency),
            now=self._clock(),
        )
        return self._repository.create_idempotent(
            payment=payment,
            idempotency_key=command.idempotency_key,
            request_fingerprint=fingerprint,
        )

