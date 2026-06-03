from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.webhook_delivery import WebhookDelivery
from app.schemas.webhook_delivery import WebhookDeliveryResponse
from app.services.webhook_dispatcher import WebhookDispatcher

router = APIRouter(prefix="/webhook-deliveries", tags=["webhook-deliveries"])
_dispatcher = WebhookDispatcher()


@router.get("")
async def list_deliveries(
    webhook_id: int | None = Query(default=None),
    email_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = select(WebhookDelivery).order_by(WebhookDelivery.created_at.desc())
    if webhook_id is not None:
        q = q.where(WebhookDelivery.webhook_id == webhook_id)
    if email_id is not None:
        q = q.where(WebhookDelivery.email_id == email_id)
    if status:
        q = q.where(WebhookDelivery.status == status)

    rows = (
        await db.execute(q.offset((page - 1) * size).limit(size))
    ).scalars().all()
    return [WebhookDeliveryResponse.model_validate(d) for d in rows]


@router.get("/{delivery_id}", response_model=WebhookDeliveryResponse)
async def get_delivery(delivery_id: int, db: AsyncSession = Depends(get_db)):
    d = await db.get(WebhookDelivery, delivery_id)
    if not d:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return WebhookDeliveryResponse.model_validate(d)


@router.post("/{delivery_id}/retry")
async def retry_delivery(delivery_id: int, db: AsyncSession = Depends(get_db)):
    delivery = await _dispatcher.retry_delivery(db, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return {"id": delivery.id, "status": delivery.status, "attempt_count": delivery.attempt_count}
