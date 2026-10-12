import json
from datetime import UTC, datetime
from hashlib import sha256
from hmac import new
from uuid import UUID

from fastapi.testclient import TestClient

from financial_workflow.application import CreatePaymentCommand, CreatePaymentResult
from financial_workflow.application.webhooks import (
    ProviderEvent,
    ProviderEventConflictError,
    ProviderEventResult,
    WebhookVerifier,
)
from financial_workflow.main import create_app

EVENT_ID = UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a122")
PAYMENT_ID = UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a121")
NOW = datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
TIMESTAMP = int(NOW.timestamp())
SECRET = "test-secret"  # noqa: S105 - intentionally public test fixture
PAYLOAD = {
    "event_id": str(EVENT_ID),
    "payment_id": str(PAYMENT_ID),
    "status": "SUCCEEDED",
    "occurred_at": "2026-10-12T14:59:30Z",
}


class UnusedPaymentHandler:
    def execute(self, command: CreatePaymentCommand) -> CreatePaymentResult:
        raise AssertionError(f"Unexpected payment command: {command}")


class StubWebhookHandler:
    def __init__(self, *, duplicate: bool = False) -> None:
        self.duplicate = duplicate
        self.event: ProviderEvent | None = None

    def execute(self, event: ProviderEvent) -> ProviderEventResult:
        self.event = event
        return ProviderEventResult(
            event.event_id,
            event.payment_id,
            "SUCCEEDED",
            self.duplicate,
        )


class ConflictingWebhookHandler:
    def execute(self, event: ProviderEvent) -> ProviderEventResult:
        raise ProviderEventConflictError("Provider event ID was reused with a different payload")


def signed_request(
    handler: StubWebhookHandler | ConflictingWebhookHandler,
    payload: dict[str, str] = PAYLOAD,
) -> tuple[TestClient, bytes, dict[str, str]]:
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = new(SECRET.encode(), f"{TIMESTAMP}.".encode() + body, sha256).hexdigest()
    app = create_app(
        readiness_check=lambda: True,
        payment_handler=UnusedPaymentHandler(),
        webhook_handler=handler,
        webhook_verifier=WebhookVerifier(SECRET, clock=lambda: NOW),
    )
    return (
        TestClient(app),
        body,
        {
            "Content-Type": "application/json",
            "X-Provider-Timestamp": str(TIMESTAMP),
            "X-Provider-Signature": signature,
        },
    )


def test_signed_webhook_is_processed() -> None:
    handler = StubWebhookHandler()
    client, body, headers = signed_request(handler)

    response = client.post("/webhooks/provider", content=body, headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "event_id": str(EVENT_ID),
        "payment_id": str(PAYMENT_ID),
        "payment_status": "SUCCEEDED",
        "duplicate": False,
    }
    assert handler.event is not None
    assert handler.event.payload_hash == sha256(body).hexdigest()


def test_duplicate_webhook_reports_replay() -> None:
    client, body, headers = signed_request(StubWebhookHandler(duplicate=True))

    response = client.post("/webhooks/provider", content=body, headers=headers)

    assert response.status_code == 200
    assert response.json()["duplicate"] is True


def test_webhook_rejects_invalid_signature_before_parsing() -> None:
    handler = StubWebhookHandler()
    client, _, headers = signed_request(handler)
    headers["X-Provider-Signature"] = "invalid"

    response = client.post("/webhooks/provider", content=b"not-json", headers=headers)

    assert response.status_code == 401
    assert handler.event is None


def test_webhook_rejects_invalid_payload_after_authentication() -> None:
    handler = StubWebhookHandler()
    client, body, headers = signed_request(handler, {"event_id": str(EVENT_ID)})

    response = client.post("/webhooks/provider", content=body, headers=headers)

    assert response.status_code == 422
    assert handler.event is None


def test_webhook_reports_conflicting_event_id() -> None:
    client, body, headers = signed_request(ConflictingWebhookHandler())

    response = client.post("/webhooks/provider", content=body, headers=headers)

    assert response.status_code == 409
    assert response.json() == {"detail": "Provider event ID was reused with a different payload"}
