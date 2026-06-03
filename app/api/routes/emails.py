from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.email import Email
from app.schemas.attachment import AttachmentResponse
from app.schemas.common import PaginatedResponse
from app.schemas.email import EmailListResponse, EmailResponse

router = APIRouter(prefix="/emails", tags=["emails"])


def _with_download_url(att) -> dict:
    data = AttachmentResponse.model_validate(att).model_dump()
    data["download_url"] = f"{settings.BASE_URL}/api/attachments/{att.id}/download"
    return data


@router.get("", response_model=PaginatedResponse[EmailListResponse])
async def list_emails(
    sender_email: Optional[str] = Query(default=None),
    subject: Optional[str] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if sender_email:
        filters.append(Email.sender_email.ilike(f"%{sender_email}%"))
    if subject:
        filters.append(Email.subject.ilike(f"%{subject}%"))
    if date_from:
        filters.append(Email.received_at >= date_from)
    if date_to:
        filters.append(Email.received_at <= date_to)

    base_q = select(Email)
    if filters:
        base_q = base_q.where(and_(*filters))

    total = (
        await db.execute(select(func.count()).select_from(base_q.subquery()))
    ).scalar_one()

    rows = (
        await db.execute(
            base_q.order_by(Email.received_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()

    return PaginatedResponse(
        items=[EmailListResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        size=size,
        pages=max(1, (total + size - 1) // size),
    )


@router.get("/{email_id}")
async def get_email(email_id: int, db: AsyncSession = Depends(get_db)):
    em = await db.get(Email, email_id)
    if not em:
        raise HTTPException(status_code=404, detail="Email not found")

    data = EmailResponse.model_validate(em).model_dump()
    data["attachments"] = [_with_download_url(a) for a in em.attachments]
    return data
