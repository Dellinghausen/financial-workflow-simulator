"""SQLAlchemy persistence models."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared metadata for application-owned tables."""


class PaymentRecord(Base):
    """Persistence representation of the payment aggregate."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_payments_amount_positive"),
        CheckConstraint(
            "currency IN ('BRL', 'EUR', 'GBP', 'USD')",
            name="ck_payments_currency_supported",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'FAILED')",
            name="ck_payments_status_valid",
        ),
        CheckConstraint("version >= 0", name="ck_payments_version_non_negative"),
        CheckConstraint(
            "updated_at >= created_at",
            name="ck_payments_timestamps_monotonic",
        ),
        Index("ix_payments_status_created_at", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(16))
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IdempotencyRecord(Base):
    """A durable reservation connecting one request key to one payment."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        CheckConstraint(
            "char_length(request_fingerprint) = 64",
            name="ck_idempotency_keys_fingerprint_length",
        ),
        UniqueConstraint("payment_id", name="uq_idempotency_keys_payment_id"),
    )

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    payment_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey(
            "payments.id",
            name="fk_idempotency_keys_payment_id_payments",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

