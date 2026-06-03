import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.attachment import Attachment
from app.models.email import Email
from app.models.webhook import Webhook
from app.models.webhook_delivery import WebhookDelivery

logger = logging.getLogger(__name__)

# Delay in seconds before each attempt (index = attempt_count after increment)
# attempt 1 → immediate, attempt 2 → +60s, attempt 3 → +300s, attempt 4 → +900s
_RETRY_DELAYS = [0, 60, 300, 900]
_MAX_ATTEMPTS = len(_RETRY_DELAYS)


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _build_payload(em: Email, attachments: List[Attachment]) -> bytes:
    data = {
        "event": "email.received",
        "email_id": em.id,
        "message_id": em.message_id,
        "sender_email": em.sender_email,
        "subject": em.subject,
        "received_at": em.received_at.isoformat() if em.received_at else None,
        "attachments": [
            {
                "id": a.id,
                "filename": a.filename,
                "mime_type": a.mime_type,
                "file_size": a.file_size,
                "download_url": (
                    f"{settings.BASE_URL}/api/attachments/{a.id}/download"
                ),
            }
            for a in attachments
        ],
    }
    return json.dumps(data).encode()


class WebhookDispatcher:
    # ── Public API ────────────────────────────────────────────────────────────

    async def dispatch_for_email(
        self,
        db: AsyncSession,
        em: Email,
        attachments: List[Attachment],
    ) -> None:
        result = await db.execute(select(Webhook).where(Webhook.active.is_(True)))
        webhooks = result.scalars().all()

        for webhook in webhooks:
            delivery = WebhookDelivery(
                webhook_id=webhook.id,
                email_id=em.id,
                status="pending",
                attempt_count=0,
            )
            db.add(delivery)
            await db.flush()
            await self._attempt(db, delivery, webhook, em, attachments)

        await db.commit()

    async def retry_pending(self, session_maker) -> None:
        """Called by the background retry worker every N seconds."""
        now = datetime.now(timezone.utc)
        async with session_maker() as db:
            res = await db.execute(
                select(WebhookDelivery)
                .join(Webhook, WebhookDelivery.webhook_id == Webhook.id)
                .where(
                    WebhookDelivery.status == "retrying",
                    WebhookDelivery.next_retry_at <= now,
                    Webhook.active.is_(True),
                )
            )
            deliveries = res.scalars().all()
            for delivery in deliveries:
                webhook = await db.get(Webhook, delivery.webhook_id)
                em = await db.get(Email, delivery.email_id)
                if not webhook or not em:
                    delivery.status = "failed"
                    continue
                atts_res = await db.execute(
                    select(Attachment).where(Attachment.email_id == em.id)
                )
                atts = atts_res.scalars().all()
                await self._attempt(db, delivery, webhook, em, atts)
            await db.commit()

    async def retry_delivery(
        self, db: AsyncSession, delivery_id: int
    ) -> Optional[WebhookDelivery]:
        """Manual retry triggered via the API."""
        delivery = await db.get(WebhookDelivery, delivery_id)
        if not delivery:
            return None
        webhook = await db.get(Webhook, delivery.webhook_id)
        em = await db.get(Email, delivery.email_id)
        if not webhook or not em:
            return None
        atts_res = await db.execute(
            select(Attachment).where(Attachment.email_id == em.id)
        )
        atts = atts_res.scalars().all()

        # Reset counters so the retry loop can run again
        delivery.status = "pending"
        delivery.attempt_count = 0

        await self._attempt(db, delivery, webhook, em, atts)
        await db.commit()
        return delivery

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _attempt(
        self,
        db: AsyncSession,
        delivery: WebhookDelivery,
        webhook: Webhook,
        em: Email,
        attachments: List[Attachment],
    ) -> None:
        payload = _build_payload(em, attachments)
        signature = _sign(webhook.secret, payload)

        delivery.attempt_count += 1
        delivery.last_attempt_at = datetime.now(timezone.utc)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook.url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Signature": f"sha256={signature}",
                        "X-Email-Gateway-Event": "email.received",
                    },
                    timeout=aiohttp.ClientTimeout(
                        total=settings.WEBHOOK_TIMEOUT_SECONDS
                    ),
                ) as resp:
                    body = (await resp.text())[:2000]
                    delivery.response_code = resp.status
                    delivery.response_body = body

                    if 200 <= resp.status < 300:
                        delivery.status = "success"
                        logger.info(
                            "Webhook %d → email %d: HTTP %d",
                            webhook.id, em.id, resp.status,
                        )
                    elif resp.status >= 500:
                        self._schedule_retry(delivery)
                    else:
                        # 4xx: don't retry
                        delivery.status = "failed"
                        logger.warning(
                            "Webhook %d → email %d: HTTP %d (no retry)",
                            webhook.id, em.id, resp.status,
                        )

        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            delivery.response_body = str(exc)[:2000]
            logger.warning("Webhook %d network error: %s", webhook.id, exc)
            self._schedule_retry(delivery)

    def _schedule_retry(self, delivery: WebhookDelivery) -> None:
        if delivery.attempt_count >= _MAX_ATTEMPTS:
            delivery.status = "failed"
            delivery.next_retry_at = None
            logger.error(
                "Delivery %d permanently failed after %d attempts",
                delivery.id, delivery.attempt_count,
            )
        else:
            delay = _RETRY_DELAYS[delivery.attempt_count]
            delivery.status = "retrying"
            delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            logger.info(
                "Delivery %d scheduled for retry in %ds (attempt %d)",
                delivery.id, delay, delivery.attempt_count + 1,
            )
