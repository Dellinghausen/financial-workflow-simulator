"""Fictional payment provider contracts."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from financial_workflow.domain import Payment


class ProviderScenario(StrEnum):
    """Deterministic outcomes available for demonstrations and tests."""

    SUCCESS = "SUCCESS"
    RETRY_ONCE = "RETRY_ONCE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"
    TIMEOUT = "TIMEOUT"


class RetryableProviderError(RuntimeError):
    """The provider call may succeed when attempted again."""


class PermanentProviderError(RuntimeError):
    """The provider rejected the payment permanently."""


@dataclass(frozen=True, slots=True)
class ProviderSubmission:
    reference: str


class ProviderClient(Protocol):
    def submit(
        self,
        payment: Payment,
        *,
        scenario: ProviderScenario,
        attempt: int,
    ) -> ProviderSubmission: ...

