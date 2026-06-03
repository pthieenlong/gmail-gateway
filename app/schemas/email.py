from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.attachment import AttachmentResponse


class EmailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: str
    sender_email: str
    sender_name: Optional[str] = None
    recipient_email: str
    subject: Optional[str] = None
    body: Optional[str] = None
    received_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    created_at: datetime
    attachments: List[AttachmentResponse] = []


class EmailListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: str
    sender_email: str
    sender_name: Optional[str] = None
    recipient_email: str
    subject: Optional[str] = None
    received_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    created_at: datetime
