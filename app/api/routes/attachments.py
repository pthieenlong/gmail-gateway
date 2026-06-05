from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.attachment import Attachment
from app.schemas.attachment import AttachmentResponse

router = APIRouter(prefix="/attachments", tags=["attachments"])


def _enrich(att: Attachment) -> dict:
    data = AttachmentResponse.model_validate(att).model_dump()
    data["download_url"] = f"{settings.BASE_URL}/api/attachments/{att.id}/download"
    data["view_url"] = f"{settings.BASE_URL}/api/attachments/{att.id}/view"
    return data


@router.get("")
async def list_attachments(
    email_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = select(Attachment).order_by(Attachment.created_at.desc())
    if email_id is not None:
        q = q.where(Attachment.email_id == email_id)
    rows = (await db.execute(q.offset((page - 1) * size).limit(size))).scalars().all()
    return [_enrich(a) for a in rows]


@router.get("/{attachment_id}")
async def get_attachment(attachment_id: int, db: AsyncSession = Depends(get_db)):
    att = await db.get(Attachment, attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return _enrich(att)


@router.get("/{attachment_id}/download")
async def download_attachment(
    attachment_id: int, db: AsyncSession = Depends(get_db)
):
    att = await db.get(Attachment, attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    path = Path(att.filepath)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    async def _stream():
        async with aiofiles.open(path, "rb") as f:
            while chunk := await f.read(65_536):
                yield chunk

    headers = {
        "Content-Disposition": f'attachment; filename="{att.filename}"',
    }
    if att.file_size:
        headers["Content-Length"] = str(att.file_size)

    return StreamingResponse(
        _stream(),
        media_type=att.mime_type or "application/octet-stream",
        headers=headers,
    )


@router.get("/{attachment_id}/view")
async def view_attachment(
    attachment_id: int, db: AsyncSession = Depends(get_db)
):
    att = await db.get(Attachment, attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    path = Path(att.filepath)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    async def _stream():
        async with aiofiles.open(path, "rb") as f:
            while chunk := await f.read(65_536):
                yield chunk

    headers = {
        "Content-Disposition": f'inline; filename="{att.filename}"',
    }
    if att.file_size:
        headers["Content-Length"] = str(att.file_size)

    return StreamingResponse(
        _stream(),
        media_type=att.mime_type or "application/octet-stream",
        headers=headers,
    )
