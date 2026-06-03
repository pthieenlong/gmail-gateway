import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.attachment import Attachment
from app.models.email import Email
from app.services.attachment_storage import AttachmentStorageService
from app.services.email_poller import crawl_trigger, poll_state
from app.services.webhook_dispatcher import WebhookDispatcher

router = APIRouter(tags=["operations"])


@router.post("/crawl", summary="Trigger an immediate email poll")
async def trigger_crawl():
    crawl_trigger.set()
    return {"status": "triggered", "message": "Email crawl has been triggered"}


@router.get("/crawl/status", summary="Return current polling state")
async def crawl_status():
    return poll_state


@router.get("/health", summary="Health check")
async def health():
    return {"status": "ok"}


@router.post(
    "/dev/inject-email",
    summary="[DEV] Inject a fake email — test full flow without a real mailbox",
    tags=["dev"],
)
async def dev_inject_email(db: AsyncSession = Depends(get_db)):
    """
    Tạo một email giả kèm attachment PDF và kích hoạt toàn bộ luồng:
    lưu DB → lưu file → gửi webhook → retry nếu thất bại.
    Dùng để test khi chưa có mailbox thật.
    """
    now = datetime.now(timezone.utc)

    em = Email(
        message_id=f"test-{uuid.uuid4()}@dev.local",
        sender_email="test-customer@example.com",
        sender_name="Test Customer",
        recipient_email="inbox@platform.com",
        subject="[TEST] Invoice June 2026",
        body=(
            "Dear Platform,\n\n"
            "Please find attached our invoice for June 2026.\n\n"
            "Best regards,\nTest Customer"
        ),
        received_at=now,
        processed_at=now,
    )
    db.add(em)
    await db.flush()

    # Tạo file PDF giả
    storage = AttachmentStorageService()
    fake_pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"% Email Gateway PoC - test attachment\n"
        b"% Invoice June 2026\n"
        b"% Amount: $1,000.00\n"
    )
    stored = await storage.save(em.id, "test_invoice.pdf", fake_pdf)

    att = Attachment(
        email_id=em.id,
        filename=stored["filename"],
        filepath=stored["filepath"],
        mime_type="application/pdf",
        file_size=stored["file_size"],
        checksum=stored["checksum"],
    )
    db.add(att)
    await db.commit()
    await db.refresh(em)
    await db.refresh(att)

    dispatcher = WebhookDispatcher()
    await dispatcher.dispatch_for_email(db, em, [att])

    return {
        "message": "Test email injected — webhooks dispatched",
        "email_id": em.id,
        "attachment_id": att.id,
        "check_email": f"/api/emails/{em.id}",
        "download_file": f"/api/attachments/{att.id}/download",
        "check_deliveries": f"/api/webhook-deliveries?email_id={em.id}",
    }
