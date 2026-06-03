# Email Ingestion Gateway

A **Proof-of-Concept** Email Gateway and File Delivery Platform.

```
Mailbox → Poll → Extract Attachments → PostgreSQL → Webhook → Customer Systems
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Application                  │
│                                                         │
│  ┌─────────────┐   ┌──────────────┐   ┌─────────────┐  │
│  │ Email Poller│   │  REST API    │   │  Retry      │  │
│  │ (asyncio)   │   │  (FastAPI)   │   │  Worker     │  │
│  └──────┬──────┘   └──────┬───────┘   └──────┬──────┘  │
│         │                 │                   │         │
│  ┌──────▼─────────────────▼───────────────────▼──────┐  │
│  │              PostgreSQL  +  Local FS               │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Quick Start (Docker)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env: set IMAP_USERNAME, IMAP_PASSWORD, BASE_URL

# 2. Start everything
docker compose up --build

# 3. Open API docs
open http://localhost:8000/docs
```

The container runs `alembic upgrade head` automatically before starting the app.

---

## Local Development

```bash
# Prerequisites: Python 3.12, PostgreSQL

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start Postgres (adjust as needed)
docker run -d --name pg \
  -e POSTGRES_DB=email_gateway \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 postgres:16-alpine

# Configure
cp .env.example .env
# Edit DATABASE_URL, IMAP_* fields, BASE_URL=http://localhost:8000

# Run migrations
alembic upgrade head

# Start the app
uvicorn app.main:app --reload
```

---

## Email Provider Setup

### Option A — IMAP (default)

Works with Gmail, Outlook, Yahoo, or any IMAP server.

**Gmail:**
1. Go to **Google Account → Security → 2-Step Verification → App passwords**
2. Create an app password for "Mail"
3. Set in `.env`:
   ```
   EMAIL_PROVIDER=imap
   IMAP_HOST=imap.gmail.com
   IMAP_PORT=993
   IMAP_USERNAME=your-inbox@gmail.com
   IMAP_PASSWORD=xxxx-xxxx-xxxx-xxxx   # 16-char app password
   ```

### Option B — Gmail API (OAuth 2.0)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create project → Enable **Gmail API**
3. Create **OAuth 2.0 Client ID** (Desktop app)
4. Download `credentials.json` → place in project root
5. Set in `.env`:
   ```
   EMAIL_PROVIDER=gmail
   GMAIL_CREDENTIALS_FILE=credentials.json
   GMAIL_TOKEN_FILE=token.json
   ```
6. Run the app **locally** first — a browser tab opens for consent
7. `token.json` is saved; subsequent runs are fully automatic

> **Docker note:** Complete the OAuth flow locally first, then commit `token.json` to the Docker context (or mount it as a volume).

---

## REST API Reference

### Webhooks

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/webhooks` | Register a new webhook |
| GET | `/api/webhooks` | List all webhooks |
| GET | `/api/webhooks/{id}` | Get webhook by ID |
| PUT | `/api/webhooks/{id}` | Update webhook |
| DELETE | `/api/webhooks/{id}` | Delete webhook |

**Register a webhook:**
```bash
curl -X POST http://localhost:8000/api/webhooks \
  -H "Content-Type: application/json" \
  -d '{"name": "OCR System", "url": "https://ocr.example.com/hook", "secret": "my-secret"}'
```

### Emails

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/emails` | List emails (paginated, filterable) |
| GET | `/api/emails/{id}` | Get email with attachments |

**Query params:** `sender_email`, `subject`, `date_from`, `date_to`, `page`, `size`

### Attachments

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/attachments` | List attachments |
| GET | `/api/attachments/{id}` | Get attachment metadata |
| GET | `/api/attachments/{id}/download` | **Stream download file** |

### Webhook Deliveries

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/webhook-deliveries` | List deliveries (filter by status, webhook_id, email_id) |
| GET | `/api/webhook-deliveries/{id}` | Get delivery details |
| POST | `/api/webhook-deliveries/{id}/retry` | Manual retry |

### Operations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/crawl` | Trigger immediate email poll |
| GET | `/api/crawl/status` | Polling state |
| GET | `/api/health` | Health check |

---

## Webhook Event Payload

Sent via `POST` to each registered webhook URL after an email is processed:

```json
{
  "event": "email.received",
  "email_id": 123,
  "message_id": "<abc123@gmail.com>",
  "sender_email": "customer@company.com",
  "subject": "Invoice Q2",
  "received_at": "2026-06-03T10:00:00+00:00",
  "attachments": [
    {
      "id": 456,
      "filename": "invoice.pdf",
      "mime_type": "application/pdf",
      "file_size": 102400,
      "download_url": "http://localhost:8000/api/attachments/456/download"
    }
  ]
}
```

### Signature Verification

Every request carries an `X-Signature` header:

```
X-Signature: sha256=<hex>
```

Verify in Python (receiver side):

```python
import hashlib, hmac

def verify_signature(secret: str, body: bytes, header: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header)
```

Verify in Node.js:

```js
const crypto = require("crypto");

function verifySignature(secret, rawBody, header) {
  const expected = "sha256=" + crypto
    .createHmac("sha256", secret)
    .update(rawBody)
    .digest("hex");
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(header));
}
```

---

## Retry Policy

| Attempt | Delay from previous |
|---------|---------------------|
| 1 | Immediate |
| 2 | +1 minute |
| 3 | +5 minutes |
| 4 | +15 minutes |
| — | Mark as `failed` |

Retries happen on: network errors, timeouts, HTTP 5xx.
HTTP 4xx responses are **not** retried (permanent failure).

The retry background worker checks every **10 seconds**.

---

## Storage Layout

```
storage/
├── email_1/
│   ├── invoice.pdf
│   └── report.xlsx
├── email_2/
│   └── image.png
```

Files are **never** stored in PostgreSQL — only paths and metadata.

---

## Supported Attachment Types

`.pdf` · `.zip` · `.docx` · `.xlsx` · `.csv` · `.txt` · `.png` · `.jpg` / `.jpeg`

All other MIME types are silently skipped.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `http://localhost:8000` | Public URL (used in download links) |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async PostgreSQL DSN |
| `EMAIL_PROVIDER` | `imap` | `imap` or `gmail` |
| `IMAP_HOST` | `imap.gmail.com` | IMAP server hostname |
| `IMAP_PORT` | `993` | IMAP SSL port |
| `IMAP_USERNAME` | — | Mailbox address |
| `IMAP_PASSWORD` | — | App password |
| `GMAIL_CREDENTIALS_FILE` | `credentials.json` | OAuth2 credentials |
| `GMAIL_TOKEN_FILE` | `token.json` | OAuth2 cached token |
| `STORAGE_PATH` | `./storage` | Attachment root directory |
| `POLL_INTERVAL_SECONDS` | `30` | Background polling interval |
| `WEBHOOK_TIMEOUT_SECONDS` | `30` | Per-request webhook timeout |

---

## Database Schema

```
emails               attachments
──────               ───────────
id PK                id PK
message_id UNIQUE    email_id FK→emails.id
sender_email         filename
sender_name          filepath
recipient_email      mime_type
subject              file_size
body                 checksum
received_at          created_at
processed_at
created_at

webhooks             webhook_deliveries
────────             ──────────────────
id PK                id PK
name                 webhook_id FK→webhooks.id
url                  email_id FK→emails.id
secret               status
active               attempt_count
created_at           response_code
                     response_body
                     next_retry_at
                     last_attempt_at
                     created_at
```

---

## Production Notes

1. **HTTPS** — Put the app behind nginx or a cloud load balancer with TLS.
2. **BASE_URL** — Set to the public HTTPS domain so download URLs work externally.
3. **Storage** — For production use S3/GCS instead of local FS; swap `AttachmentStorageService`.
4. **Secrets** — Store `IMAP_PASSWORD` and webhook secrets in a secrets manager (Vault, AWS Secrets Manager).
5. **Scaling** — The polling loop is single-process; for multi-replica deployments, run the poller as a dedicated worker container (remove the `lifespan` tasks from the API replica).
6. **Monitoring** — Add Prometheus metrics to `GET /api/health` and expose `poll_state` for alerting.
7. **Migrations** — Always run `alembic upgrade head` in a pre-start hook, not in every replica.
