from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from financial_workflow.domain import (
    Currency,
    DomainInvariantError,
    InvalidPaymentTransitionError,
    Money,
    Payment,
    PaymentStatus,
)

PAYMENT_ID = UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a121")
CREATED_AT = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def build_payment() -> Payment:
    return Payment.create(
        payment_id=PAYMENT_ID,
        money=Money(amount_minor=12_345, currency=Currency.USD),
        now=CREATED_AT,
    )


def test_new_payment_is_pending() -> None:
    payment = build_payment()

    assert payment.id == PAYMENT_ID
    assert payment.money == Money(amount_minor=12_345, currency=Currency.USD)
    assert payment.status is PaymentStatus.PENDING
    assert payment.created_at == CREATED_AT
    assert payment.updated_at == CREATED_AT
    assert payment.version == 0


@pytest.mark.parametrize("terminal_status", [PaymentStatus.SUCCEEDED, PaymentStatus.FAILED])
def test_payment_follows_a_valid_terminal_path(terminal_status: PaymentStatus) -> None:
    payment = build_payment()
    processing_at = CREATED_AT + timedelta(seconds=1)
    terminal_at = CREATED_AT + timedelta(seconds=2)

    payment.start_processing(now=processing_at)
    if terminal_status is PaymentStatus.SUCCEEDED:
        payment.mark_succeeded(now=terminal_at)
    else:
        payment.mark_failed(now=terminal_at)

    assert payment.status is terminal_status
    assert payment.updated_at == terminal_at
    assert payment.version == 2


@pytest.mark.parametrize(
    ("initial_status", "action", "target_status"),
    [
        (PaymentStatus.PENDING, "succeed", PaymentStatus.SUCCEEDED),
        (PaymentStatus.PENDING, "fail", PaymentStatus.FAILED),
        (PaymentStatus.PROCESSING, "process", PaymentStatus.PROCESSING),
        (PaymentStatus.SUCCEEDED, "fail", PaymentStatus.FAILED),
        (PaymentStatus.FAILED, "process", PaymentStatus.PROCESSING),
    ],
)
def test_payment_rejects_invalid_transitions(
    initial_status: PaymentStatus,
    action: str,
    target_status: PaymentStatus,
) -> None:
    payment = Payment.rehydrate(
        payment_id=PAYMENT_ID,
        money=Money(amount_minor=500, currency=Currency.EUR),
        status=initial_status,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
        version=3,
    )
    actions = {
        "process": payment.start_processing,
        "succeed": payment.mark_succeeded,
        "fail": payment.mark_failed,
    }

    with pytest.raises(InvalidPaymentTransitionError) as captured:
        actions[action](now=CREATED_AT + timedelta(seconds=1))

    assert captured.value.payment_id == PAYMENT_ID
    assert captured.value.current == initial_status
    assert captured.value.target == target_status
    assert payment.status is initial_status
    assert payment.version == 3


@pytest.mark.parametrize(
    "invalid_timestamp",
    [
        datetime(2026, 10, 1, 12, 0),
        datetime(2026, 10, 1, 9, 0, tzinfo=timezone(timedelta(hours=-3))),
    ],
)
def test_payment_requires_utc_timestamps(invalid_timestamp: datetime) -> None:
    with pytest.raises(DomainInvariantError, match="must be timezone-aware UTC"):
        Payment.create(
            payment_id=PAYMENT_ID,
            money=Money(amount_minor=500, currency=Currency.GBP),
            now=invalid_timestamp,
        )


def test_payment_rejects_a_transition_timestamp_before_its_last_update() -> None:
    payment = build_payment()
    payment.start_processing(now=CREATED_AT + timedelta(seconds=2))

    with pytest.raises(DomainInvariantError, match="cannot move backwards"):
        payment.mark_succeeded(now=CREATED_AT + timedelta(seconds=1))

    assert payment.status is PaymentStatus.PROCESSING
    assert payment.version == 1


def test_rehydration_rechecks_persisted_invariants() -> None:
    with pytest.raises(DomainInvariantError, match="cannot precede"):
        Payment.rehydrate(
            payment_id=PAYMENT_ID,
            money=Money(amount_minor=500, currency=Currency.BRL),
            status=PaymentStatus.PROCESSING,
            created_at=CREATED_AT,
            updated_at=CREATED_AT - timedelta(seconds=1),
            version=1,
        )

    with pytest.raises(DomainInvariantError, match="cannot be negative"):
        Payment.rehydrate(
            payment_id=PAYMENT_ID,
            money=Money(amount_minor=500, currency=Currency.BRL),
            status=PaymentStatus.PENDING,
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
            version=-1,
        )
