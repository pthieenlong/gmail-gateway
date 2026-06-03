from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email_id: int
    filename: str
    filepath: str
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    checksum: Optional[str] = None
    created_at: datetime
    download_url: Optional[str] = None
