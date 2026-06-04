# API Response Reference

Base URL: `http://localhost:8000/api`

---

## Health & Operations

### `GET /api/health`

```json
{
  "status": "ok"
}
```

### `GET /api/crawl/status`

```json
{
  "is_running": false,
  "last_run_at": "2026-06-04T10:00:00Z",
  "last_run_status": "success",
  "emails_processed_last_run": 3,
  "total_emails_processed": 42,
  "last_error": null
}
```

### `POST /api/crawl`

```json
{
  "status": "triggered",
  "message": "Email crawl has been triggered"
}
```

### `POST /api/dev/inject-email`

```json
{
  "message": "Test email injected — webhooks dispatched",
  "email_id": 1,
  "attachment_id": 1,
  "check_email": "/api/emails/1",
  "download_file": "/api/attachments/1/download",
  "check_deliveries": "/api/webhook-deliveries?email_id=1"
}
```

---

## Emails

### `GET /api/emails` — List (paginated)

Query params: `sender_email`, `subject`, `date_from`, `date_to`, `page` (default 1), `size` (default 20, max 100)

```json
{
  "items": [
    {
      "id": 1,
      "message_id": "<abc123@mail.example.com>",
      "sender_email": "sender@example.com",
      "sender_name": "John Doe",
      "recipient_email": "inbox@platform.com",
      "subject": "Invoice June 2026",
      "received_at": "2026-06-04T09:30:00Z",
      "processed_at": "2026-06-04T09:30:05Z",
      "created_at": "2026-06-04T09:30:05Z"
    }
  ],
  "total": 84,
  "page": 1,
  "size": 20,
  "pages": 5
}
```

### `GET /api/emails/{email_id}`

```json
{
  "id": 1,
  "message_id": "<abc123@mail.example.com>",
  "sender_email": "sender@example.com",
  "sender_name": "John Doe",
  "recipient_email": "inbox@platform.com",
  "subject": "Invoice June 2026",
  "body": "Dear Platform,\n\nPlease find attached our invoice.\n\nBest regards,\nJohn",
  "received_at": "2026-06-04T09:30:00Z",
  "processed_at": "2026-06-04T09:30:05Z",
  "created_at": "2026-06-04T09:30:05Z",
  "attachments": [
    {
      "id": 1,
      "email_id": 1,
      "filename": "invoice_june_2026.pdf",
      "filepath": "storage/1/invoice_june_2026.pdf",
      "mime_type": "application/pdf",
      "file_size": 204800,
      "checksum": "sha256:e3b0c44298fc1c149afb...",
      "created_at": "2026-06-04T09:30:05Z",
      "download_url": "http://localhost:8000/api/attachments/1/download"
    }
  ]
}
```

#### 404

```json
{ "detail": "Email not found" }
```

---

## Attachments

### `GET /api/attachments` — List

Query params: `email_id`, `page` (default 1), `size` (default 50, max 200)

```json
[
  {
    "id": 1,
    "email_id": 1,
    "filename": "invoice_june_2026.pdf",
    "filepath": "storage/1/invoice_june_2026.pdf",
    "mime_type": "application/pdf",
    "file_size": 204800,
    "checksum": "sha256:e3b0c44298fc1c149afb...",
    "created_at": "2026-06-04T09:30:05Z",
    "download_url": "http://localhost:8000/api/attachments/1/download"
  }
]
```

### `GET /api/attachments/{attachment_id}`

```json
{
  "id": 1,
  "email_id": 1,
  "filename": "invoice_june_2026.pdf",
  "filepath": "storage/1/invoice_june_2026.pdf",
  "mime_type": "application/pdf",
  "file_size": 204800,
  "checksum": "sha256:e3b0c44298fc1c149afb...",
  "created_at": "2026-06-04T09:30:05Z",
  "download_url": "http://localhost:8000/api/attachments/1/download"
}
```

#### 404

```json
{ "detail": "Attachment not found" }
```

### `GET /api/attachments/{attachment_id}/download`

Returns the raw file as a binary stream.

| Header | Example |
|---|---|
| `Content-Type` | `application/pdf` |
| `Content-Disposition` | `attachment; filename="invoice_june_2026.pdf"` |
| `Content-Length` | `204800` |

#### 404 — attachment record missing

```json
{ "detail": "Attachment not found" }
```

#### 404 — file missing on disk

```json
{ "detail": "File not found on disk" }
```

---

## Webhooks

> All webhook endpoints require `X-API-Key` header.

### `POST /api/webhooks` — Create

**Request body:**

```json
{
  "name": "My Webhook",
  "url": "https://downstream.example.com/hook",
  "secret": "super-secret-token"
}
```

**Response `201`:**

```json
{
  "id": 1,
  "status": "created"
}
```

### `GET /api/webhooks` — List

```json
[
  {
    "id": 1,
    "name": "My Webhook",
    "url": "https://downstream.example.com/hook",
    "active": true,
    "created_at": "2026-06-04T08:00:00Z"
  }
]
```

### `GET /api/webhooks/{webhook_id}`

```json
{
  "id": 1,
  "name": "My Webhook",
  "url": "https://downstream.example.com/hook",
  "active": true,
  "created_at": "2026-06-04T08:00:00Z"
}
```

#### 404

```json
{ "detail": "Webhook not found" }
```

### `PUT /api/webhooks/{webhook_id}` — Update

**Request body (all fields optional):**

```json
{
  "name": "Updated Name",
  "url": "https://new-url.example.com/hook",
  "secret": "new-secret",
  "active": false
}
```

**Response `200`:**

```json
{
  "id": 1,
  "name": "Updated Name",
  "url": "https://new-url.example.com/hook",
  "active": false,
  "created_at": "2026-06-04T08:00:00Z"
}
```

#### 404

```json
{ "detail": "Webhook not found" }
```

### `DELETE /api/webhooks/{webhook_id}`

**Response `204` — no body**

#### 404

```json
{ "detail": "Webhook not found" }
```

---

## Webhook Deliveries

### `GET /api/webhook-deliveries` — List

Query params: `webhook_id`, `email_id`, `status` (`pending` / `success` / `failed`), `page` (default 1), `size` (default 50, max 200)

```json
[
  {
    "id": 1,
    "webhook_id": 1,
    "email_id": 1,
    "status": "success",
    "attempt_count": 1,
    "response_code": 200,
    "response_body": "ok",
    "next_retry_at": null,
    "last_attempt_at": "2026-06-04T09:30:10Z",
    "created_at": "2026-06-04T09:30:06Z"
  }
]
```

**Status values:** `pending` · `success` · `failed`

### `GET /api/webhook-deliveries/{delivery_id}`

```json
{
  "id": 1,
  "webhook_id": 1,
  "email_id": 1,
  "status": "failed",
  "attempt_count": 3,
  "response_code": 503,
  "response_body": "Service Unavailable",
  "next_retry_at": "2026-06-04T10:00:00Z",
  "last_attempt_at": "2026-06-04T09:45:00Z",
  "created_at": "2026-06-04T09:30:06Z"
}
```

#### 404

```json
{ "detail": "Delivery not found" }
```

### `POST /api/webhook-deliveries/{delivery_id}/retry`

```json
{
  "id": 1,
  "status": "pending",
  "attempt_count": 4
}
```

#### 404

```json
{ "detail": "Delivery not found" }
```

---

## Webhook Payload (outgoing)

Payload gửi tới downstream khi có email mới:

```json
{
  "event": "email.received",
  "email_id": 1,
  "message_id": "<abc123@mail.example.com>",
  "sender_email": "sender@example.com",
  "subject": "Invoice June 2026",
  "received_at": "2026-06-04T09:30:00Z",
  "attachments": [
    {
      "id": 1,
      "filename": "invoice_june_2026.pdf",
      "mime_type": "application/pdf",
      "file_size": 204800,
      "download_url": "http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api/attachments/1/download"
    }
  ]
}
```

---

## Common Error Responses

| Status | Body |
|---|---|
| `401` | `{ "detail": "Invalid or missing API key" }` |
| `404` | `{ "detail": "<resource> not found" }` |
| `422` | `{ "detail": [{ "loc": ["body", "url"], "msg": "field required", "type": "missing" }] }` |
