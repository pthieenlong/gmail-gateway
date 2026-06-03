# API Reference — Email Ingestion Gateway

**Base URL:** `http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io`  
**Swagger UI:** `http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/docs`  
**Content-Type:** `application/json` (tất cả request/response)

---

## Mục lục

| Nhóm | Endpoints |
|------|-----------|
| [Hệ thống](#1-hệ-thống) | `GET /api/health` · `GET /api/crawl/status` · `POST /api/crawl` |
| [Emails](#2-emails) | `GET /api/emails` · `GET /api/emails/{id}` |
| [Attachments](#3-attachments) | `GET /api/attachments` · `GET /api/attachments/{id}` · `GET /api/attachments/{id}/download` |
| [Webhooks](#4-webhooks) | `POST` · `GET` · `PUT` · `DELETE /api/webhooks` |
| [Webhook Deliveries](#5-webhook-deliveries) | `GET /api/webhook-deliveries` · `POST .../retry` |

---

## 1. Hệ thống

---

### `GET /api/health`

Kiểm tra hệ thống đang chạy.

**Request:**
```bash
curl http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api/health
```

**Response `200`:**
```json
{
  "status": "ok"
}
```

---

### `GET /api/crawl/status`

Xem trạng thái của background email polling.

**Request:**
```bash
curl http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api/crawl/status
```

**Response `200`:**
```json
{
  "is_running": false,
  "last_run_at": "2026-06-03T07:57:11Z",
  "last_run_status": "success",
  "emails_processed_last_run": 1,
  "total_emails_processed": 1,
  "last_error": null
}
```

| Field | Ý nghĩa |
|-------|---------|
| `is_running` | `true` nếu đang poll ngay lúc này |
| `last_run_status` | `success` / `error` |
| `emails_processed_last_run` | Số email xử lý được lần poll gần nhất |
| `total_emails_processed` | Tổng số email đã xử lý từ khi khởi động |
| `last_error` | Mô tả lỗi nếu poll thất bại (null nếu OK) |

---

### `POST /api/crawl`

Kích hoạt poll email **ngay lập tức** — không cần chờ 30 giây.

**Dùng khi:** biết có email mới vừa gửi đến, muốn xử lý ngay.

**Request:**
```bash
curl -X POST http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api/crawl
```

**Response `200`:**
```json
{
  "status": "triggered",
  "message": "Email crawl has been triggered"
}
```

---

## 2. Emails

---

### `GET /api/emails`

Lấy danh sách email đã nhận. Hỗ trợ phân trang và lọc.

**Request:**
```bash
curl "http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api/emails"
```

**Query parameters:**

| Param | Kiểu | Ví dụ | Mô tả |
|-------|------|-------|-------|
| `sender_email` | string | `company.com` | Lọc theo email người gửi (tìm kiếm chứa) |
| `subject` | string | `invoice` | Lọc theo tiêu đề (tìm kiếm chứa) |
| `date_from` | datetime | `2026-06-01T00:00:00` | Từ ngày (ISO 8601) |
| `date_to` | datetime | `2026-06-30T23:59:59` | Đến ngày (ISO 8601) |
| `page` | int | `1` | Trang hiện tại (mặc định: 1) |
| `size` | int | `20` | Số record/trang (mặc định: 20, tối đa: 100) |

**Ví dụ lọc:**
```bash
# Lọc theo người gửi
curl "http://.../api/emails?sender_email=customer@company.com"

# Lọc theo tiêu đề
curl "http://.../api/emails?subject=invoice"

# Lọc theo ngày
curl "http://.../api/emails?date_from=2026-06-01T00:00:00&date_to=2026-06-30T23:59:59"

# Phân trang — trang 2, mỗi trang 10 email
curl "http://.../api/emails?page=2&size=10"

# Kết hợp nhiều filter
curl "http://.../api/emails?sender_email=company.com&subject=invoice&page=1&size=5"
```

**Response `200`:**
```json
{
  "items": [
    {
      "id": 1,
      "message_id": "<CA+f4+QVFh...@mail.gmail.com>",
      "sender_email": "nguyenquangk981@gmail.com",
      "sender_name": "Nguyễn Quang Khải",
      "recipient_email": "khainqk981@gmail.com",
      "subject": "Hoá đơn test",
      "received_at": "2026-06-03T07:51:03Z",
      "processed_at": "2026-06-03T07:57:11Z",
      "created_at": "2026-06-03T07:57:11Z"
    }
  ],
  "total": 1,
  "page": 1,
  "size": 20,
  "pages": 1
}
```

| Field | Ý nghĩa |
|-------|---------|
| `received_at` | Thời điểm email được gửi (từ header email) |
| `processed_at` | Thời điểm platform xử lý xong |
| `total` | Tổng số email khớp filter |
| `pages` | Tổng số trang |

---

### `GET /api/emails/{id}`

Lấy chi tiết một email, **bao gồm danh sách file đính kèm** và link download.

**Request:**
```bash
curl http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api/emails/1
```

**Response `200`:**
```json
{
  "id": 1,
  "message_id": "<CA+f4+QVFh...@mail.gmail.com>",
  "sender_email": "nguyenquangk981@gmail.com",
  "sender_name": "Nguyễn Quang Khải",
  "recipient_email": "khainqk981@gmail.com",
  "subject": "Hoá đơn test",
  "body": "Kính gửi, đính kèm hoá đơn tháng 6.",
  "received_at": "2026-06-03T07:51:03Z",
  "processed_at": "2026-06-03T07:57:11Z",
  "created_at": "2026-06-03T07:57:11Z",
  "attachments": [
    {
      "id": 1,
      "email_id": 1,
      "filename": "San Hà.pdf",
      "mime_type": "application/pdf",
      "file_size": 159504,
      "checksum": "9d60edfac8c4748336a69668a7a93a841d84f923bd8a7b473aa825373e98de60",
      "created_at": "2026-06-03T07:57:11Z",
      "download_url": "http://.../api/attachments/1/download"
    }
  ]
}
```

**Response `404`:**
```json
{
  "detail": "Email not found"
}
```

---

## 3. Attachments

---

### `GET /api/attachments`

Lấy danh sách tất cả file đính kèm.

**Request:**
```bash
curl "http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api/attachments"
```

**Query parameters:**

| Param | Kiểu | Mô tả |
|-------|------|-------|
| `email_id` | int | Lọc attachment của một email cụ thể |
| `page` | int | Trang (mặc định: 1) |
| `size` | int | Số record/trang (mặc định: 50, tối đa: 200) |

**Ví dụ:**
```bash
# Attachment của email ID 1
curl "http://.../api/attachments?email_id=1"
```

**Response `200`:**
```json
[
  {
    "id": 1,
    "email_id": 1,
    "filename": "San Hà.pdf",
    "mime_type": "application/pdf",
    "file_size": 159504,
    "checksum": "9d60edfac8c474...",
    "created_at": "2026-06-03T07:57:11Z",
    "download_url": "http://.../api/attachments/1/download"
  }
]
```

| Field | Ý nghĩa |
|-------|---------|
| `file_size` | Kích thước file tính bằng **bytes** |
| `checksum` | SHA-256 hash — dùng để verify file toàn vẹn |
| `download_url` | URL tải file trực tiếp |

---

### `GET /api/attachments/{id}`

Xem metadata của một file đính kèm.

**Request:**
```bash
curl http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api/attachments/1
```

**Response `200`:** _(giống object trong danh sách ở trên)_

---

### `GET /api/attachments/{id}/download`

**Tải file về.** Trả về binary content của file — stream trực tiếp.

**Request:**
```bash
# Tải về, tự đặt tên file
curl -O http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api/attachments/1/download

# Tải về, đặt tên cụ thể
curl -o invoice.pdf http://.../api/attachments/1/download
```

**Bằng Python:**
```python
import requests

def download_attachment(base_url: str, attachment_id: int, save_path: str):
    url = f"{base_url}/api/attachments/{attachment_id}/download"
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)

download_attachment(
    "http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io",
    attachment_id=1,
    save_path="/tmp/SanHa.pdf"
)
```

**Bằng Node.js:**
```javascript
const fs = require("fs");
const https = require("https");

function downloadAttachment(baseUrl, attachmentId, savePath) {
  const url = `${baseUrl}/api/attachments/${attachmentId}/download`;
  const file = fs.createWriteStream(savePath);
  https.get(url, (res) => res.pipe(file));
}

downloadAttachment(
  "http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io",
  1,
  "/tmp/SanHa.pdf"
);
```

**Response headers:**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="San Hà.pdf"
Content-Length: 159504
```

**Response `404`:**
```json
{ "detail": "Attachment not found" }
```

---

## 4. Webhooks

Webhook là cơ chế platform **tự động báo** cho hệ thống của bạn khi có email mới — thay vì bạn phải polling liên tục.

---

### `POST /api/webhooks`

Đăng ký một webhook mới.

**Request:**
```bash
curl -X POST http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api/webhooks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "OCR System",
    "url": "https://your-system.com/webhook/email",
    "secret": "chuoi-bi-mat-manh"
  }'
```

**Body fields:**

| Field | Bắt buộc | Mô tả |
|-------|----------|-------|
| `name` | ✓ | Tên gợi nhớ |
| `url` | ✓ | URL endpoint nhận event (phải public, HTTPS) |
| `secret` | ✓ | Chuỗi bí mật để ký request — dùng verify phía nhận |

**Response `201`:**
```json
{
  "id": 1,
  "status": "created"
}
```

---

### `GET /api/webhooks`

Danh sách tất cả webhook đã đăng ký.

**Request:**
```bash
curl http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api/webhooks
```

**Response `200`:**
```json
[
  {
    "id": 1,
    "name": "OCR System",
    "url": "https://your-system.com/webhook/email",
    "active": true,
    "created_at": "2026-06-03T07:57:11Z"
  }
]
```

> `secret` không bao giờ trả về trong response — bảo mật.

---

### `GET /api/webhooks/{id}`

Chi tiết một webhook.

```bash
curl http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api/webhooks/1
```

---

### `PUT /api/webhooks/{id}`

Cập nhật webhook — đổi URL, tắt/bật, đổi secret.

**Request:**
```bash
# Đổi URL
curl -X PUT http://.../api/webhooks/1 \
  -H "Content-Type: application/json" \
  -d '{"url": "https://new-url.company.com/hook"}'

# Tắt webhook tạm thời
curl -X PUT http://.../api/webhooks/1 \
  -H "Content-Type: application/json" \
  -d '{"active": false}'

# Đổi secret
curl -X PUT http://.../api/webhooks/1 \
  -H "Content-Type: application/json" \
  -d '{"secret": "new-secret-string"}'
```

**Body fields** _(tất cả optional — chỉ truyền field cần thay đổi)_:

| Field | Kiểu | Mô tả |
|-------|------|-------|
| `name` | string | Tên mới |
| `url` | string | URL mới |
| `secret` | string | Secret mới |
| `active` | bool | `true` = bật, `false` = tắt |

**Response `200`:** trả về webhook sau khi cập nhật.

---

### `DELETE /api/webhooks/{id}`

Xóa webhook.

```bash
curl -X DELETE http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api/webhooks/1
```

**Response `204`:** No content (xóa thành công).

---

### Payload webhook nhận được

Mỗi khi có email mới, platform gửi **POST** tới URL đã đăng ký:

```
POST https://your-system.com/webhook/email
Content-Type: application/json
X-Signature: sha256=a3f9c2...
X-Email-Gateway-Event: email.received
```

```json
{
  "event": "email.received",
  "email_id": 1,
  "message_id": "<CA+f4+QVFh...@mail.gmail.com>",
  "sender_email": "nguyenquangk981@gmail.com",
  "subject": "Hoá đơn test",
  "received_at": "2026-06-03T07:51:03Z",
  "attachments": [
    {
      "id": 1,
      "filename": "San Hà.pdf",
      "mime_type": "application/pdf",
      "file_size": 159504,
      "download_url": "http://.../api/attachments/1/download"
    }
  ]
}
```

### Xác thực chữ ký webhook (bắt buộc)

Header `X-Signature` chứa HMAC-SHA256 của toàn bộ request body, ký bằng `secret`.  
Luôn verify trước khi xử lý — tránh request giả mạo.

**Python:**
```python
import hashlib, hmac
from fastapi import Request, HTTPException

WEBHOOK_SECRET = "chuoi-bi-mat-manh"

@app.post("/webhook/email")
async def receive_email_event(request: Request):
    body = await request.body()
    sig  = request.headers.get("X-Signature", "")

    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    email_id = payload["email_id"]

    for att in payload["attachments"]:
        # Tải file từ platform về
        file_resp = requests.get(att["download_url"])
        # Lưu hoặc xử lý tiếp
        with open(att["filename"], "wb") as f:
            f.write(file_resp.content)

    return {"status": "received"}   # trả về 200 để platform đánh dấu thành công
```

**Node.js / Express:**
```javascript
const crypto = require("crypto");
const express = require("express");
const app = express();

const WEBHOOK_SECRET = "chuoi-bi-mat-manh";

app.post("/webhook/email", express.raw({ type: "application/json" }), (req, res) => {
  const sig = req.headers["x-signature"] || "";
  const expected = "sha256=" + crypto
    .createHmac("sha256", WEBHOOK_SECRET)
    .update(req.body)
    .digest("hex");

  if (!crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(sig))) {
    return res.status(401).json({ error: "Invalid signature" });
  }

  const payload = JSON.parse(req.body);
  console.log("Email received:", payload.subject);
  payload.attachments.forEach(att => {
    console.log("Download:", att.download_url);
    // fetch(att.download_url) → xử lý file
  });

  res.json({ status: "received" });
});
```

### Retry policy

| Lần thử | Thời điểm |
|---------|-----------|
| 1 | Ngay lập tức |
| 2 | +1 phút |
| 3 | +5 phút |
| 4 | +15 phút |
| Sau đó | `status: failed` |

Platform retry khi nhận HTTP 5xx hoặc timeout. HTTP 4xx = không retry.  
**Endpoint của bạn phải trả về HTTP 2xx** để delivery được đánh dấu thành công.

---

## 5. Webhook Deliveries

Mỗi lần platform gửi webhook là một delivery record — có thể theo dõi và retry thủ công.

---

### `GET /api/webhook-deliveries`

Xem lịch sử gửi webhook.

**Request:**
```bash
curl "http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api/webhook-deliveries"
```

**Query parameters:**

| Param | Mô tả |
|-------|-------|
| `status` | Lọc: `pending` / `success` / `retrying` / `failed` |
| `webhook_id` | Lọc theo webhook |
| `email_id` | Lọc theo email |
| `page` / `size` | Phân trang |

**Ví dụ:**
```bash
# Xem deliveries thất bại
curl "http://.../api/webhook-deliveries?status=failed"

# Xem deliveries của email ID 1
curl "http://.../api/webhook-deliveries?email_id=1"
```

**Response `200`:**
```json
[
  {
    "id": 1,
    "webhook_id": 1,
    "email_id": 1,
    "status": "success",
    "attempt_count": 1,
    "response_code": 200,
    "response_body": "{\"status\":\"received\"}",
    "last_attempt_at": "2026-06-03T07:57:11Z",
    "next_retry_at": null,
    "created_at": "2026-06-03T07:57:11Z"
  }
]
```

| `status` | Ý nghĩa |
|----------|---------|
| `pending` | Đang xử lý lần đầu |
| `success` | Gửi thành công |
| `retrying` | Thất bại, đang chờ retry |
| `failed` | Thất bại sau 4 lần — cần retry thủ công |

---

### `GET /api/webhook-deliveries/{id}`

Chi tiết một delivery.

```bash
curl http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api/webhook-deliveries/1
```

---

### `POST /api/webhook-deliveries/{id}/retry`

Retry thủ công một delivery thất bại.

**Dùng khi:** hệ thống downstream vừa restore lại, muốn gửi lại.

```bash
curl -X POST http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api/webhook-deliveries/1/retry
```

**Response `200`:**
```json
{
  "id": 1,
  "status": "success",
  "attempt_count": 2
}
```

---

## Luồng sử dụng theo vai trò

### Vai trò A — Hệ thống nhận file (OCR, ERP, AI...)

```
1. Đăng ký webhook một lần:
   POST /api/webhooks

2. Khi nhận POST từ platform:
   → Verify X-Signature
   → Đọc payload["attachments"]
   → GET /api/attachments/{id}/download  → xử lý file

3. Nếu delivery thất bại, retry:
   POST /api/webhook-deliveries/{id}/retry
```

### Vai trò B — Quản trị / Giám sát

```
Xem email đã nhận:     GET /api/emails?date_from=...
Xem file đính kèm:     GET /api/attachments?email_id=...
Tải file thủ công:     GET /api/attachments/{id}/download
Xem tình trạng gửi:    GET /api/webhook-deliveries?status=failed
Trigger poll ngay:     POST /api/crawl
Kiểm tra hệ thống:     GET /api/health
```

---

## Tóm tắt nhanh — Copy & Run

```bash
BASE="http://i9ontd9frpiurphdjkudw5mw.103.74.122.58.sslip.io/api"

# Health
curl $BASE/health

# Danh sách email
curl "$BASE/emails"

# Chi tiết email (kèm attachment)
curl "$BASE/emails/1"

# Danh sách file
curl "$BASE/attachments"

# Tải file
curl -O "$BASE/attachments/1/download"

# Đăng ký webhook
curl -X POST $BASE/webhooks \
  -H "Content-Type: application/json" \
  -d '{"name":"My System","url":"https://your.com/hook","secret":"my-secret"}'

# Trigger poll ngay
curl -X POST $BASE/crawl

# Xem webhook deliveries
curl "$BASE/webhook-deliveries"

# Retry delivery thất bại
curl -X POST $BASE/webhook-deliveries/1/retry
```
