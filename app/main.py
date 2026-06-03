import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import attachments, emails, operations, webhook_deliveries, webhooks
from app.services.email_poller import start_polling, start_retry_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    poll_task = asyncio.create_task(start_polling(), name="email-poller")
    retry_task = asyncio.create_task(start_retry_worker(), name="retry-worker")
    logger.info("Email Gateway started")
    try:
        yield
    finally:
        poll_task.cancel()
        retry_task.cancel()
        await asyncio.gather(poll_task, retry_task, return_exceptions=True)
        logger.info("Email Gateway stopped")


app = FastAPI(
    title="Email Ingestion Gateway",
    description=(
        "Receives emails, stores attachments, and notifies downstream systems "
        "via webhooks. Acts as an Email Gateway and File Delivery Platform."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api"
app.include_router(emails.router, prefix=PREFIX)
app.include_router(attachments.router, prefix=PREFIX)
app.include_router(webhooks.router, prefix=PREFIX)
app.include_router(webhook_deliveries.router, prefix=PREFIX)
app.include_router(operations.router, prefix=PREFIX)
