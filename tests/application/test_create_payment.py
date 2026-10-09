from datetime import UTC, datetime
from uuid import UUID

from financial_workflow.application import (
    CreatePaymentCommand,
    CreatePaymentResult,
    CreatePaymentService,
    ProviderScenario,
)
from financial_workflow.domain import Currency, PaymentStatus

PAYMENT_ID = UUID("018f47d2-a97c-7f18-bb5c-d53f8b86a121")
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


class RecordingRepository:
    def __init__(self) -> None:
        self.payment_id = PAYMENT_ID
        self.idempotency_key = ""
        self.request_fingerprint = ""

    def create_idempotent(
        self,
        *,
        payment: object,
        idempotency_key: str,
        request_fingerprint: str,
        provider_scenario: ProviderScenario,
    ) -> CreatePaymentResult:
        from financial_workflow.domain import Payment

        assert isinstance(payment, Payment)
        self.payment_id = payment.id
        self.idempotency_key = idempotency_key
        self.request_fingerprint = request_fingerprint
        self.provider_scenario = provider_scenario
        return CreatePaymentResult(payment=payment, replayed=False)


def test_create_payment_builds_pending_aggregate_and_stable_fingerprint() -> None:
    repository = RecordingRepository()
    service = CreatePaymentService(
        repository,
        id_factory=lambda: PAYMENT_ID,
        clock=lambda: NOW,
    )

    result = service.execute(
        CreatePaymentCommand(
            idempotency_key="checkout-123",
            amount_minor=12_345,
            currency=Currency.USD,
        )
    )

    assert result.payment.id == PAYMENT_ID
    assert result.payment.status is PaymentStatus.PENDING
    assert result.payment.created_at == NOW
    assert repository.idempotency_key == "checkout-123"
    assert repository.request_fingerprint == (
        "49deef905d2ca493a6eb2b734f4608fbae2f1d018bbb3914c6c7d4b443dbd19e"
    )
    assert repository.provider_scenario is ProviderScenario.SUCCESS

