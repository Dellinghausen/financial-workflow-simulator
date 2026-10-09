from datetime import UTC, datetime
from uuid import UUID

import pytest

from financial_workflow.application import (
    PermanentProviderError,
    ProviderScenario,
    RetryableProviderError,
)
from financial_workflow.domain import Currency, Money, Payment
from financial_workflow.integrations import DeterministicProviderClient

PAYMENT = Payment.create(
    payment_id=UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a121"),
    money=Money(500, Currency.USD),
    now=datetime(2026, 10, 9, 12, 0, tzinfo=UTC),
)


@pytest.mark.parametrize("scenario", [ProviderScenario.SUCCESS, ProviderScenario.RETRY_ONCE])
def test_provider_accepts_successful_scenarios(scenario: ProviderScenario) -> None:
    result = DeterministicProviderClient().submit(PAYMENT, scenario=scenario, attempt=2)

    assert result.reference == f"sim_{PAYMENT.id.hex}"


def test_provider_retry_once_fails_only_on_first_attempt() -> None:
    with pytest.raises(RetryableProviderError, match="temporarily unavailable"):
        DeterministicProviderClient().submit(
            PAYMENT,
            scenario=ProviderScenario.RETRY_ONCE,
            attempt=1,
        )


def test_provider_timeout_is_retryable() -> None:
    with pytest.raises(RetryableProviderError, match="timed out"):
        DeterministicProviderClient().submit(
            PAYMENT,
            scenario=ProviderScenario.TIMEOUT,
            attempt=1,
        )


def test_provider_permanent_failure_is_not_retryable() -> None:
    with pytest.raises(PermanentProviderError, match="rejected"):
        DeterministicProviderClient().submit(
            PAYMENT,
            scenario=ProviderScenario.PERMANENT_FAILURE,
            attempt=1,
        )
