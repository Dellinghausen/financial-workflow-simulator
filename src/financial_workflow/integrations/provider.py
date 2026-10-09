"""Deterministic fictional provider adapter."""

from financial_workflow.application.providers import (
    PermanentProviderError,
    ProviderScenario,
    ProviderSubmission,
    RetryableProviderError,
)
from financial_workflow.domain import Payment


class DeterministicProviderClient:
    """Produce controlled outcomes without real network or financial activity."""

    def submit(
        self,
        payment: Payment,
        *,
        scenario: ProviderScenario,
        attempt: int,
    ) -> ProviderSubmission:
        if scenario is ProviderScenario.PERMANENT_FAILURE:
            raise PermanentProviderError("fictional provider rejected the payment")
        if scenario is ProviderScenario.TIMEOUT:
            raise RetryableProviderError("fictional provider timed out")
        if scenario is ProviderScenario.RETRY_ONCE and attempt == 1:
            raise RetryableProviderError("fictional provider is temporarily unavailable")
        return ProviderSubmission(reference=f"sim_{payment.id.hex}")

