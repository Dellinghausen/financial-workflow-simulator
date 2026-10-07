"""PostgreSQL repository implementations."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from financial_workflow.application import (
    CreatePaymentResult,
    IdempotencyConflictError,
)
from financial_workflow.domain import Currency, Money, Payment, PaymentStatus
from financial_workflow.persistence.models import IdempotencyRecord, PaymentRecord


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

