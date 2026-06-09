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
    cc_emails: Optional[str] = None
    delivered_via: Optional[str] = None
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
    cc_emails: Optional[str] = None
    delivered_via: Optional[str] = None
    subject: Optional[str] = None
    received_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    created_at: datetime


class MailboxGroup(BaseModel):
    """Emails grouped by the mailbox they were scanned from (recipient_email)."""

    email: str
    data: List[EmailListResponse]
