"""Fictional provider webhook endpoint."""

from datetime import datetime
from hashlib import sha256
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, ValidationError

from financial_workflow.application.webhooks import (
    ProviderEvent,
    ProviderEventConflictError,
    ProviderEventStatus,
    ProviderWebhookHandler,
    WebhookAuthenticationError,
    WebhookVerifier,
)
from financial_workflow.domain import DomainInvariantError


class ProviderWebhookPayload(BaseModel):
    event_id: UUID
    payment_id: UUID
    status: ProviderEventStatus
    occurred_at: datetime


class ProviderWebhookResponse(BaseModel):
    event_id: UUID
    payment_id: UUID
    payment_status: str
    duplicate: bool


def build_webhook_router(handler: ProviderWebhookHandler, verifier: WebhookVerifier) -> APIRouter:
    router = APIRouter(prefix="/webhooks", tags=["webhooks"])

    @router.post("/provider", response_model=ProviderWebhookResponse)
    async def receive_provider_webhook(
        request: Request,
        signature: Annotated[str, Header(alias="X-Provider-Signature")],
        timestamp: Annotated[int, Header(alias="X-Provider-Timestamp")],
    ) -> ProviderWebhookResponse:
        body = await request.body()
        try:
            verifier.verify(body, timestamp=timestamp, signature=signature)
            parsed = ProviderWebhookPayload.model_validate_json(body)
        except WebhookAuthenticationError as error:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
        except ValidationError as error:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid payload"
            ) from error

        try:
            result = handler.execute(
                ProviderEvent(
                    event_id=parsed.event_id,
                    payment_id=parsed.payment_id,
                    status=parsed.status,
                    occurred_at=parsed.occurred_at,
                    payload=parsed.model_dump(mode="json"),
                    payload_hash=sha256(body).hexdigest(),
                )
            )
        except ProviderEventConflictError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error
        except DomainInvariantError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error
        return ProviderWebhookResponse(
            event_id=result.event_id,
            payment_id=result.payment_id,
            payment_status=result.payment_status,
            duplicate=result.duplicate,
        )

    return router
