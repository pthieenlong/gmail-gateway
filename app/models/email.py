from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(500), unique=True, nullable=False, index=True)
    sender_email = Column(String(255), nullable=False, index=True)
    sender_name = Column(String(255), nullable=True)
    recipient_email = Column(String(255), nullable=False)
    cc_emails = Column(Text, nullable=True)  # comma-separated CC addresses
    delivered_via = Column(String(8), nullable=True)  # "to" or "cc" for the scanned mailbox
    subject = Column(Text, nullable=True)
    body = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    attachments = relationship(
        "Attachment",
        back_populates="email",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    webhook_deliveries = relationship(
        "WebhookDelivery",
        back_populates="email",
        cascade="all, delete-orphan",
    )
