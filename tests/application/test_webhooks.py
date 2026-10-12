from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import new

import pytest

from financial_workflow.application.webhooks import (
    WebhookAuthenticationError,
    WebhookVerifier,
)

NOW = datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
BODY = b'{"event_id":"example"}'
SECRET = "test-secret"  # noqa: S105 - intentionally public test fixture


def signature(timestamp: int) -> str:
    return new(SECRET.encode(), f"{timestamp}.".encode() + BODY, sha256).hexdigest()


def test_verifier_accepts_a_valid_signature_inside_replay_window() -> None:
    timestamp = int(NOW.timestamp())
    verifier = WebhookVerifier(SECRET, clock=lambda: NOW)

    verifier.verify(BODY, timestamp=timestamp, signature=signature(timestamp))


def test_verifier_rejects_an_invalid_signature() -> None:
    verifier = WebhookVerifier(SECRET, clock=lambda: NOW)

    with pytest.raises(WebhookAuthenticationError, match="signature is invalid"):
        verifier.verify(BODY, timestamp=int(NOW.timestamp()), signature="invalid")


@pytest.mark.parametrize("offset", [-301, 301])
def test_verifier_rejects_timestamps_outside_replay_window(offset: int) -> None:
    timestamp = int((NOW + timedelta(seconds=offset)).timestamp())
    verifier = WebhookVerifier(SECRET, clock=lambda: NOW)

    with pytest.raises(WebhookAuthenticationError, match="outside the allowed window"):
        verifier.verify(BODY, timestamp=timestamp, signature=signature(timestamp))
