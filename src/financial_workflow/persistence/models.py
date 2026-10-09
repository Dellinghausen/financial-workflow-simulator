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


class JobRecord(Base):
    """A durable unit of background work with a recoverable lease."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('PROCESS_PAYMENT')",
            name="ck_jobs_kind_valid",
        ),
        CheckConstraint(
            "status IN ('READY', 'PROCESSING', 'COMPLETED', 'FAILED')",
            name="ck_jobs_status_valid",
        ),
        CheckConstraint("attempts >= 0", name="ck_jobs_attempts_non_negative"),
        Index("ix_jobs_claim", "status", "available_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, str]] = mapped_column(postgresql.JSONB)
    status: Mapped[str] = mapped_column(String(16))
    attempts: Mapped[int] = mapped_column(Integer)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(128))
    last_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

