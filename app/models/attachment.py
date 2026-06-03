from sqlalchemy import Column, Integer, String, BigInteger, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(
        Integer, ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename = Column(String(500), nullable=False)
    filepath = Column(String(1000), nullable=False)
    mime_type = Column(String(255), nullable=True)
    file_size = Column(BigInteger, nullable=True)
    checksum = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    email = relationship("Email", back_populates="attachments")
