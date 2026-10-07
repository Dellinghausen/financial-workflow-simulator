from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from financial_workflow.application import (
    CreatePaymentCommand,
    CreatePaymentService,
    IdempotencyConflictError,
)
from financial_workflow.config import get_settings
from financial_workflow.database import build_engine
from financial_workflow.domain import Currency
from financial_workflow.persistence.models import IdempotencyRecord, PaymentRecord
from financial_workflow.persistence.repositories import PostgreSQLPaymentRepository

pytestmark = pytest.mark.integration

PAYMENT_ID = UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a121")
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def test_postgresql_enforces_idempotent_payment_creation() -> None:
    engine = build_engine(get_settings().database_url)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as session:
        session.execute(delete(IdempotencyRecord))
        session.execute(delete(PaymentRecord))

    service = CreatePaymentService(
        PostgreSQLPaymentRepository(sessions),
        id_factory=lambda: PAYMENT_ID,
        clock=lambda: NOW,
    )
    command = CreatePaymentCommand("checkout-123", 500, Currency.BRL)

    first = service.execute(command)
    replay = service.execute(command)

    assert first.replayed is False
    assert replay.replayed is True
    assert replay.payment.id == first.payment.id

    with pytest.raises(IdempotencyConflictError):
        service.execute(CreatePaymentCommand("checkout-123", 501, Currency.BRL))

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(PaymentRecord)) == 1
        assert session.scalar(select(func.count()).select_from(IdempotencyRecord)) == 1
    engine.dispose()

