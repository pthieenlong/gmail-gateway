from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class WebhookDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    webhook_id: int
    email_id: int
    status: str
    attempt_count: int
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    last_attempt_at: Optional[datetime] = None
    created_at: datetime
