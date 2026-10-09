from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from financial_workflow.application import (
    CreatePaymentCommand,
    CreatePaymentResult,
    IdempotencyConflictError,
)
from financial_workflow.domain import Currency, Money, Payment
from financial_workflow.main import create_app

PAYMENT_ID = UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a121")
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def payment_result(*, replayed: bool) -> CreatePaymentResult:
    return CreatePaymentResult(
        payment=Payment.create(
            payment_id=PAYMENT_ID,
            money=Money(12_345, Currency.USD),
            now=NOW,
        ),
        replayed=replayed,
    )


class StubHandler:
    def __init__(self, result: CreatePaymentResult) -> None:
        self.result = result
        self.command: CreatePaymentCommand | None = None

    def execute(self, command: CreatePaymentCommand) -> CreatePaymentResult:
        self.command = command
        return self.result


class ConflictingHandler:
    def execute(self, command: CreatePaymentCommand) -> CreatePaymentResult:
        raise IdempotencyConflictError(command.idempotency_key)


@pytest.mark.parametrize("replayed", [False, True])
def test_create_payment_returns_resource_and_replay_metadata(replayed: bool) -> None:
    handler = StubHandler(payment_result(replayed=replayed))
    client = TestClient(
        create_app(readiness_check=lambda: True, payment_handler=handler)
    )

    response = client.post(
        "/payments",
        headers={"Idempotency-Key": "checkout-123"},
        json={"amount_minor": 12_345, "currency": "USD"},
    )

    assert response.status_code == 201
    assert response.headers["Idempotent-Replayed"] == str(replayed).lower()
    assert response.headers["Location"] == f"/payments/{PAYMENT_ID}"
    assert response.json() == {
        "id": str(PAYMENT_ID),
        "amount_minor": 12_345,
        "currency": "USD",
        "status": "PENDING",
        "created_at": "2026-10-07T12:00:00Z",
        "updated_at": "2026-10-07T12:00:00Z",
        "version": 0,
    }
    assert handler.command == CreatePaymentCommand(
        idempotency_key="checkout-123",
        amount_minor=12_345,
        currency=Currency.USD,
    )


def test_reusing_key_for_different_request_returns_conflict() -> None:
    client = TestClient(
        create_app(readiness_check=lambda: True, payment_handler=ConflictingHandler())
    )

    response = client.post(
        "/payments",
        headers={"Idempotency-Key": "checkout-123"},
        json={"amount_minor": 999, "currency": "EUR"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Idempotency key was already used with a different request"
    }


@pytest.mark.parametrize(
    ("headers", "payload"),
    [
        ({}, {"amount_minor": 100, "currency": "USD"}),
        ({"Idempotency-Key": "invalid key"}, {"amount_minor": 100, "currency": "USD"}),
        ({"Idempotency-Key": "valid"}, {"amount_minor": 0, "currency": "USD"}),
        ({"Idempotency-Key": "valid"}, {"amount_minor": 100, "currency": "CAD"}),
        (
            {"Idempotency-Key": "valid"},
            {
                "amount_minor": 100,
                "currency": "USD",
                "provider_scenario": "RANDOM",
            },
        ),
    ],
)
def test_create_payment_rejects_invalid_input(
    headers: dict[str, str], payload: dict[str, object]
) -> None:
    handler = StubHandler(payment_result(replayed=False))
    client = TestClient(
        create_app(readiness_check=lambda: True, payment_handler=handler)
    )

    response = client.post("/payments", headers=headers, json=payload)

    assert response.status_code == 422
    assert handler.command is None

