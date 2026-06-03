from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_api_key
from app.database import get_db
from app.models.webhook import Webhook
from app.schemas.webhook import WebhookCreate, WebhookResponse, WebhookUpdate

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("", status_code=201, dependencies=[Depends(require_api_key)])
async def create_webhook(body: WebhookCreate, db: AsyncSession = Depends(get_db)):
    wh = Webhook(**body.model_dump())
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    return {"id": wh.id, "status": "created"}


@router.get("", dependencies=[Depends(require_api_key)])
async def list_webhooks(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(Webhook).order_by(Webhook.created_at.desc()))
    ).scalars().all()
    return [WebhookResponse.model_validate(w) for w in rows]


@router.get("/{webhook_id}", response_model=WebhookResponse,
            dependencies=[Depends(require_api_key)])
async def get_webhook(webhook_id: int, db: AsyncSession = Depends(get_db)):
    wh = await db.get(Webhook, webhook_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return WebhookResponse.model_validate(wh)


@router.put("/{webhook_id}", response_model=WebhookResponse,
            dependencies=[Depends(require_api_key)])
async def update_webhook(
    webhook_id: int, body: WebhookUpdate, db: AsyncSession = Depends(get_db)
):
    wh = await db.get(Webhook, webhook_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(wh, field, value)
    await db.commit()
    await db.refresh(wh)
    return WebhookResponse.model_validate(wh)


@router.delete("/{webhook_id}", status_code=204,
               dependencies=[Depends(require_api_key)])
async def delete_webhook(webhook_id: int, db: AsyncSession = Depends(get_db)):
    wh = await db.get(Webhook, webhook_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await db.delete(wh)
    await db.commit()
