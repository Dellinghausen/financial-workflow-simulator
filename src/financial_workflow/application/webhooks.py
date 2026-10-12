"""Signed provider webhook processing."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from hmac import compare_digest, new
from typing import Protocol
from uuid import UUID


class WebhookAuthenticationError(ValueError):
    """The webhook signature or timestamp is not trustworthy."""


class ProviderEventConflictError(ValueError):
    """An event identifier was reused with different content."""


class ProviderEventStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ProviderEvent:
    event_id: UUID
    payment_id: UUID
    status: ProviderEventStatus
    occurred_at: datetime
    payload: dict[str, object]
    payload_hash: str


@dataclass(frozen=True, slots=True)
class ProviderEventResult:
    event_id: UUID
    payment_id: UUID
    payment_status: str
    duplicate: bool


class ProviderEventRepository(Protocol):
    def apply(self, event: ProviderEvent, *, received_at: datetime) -> ProviderEventResult: ...


class ProviderWebhookHandler(Protocol):
    def execute(self, event: ProviderEvent) -> ProviderEventResult: ...


class WebhookVerifier:
    def __init__(
        self,
        secret: str,
        *,
        tolerance: timedelta = timedelta(minutes=5),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._secret = secret.encode()
        self._tolerance = tolerance
        self._clock = clock

    def verify(self, body: bytes, *, timestamp: int, signature: str) -> None:
        event_time = datetime.fromtimestamp(timestamp, tz=UTC)
        if abs(self._clock() - event_time) > self._tolerance:
            raise WebhookAuthenticationError("Webhook timestamp is outside the allowed window")
        signed = str(timestamp).encode() + b"." + body
        expected = new(self._secret, signed, sha256).hexdigest()
        if not compare_digest(expected, signature):
            raise WebhookAuthenticationError("Webhook signature is invalid")


class ProviderWebhookService:
    def __init__(
        self,
        repository: ProviderEventRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._clock = clock

    def execute(self, event: ProviderEvent) -> ProviderEventResult:
        return self._repository.apply(event, received_at=self._clock())
