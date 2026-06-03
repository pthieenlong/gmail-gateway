import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.attachment import Attachment
from app.models.email import Email
from app.services.attachment_storage import AttachmentStorageService
from app.services.webhook_dispatcher import WebhookDispatcher

logger = logging.getLogger(__name__)

# ── Shared state (read by /api/crawl/status) ──────────────────────────────────
poll_state: Dict[str, Any] = {
    "is_running": False,
    "last_run_at": None,
    "last_run_status": "never_run",
    "emails_processed_last_run": 0,
    "total_emails_processed": 0,
    "last_error": None,
}

# Set this event to trigger an immediate poll (POST /api/crawl)
crawl_trigger = asyncio.Event()


# ── Email processing ──────────────────────────────────────────────────────────

async def _process_one(
    db: AsyncSession,
    email_data: Dict[str, Any],
    storage: AttachmentStorageService,
    dispatcher: WebhookDispatcher,
) -> bool:
    """Persist a single email and its attachments, then fire webhooks.
    Returns True if a new record was created."""

    # Idempotency guard
    existing = await db.execute(
        select(Email).where(Email.message_id == email_data["message_id"])
    )
    if existing.scalar_one_or_none():
        logger.debug("Skipping duplicate message_id: %s", email_data["message_id"])
        return False

    em = Email(
        message_id=email_data["message_id"],
        sender_email=email_data["sender_email"],
        sender_name=email_data.get("sender_name"),
        recipient_email=email_data["recipient_email"],
        subject=email_data.get("subject"),
        body=email_data.get("body"),
        received_at=email_data.get("received_at"),
    )
    db.add(em)
    await db.flush()  # Assign ID before we need it for file paths

    saved_attachments: List[Attachment] = []
    for att in email_data.get("attachments", []):
        if not storage.is_allowed(att["filename"]):
            logger.info("Skipping disallowed attachment: %s", att["filename"])
            continue
        stored = await storage.save(em.id, att["filename"], att["content"])
        record = Attachment(
            email_id=em.id,
            filename=stored["filename"],
            filepath=stored["filepath"],
            mime_type=att.get("mime_type"),
            file_size=stored["file_size"],
            checksum=stored["checksum"],
        )
        db.add(record)
        saved_attachments.append(record)

    em.processed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(em)
    for a in saved_attachments:
        await db.refresh(a)

    logger.info(
        "Saved email id=%d from=%s subject='%s' attachments=%d",
        em.id, em.sender_email, em.subject, len(saved_attachments),
    )

    await dispatcher.dispatch_for_email(db, em, saved_attachments)
    return True


# ── Poll cycle ────────────────────────────────────────────────────────────────

async def run_one_cycle(
    storage: AttachmentStorageService,
    dispatcher: WebhookDispatcher,
) -> int:
    if settings.EMAIL_PROVIDER == "gmail":
        from app.services.email_fetcher import GmailAPIFetcher as Fetcher
    else:
        from app.services.email_fetcher import IMAPEmailFetcher as Fetcher

    fetcher = Fetcher()
    try:
        emails = await fetcher.fetch_unread_emails()
    finally:
        fetcher.close()

    processed = 0
    for email_data in emails:
        async with async_session() as db:
            try:
                if await _process_one(db, email_data, storage, dispatcher):
                    processed += 1
            except Exception as exc:
                logger.error("Error processing email: %s", exc, exc_info=True)
                await db.rollback()

    return processed


# ── Background tasks ──────────────────────────────────────────────────────────

async def start_polling() -> None:
    storage = AttachmentStorageService()
    dispatcher = WebhookDispatcher()

    logger.info(
        "Email poller started (interval=%ds, provider=%s)",
        settings.POLL_INTERVAL_SECONDS, settings.EMAIL_PROVIDER,
    )

    while True:
        poll_state["is_running"] = True
        poll_state["last_run_at"] = datetime.now(timezone.utc).isoformat()

        try:
            count = await run_one_cycle(storage, dispatcher)
            poll_state["emails_processed_last_run"] = count
            poll_state["total_emails_processed"] += count
            poll_state["last_run_status"] = "success"
            poll_state["last_error"] = None
        except Exception as exc:
            logger.error("Poll cycle failed: %s", exc, exc_info=True)
            poll_state["last_run_status"] = "error"
            poll_state["last_error"] = str(exc)
        finally:
            poll_state["is_running"] = False

        # Wait for the next scheduled interval OR an immediate trigger
        try:
            await asyncio.wait_for(
                crawl_trigger.wait(),
                timeout=settings.POLL_INTERVAL_SECONDS,
            )
            crawl_trigger.clear()
            logger.info("Manual crawl triggered via API")
        except asyncio.TimeoutError:
            pass


async def start_retry_worker() -> None:
    dispatcher = WebhookDispatcher()
    logger.info("Webhook retry worker started (checks every 10s)")

    while True:
        await asyncio.sleep(10)
        try:
            await dispatcher.retry_pending(async_session)
        except Exception as exc:
            logger.error("Retry worker error: %s", exc, exc_info=True)
