"""PostgreSQL repository implementations."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from financial_workflow.application import (
    CreatePaymentResult,
    IdempotencyConflictError,
    ProviderScenario,
)
from financial_workflow.application.webhooks import (
    ProviderEvent,
    ProviderEventConflictError,
    ProviderEventResult,
    ProviderEventStatus,
)
from financial_workflow.domain import Currency, Money, Payment, PaymentStatus
from financial_workflow.persistence.models import (
    IdempotencyRecord,
    JobRecord,
    PaymentRecord,
    ProviderEventRecord,
)


def _to_record(payment: Payment) -> PaymentRecord:
    return PaymentRecord(
        id=payment.id,
        amount_minor=payment.money.amount_minor,
        currency=payment.money.currency.value,
        status=payment.status.value,
        version=payment.version,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
    )


def _to_domain(record: PaymentRecord) -> Payment:
    return Payment.rehydrate(
        payment_id=record.id,
        money=Money(record.amount_minor, Currency(record.currency)),
        status=PaymentStatus(record.status),
        created_at=record.created_at,
        updated_at=record.updated_at,
        version=record.version,
    )


class PostgreSQLPaymentRepository:
    """Persist payments and idempotency reservations atomically."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create_idempotent(
        self,
        *,
        payment: Payment,
        idempotency_key: str,
        request_fingerprint: str,
        provider_scenario: ProviderScenario,
    ) -> CreatePaymentResult:
        with self._sessions.begin() as session:
            reservation = session.execute(
                insert(IdempotencyRecord)
                .values(
                    key=idempotency_key,
                    request_fingerprint=request_fingerprint,
                    payment_id=payment.id,
                    created_at=payment.created_at,
                )
                .on_conflict_do_nothing(index_elements=[IdempotencyRecord.key])
                .returning(IdempotencyRecord.key)
            ).scalar_one_or_none()

            if reservation is not None:
                session.add(_to_record(payment))
                session.add(
                    JobRecord(
                        id=uuid4(),
                        kind="PROCESS_PAYMENT",
                        payload={
                            "payment_id": str(payment.id),
                            "provider_scenario": provider_scenario.value,
                        },
                        status="READY",
                        attempts=0,
                        available_at=payment.created_at,
                        locked_at=None,
                        locked_by=None,
                        last_error=None,
                        created_at=payment.created_at,
                        updated_at=payment.created_at,
                    )
                )
                return CreatePaymentResult(payment=payment, replayed=False)

            existing = session.execute(
                select(IdempotencyRecord).where(IdempotencyRecord.key == idempotency_key)
            ).scalar_one()
            if existing.request_fingerprint != request_fingerprint:
                raise IdempotencyConflictError(idempotency_key)

            payment_record = session.get(PaymentRecord, existing.payment_id)
            if payment_record is None:
                raise RuntimeError("Idempotency record references a missing payment")
            return CreatePaymentResult(payment=_to_domain(payment_record), replayed=True)


class PostgreSQLPaymentProcessor:
    """Advance payments to processing with row-level serialization."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def start_processing(self, payment_id: UUID, *, now: datetime) -> Payment:
        with self._sessions.begin() as session:
            record = session.execute(
                select(PaymentRecord).where(PaymentRecord.id == payment_id).with_for_update()
            ).scalar_one()
            payment = _to_domain(record)
            if payment.status is PaymentStatus.PROCESSING:
                return payment
            payment.start_processing(now=now)
            self._apply(record, payment)
            return payment

    def mark_failed(self, payment_id: UUID, *, now: datetime) -> None:
        with self._sessions.begin() as session:
            record = session.execute(
                select(PaymentRecord).where(PaymentRecord.id == payment_id).with_for_update()
            ).scalar_one()
            payment = _to_domain(record)
            if payment.status is PaymentStatus.FAILED:
                return
            payment.mark_failed(now=now)
            self._apply(record, payment)

    @staticmethod
    def _apply(record: PaymentRecord, payment: Payment) -> None:
        record.status = payment.status.value
        record.updated_at = payment.updated_at
        record.version = payment.version


class PostgreSQLProviderEventRepository:
    """Deduplicate and apply provider events in one transaction."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def apply(self, event: ProviderEvent, *, received_at: datetime) -> ProviderEventResult:
        with self._sessions.begin() as session:
            inserted = session.execute(
                insert(ProviderEventRecord)
                .values(
                    event_id=event.event_id,
                    payment_id=event.payment_id,
                    event_status=event.status.value,
                    payload_hash=event.payload_hash,
                    payload=event.payload,
                    occurred_at=event.occurred_at,
                    received_at=received_at,
                    processed_at=received_at,
                )
                .on_conflict_do_nothing(index_elements=[ProviderEventRecord.event_id])
                .returning(ProviderEventRecord.event_id)
            ).scalar_one_or_none()

            if inserted is None:
                existing = session.get(ProviderEventRecord, event.event_id)
                if existing is None or existing.payload_hash != event.payload_hash:
                    raise ProviderEventConflictError(
                        "Provider event ID was reused with a different payload"
                    )
                payment_record = session.get(PaymentRecord, existing.payment_id)
                if payment_record is None:
                    raise RuntimeError("Provider event references a missing payment")
                return ProviderEventResult(
                    event.event_id,
                    existing.payment_id,
                    payment_record.status,
                    True,
                )

            payment_record = session.execute(
                select(PaymentRecord).where(PaymentRecord.id == event.payment_id).with_for_update()
            ).scalar_one()
            payment = _to_domain(payment_record)
            if event.status is ProviderEventStatus.SUCCEEDED:
                payment.mark_succeeded(now=received_at)
            else:
                payment.mark_failed(now=received_at)
            PostgreSQLPaymentProcessor._apply(payment_record, payment)
            return ProviderEventResult(
                event.event_id,
                event.payment_id,
                payment.status.value,
                False,
            )
