from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class WebhookCreate(BaseModel):
    name: str
    url: str
    secret: str


class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    secret: Optional[str] = None
    active: Optional[bool] = None


class WebhookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    active: bool
    created_at: datetime
