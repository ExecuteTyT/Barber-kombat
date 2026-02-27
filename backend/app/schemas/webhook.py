"""Pydantic schemas for YClients webhook payloads."""

from pydantic import BaseModel, Field


class YClientsWebhookPayload(BaseModel):
    """Incoming YClients webhook event payload."""

    company_id: int = 0
    resource: str = ""
    status: str = ""
    data: dict = Field(default_factory=dict)


class WebhookResponse(BaseModel):
    """Response returned by the webhook endpoint."""

    ok: bool = True
