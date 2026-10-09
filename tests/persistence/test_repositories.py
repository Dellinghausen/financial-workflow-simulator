from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from financial_workflow.application import IdempotencyConflictError, ProviderScenario
from financial_workflow.domain import Currency, Money, Payment
from financial_workflow.persistence.models import IdempotencyRecord, JobRecord, PaymentRecord
from financial_workflow.persistence.repositories import (
    PostgreSQLPaymentProcessor,
    PostgreSQLPaymentRepository,
)

PAYMENT_ID = UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a121")
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
FINGERPRINT = "a" * 64


def build_payment() -> Payment:
    return Payment.create(
        payment_id=PAYMENT_ID,
        money=Money(500, Currency.BRL),
        now=NOW,
    )


def build_repository() -> tuple[PostgreSQLPaymentRepository, MagicMock]:
    sessions = MagicMock()
    session = sessions.begin.return_value.__enter__.return_value
    return PostgreSQLPaymentRepository(sessions), session


def test_repository_inserts_new_payment_after_reserving_key() -> None:
    repository, session = build_repository()
    session.execute.return_value.scalar_one_or_none.return_value = "checkout-123"

    result = repository.create_idempotent(
        payment=build_payment(),
        idempotency_key="checkout-123",
        request_fingerprint=FINGERPRINT,
        provider_scenario=ProviderScenario.RETRY_ONCE,
    )

    assert result.replayed is False
    persisted = session.add.call_args_list[0].args[0]
    assert isinstance(persisted, PaymentRecord)
    assert persisted.id == PAYMENT_ID
    job = session.add.call_args_list[1].args[0]
    assert isinstance(job, JobRecord)
    assert job.payload == {
        "payment_id": str(PAYMENT_ID),
        "provider_scenario": "RETRY_ONCE",
    }


def test_repository_replays_existing_payment() -> None:
    repository, session = build_repository()
    reservation_result = MagicMock()
    reservation_result.scalar_one_or_none.return_value = None
    existing_result = MagicMock()
    existing_result.scalar_one.return_value = IdempotencyRecord(
        key="checkout-123",
        request_fingerprint=FINGERPRINT,
        payment_id=PAYMENT_ID,
        created_at=NOW,
    )
    session.execute.side_effect = [reservation_result, existing_result]
    session.get.return_value = PaymentRecord(
        id=PAYMENT_ID,
        amount_minor=500,
        currency="BRL",
        status="PENDING",
        version=0,
        created_at=NOW,
        updated_at=NOW,
    )

    result = repository.create_idempotent(
        payment=build_payment(),
        idempotency_key="checkout-123",
        request_fingerprint=FINGERPRINT,
        provider_scenario=ProviderScenario.SUCCESS,
    )

    assert result.replayed is True
    assert result.payment.id == PAYMENT_ID
    assert result.payment.money == Money(500, Currency.BRL)


def test_repository_rejects_conflicting_payload() -> None:
    repository, session = build_repository()
    reservation_result = MagicMock()
    reservation_result.scalar_one_or_none.return_value = None
    existing_result = MagicMock()
    existing_result.scalar_one.return_value = IdempotencyRecord(
        key="checkout-123",
        request_fingerprint="b" * 64,
        payment_id=PAYMENT_ID,
        created_at=NOW,
    )
    session.execute.side_effect = [reservation_result, existing_result]

    with pytest.raises(IdempotencyConflictError):
        repository.create_idempotent(
            payment=build_payment(),
            idempotency_key="checkout-123",
            request_fingerprint=FINGERPRINT,
            provider_scenario=ProviderScenario.SUCCESS,
        )


def test_repository_detects_broken_idempotency_reference() -> None:
    repository, session = build_repository()
    reservation_result = MagicMock()
    reservation_result.scalar_one_or_none.return_value = None
    existing_result = MagicMock()
    existing_result.scalar_one.return_value = IdempotencyRecord(
        key="checkout-123",
        request_fingerprint=FINGERPRINT,
        payment_id=PAYMENT_ID,
        created_at=NOW,
    )
    session.execute.side_effect = [reservation_result, existing_result]
    session.get.return_value = None

    with pytest.raises(RuntimeError, match="missing payment"):
        repository.create_idempotent(
            payment=build_payment(),
            idempotency_key="checkout-123",
            request_fingerprint=FINGERPRINT,
            provider_scenario=ProviderScenario.SUCCESS,
        )


def test_payment_processor_moves_pending_payment_to_processing() -> None:
    sessions = MagicMock()
    session = sessions.begin.return_value.__enter__.return_value
    record = PaymentRecord(
        id=PAYMENT_ID,
        amount_minor=500,
        currency="BRL",
        status="PENDING",
        version=0,
        created_at=NOW,
        updated_at=NOW,
    )
    session.execute.return_value.scalar_one.return_value = record

    payment = PostgreSQLPaymentProcessor(sessions).start_processing(
        PAYMENT_ID, now=NOW + timedelta(seconds=1)
    )

    assert record.status == "PROCESSING"
    assert record.version == 1
    assert payment.status.value == "PROCESSING"


def test_payment_processor_is_idempotent_after_transition() -> None:
    sessions = MagicMock()
    session = sessions.begin.return_value.__enter__.return_value
    record = PaymentRecord(
        id=PAYMENT_ID,
        amount_minor=500,
        currency="BRL",
        status="PROCESSING",
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    session.execute.return_value.scalar_one.return_value = record

    payment = PostgreSQLPaymentProcessor(sessions).start_processing(PAYMENT_ID, now=NOW)

    assert record.version == 1
    assert payment.status.value == "PROCESSING"


def test_payment_processor_marks_processing_payment_failed() -> None:
    sessions = MagicMock()
    session = sessions.begin.return_value.__enter__.return_value
    record = PaymentRecord(
        id=PAYMENT_ID,
        amount_minor=500,
        currency="BRL",
        status="PROCESSING",
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    session.execute.return_value.scalar_one.return_value = record

    PostgreSQLPaymentProcessor(sessions).mark_failed(
        PAYMENT_ID, now=NOW + timedelta(seconds=1)
    )

    assert record.status == "FAILED"
    assert record.version == 2


def test_payment_processor_failure_is_idempotent() -> None:
    sessions = MagicMock()
    session = sessions.begin.return_value.__enter__.return_value
    record = PaymentRecord(
        id=PAYMENT_ID,
        amount_minor=500,
        currency="BRL",
        status="FAILED",
        version=2,
        created_at=NOW,
        updated_at=NOW,
    )
    session.execute.return_value.scalar_one.return_value = record

    PostgreSQLPaymentProcessor(sessions).mark_failed(PAYMENT_ID, now=NOW)

    assert record.version == 2

