"""Payment HTTP endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response, status
from pydantic import BaseModel, Field

from financial_workflow.application import (
    CreatePaymentCommand,
    CreatePaymentHandler,
    IdempotencyConflictError,
    ProviderScenario,
)
from financial_workflow.domain import Currency, Payment

IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
]


class CreatePaymentRequest(BaseModel):
    amount_minor: int = Field(gt=0, le=9_999_999_999)
    currency: Currency
    provider_scenario: ProviderScenario = ProviderScenario.SUCCESS


class PaymentResponse(BaseModel):
    id: UUID
    amount_minor: int
    currency: Currency
    status: str
    created_at: datetime
    updated_at: datetime
    version: int

    @classmethod
    def from_domain(cls, payment: Payment) -> "PaymentResponse":
        return cls(
            id=payment.id,
            amount_minor=payment.money.amount_minor,
            currency=payment.money.currency,
            status=payment.status.value,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
            version=payment.version,
        )


def build_payment_router(handler: CreatePaymentHandler) -> APIRouter:
    router = APIRouter(prefix="/payments", tags=["payments"])

    @router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
    def create_payment(
        request: CreatePaymentRequest,
        response: Response,
        idempotency_key: IdempotencyKey,
    ) -> PaymentResponse:
        try:
            result = handler.execute(
                CreatePaymentCommand(
                    idempotency_key=idempotency_key,
                    amount_minor=request.amount_minor,
                    currency=request.currency,
                    provider_scenario=request.provider_scenario,
                )
            )
        except IdempotencyConflictError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key was already used with a different request",
            ) from error

        response.headers["Idempotent-Replayed"] = str(result.replayed).lower()
        response.headers["Location"] = f"/payments/{result.payment.id}"
        return PaymentResponse.from_domain(result.payment)

    return router

