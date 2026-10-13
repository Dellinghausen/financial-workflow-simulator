from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from financial_workflow.application import (
    CreatePaymentCommand,
    CreatePaymentService,
    IdempotencyConflictError,
    JobKind,
    ProcessPaymentJobHandler,
    Worker,
)
from financial_workflow.application.webhooks import (
    ProviderEvent,
    ProviderEventConflictError,
    ProviderEventStatus,
)
from financial_workflow.config import get_settings
from financial_workflow.database import build_engine
from financial_workflow.domain import Currency
from financial_workflow.integrations import DeterministicProviderClient
from financial_workflow.persistence.jobs import PostgreSQLJobQueue
from financial_workflow.persistence.models import (
    IdempotencyRecord,
    JobRecord,
    LedgerEntryRecord,
    LedgerTransactionRecord,
    PaymentRecord,
    ProviderEventRecord,
)
from financial_workflow.persistence.repositories import (
    PostgreSQLPaymentProcessor,
    PostgreSQLPaymentRepository,
    PostgreSQLProviderEventRepository,
)

pytestmark = pytest.mark.integration

PAYMENT_ID = UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a121")
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
EVENT_ID = UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a122")


def test_postgresql_enforces_idempotent_payment_creation() -> None:
    engine = build_engine(get_settings().database_url)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as session:
        session.execute(delete(LedgerEntryRecord))
        session.execute(delete(LedgerTransactionRecord))
        session.execute(delete(ProviderEventRecord))
        session.execute(delete(JobRecord))
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
        assert session.scalar(select(func.count()).select_from(JobRecord)) == 1

    worker = Worker(
        PostgreSQLJobQueue(sessions),
        {
            JobKind.PROCESS_PAYMENT: ProcessPaymentJobHandler(
                PostgreSQLPaymentProcessor(sessions),
                DeterministicProviderClient(),
            )
        },
        worker_id="integration-worker",
        clock=lambda: NOW,
    )
    assert worker.run_once() is True

    with Session(engine) as session:
        assert session.scalar(select(PaymentRecord.status)) == "PROCESSING"
        assert session.scalar(select(JobRecord.status)) == "COMPLETED"

    event = ProviderEvent(
        event_id=EVENT_ID,
        payment_id=PAYMENT_ID,
        status=ProviderEventStatus.SUCCEEDED,
        occurred_at=NOW,
        payload={"event_id": str(EVENT_ID), "status": "SUCCEEDED"},
        payload_hash="a" * 64,
    )
    event_repository = PostgreSQLProviderEventRepository(sessions)

    processed = event_repository.apply(event, received_at=NOW)
    duplicate = event_repository.apply(event, received_at=NOW)

    assert processed.payment_status == "SUCCEEDED"
    assert processed.duplicate is False
    assert duplicate.payment_status == "SUCCEEDED"
    assert duplicate.duplicate is True

    conflicting = ProviderEvent(
        event_id=EVENT_ID,
        payment_id=PAYMENT_ID,
        status=ProviderEventStatus.FAILED,
        occurred_at=NOW,
        payload={"event_id": str(EVENT_ID), "status": "FAILED"},
        payload_hash="b" * 64,
    )
    with pytest.raises(ProviderEventConflictError):
        event_repository.apply(conflicting, received_at=NOW)

    with Session(engine) as session:
        assert session.scalar(select(PaymentRecord.status)) == "SUCCEEDED"
        assert session.scalar(select(func.count()).select_from(ProviderEventRecord)) == 1
        assert session.scalar(select(func.count()).select_from(LedgerTransactionRecord)) == 1
        entries = session.scalars(select(LedgerEntryRecord)).all()
        assert len(entries) == 2
        assert sum(entry.amount_minor for entry in entries if entry.direction == "DEBIT") == sum(
            entry.amount_minor for entry in entries if entry.direction == "CREDIT"
        )

    with pytest.raises(IntegrityError), sessions.begin() as session:
        session.execute(
            update(LedgerEntryRecord)
            .where(LedgerEntryRecord.direction == "DEBIT")
            .values(amount_minor=501)
        )

    with Session(engine) as session:
        assert set(session.scalars(select(LedgerEntryRecord.amount_minor))) == {500}
    engine.dispose()
