# Hướng dẫn sử dụng — Email Ingestion Gateway

> Tài liệu này dành cho người vận hành hệ thống sau khi đã deploy thành công.  
> Giả sử endpoint đang chạy tại `http://localhost:8000` (thay bằng domain thật nếu deploy lên server).

---

## Mục lục

1. [Kiến trúc tổng quan](#1-kiến-trúc-tổng-quan)
2. [Cấu hình lần đầu (First-time setup)](#2-cấu-hình-lần-đầu)
3. [Đăng ký hộp thư hệ thống](#3-đăng-ký-hộp-thư-hệ-thống)
4. [Đăng ký Webhook](#4-đăng-ký-webhook)
5. [Khách hàng gửi email như thế nào](#5-khách-hàng-gửi-email)
6. [Theo dõi email đã nhận](#6-theo-dõi-email-đã-nhận)
7. [Tải file đính kèm](#7-tải-file-đính-kèm)
8. [Quản lý Webhook Deliveries](#8-quản-lý-webhook-deliveries)
9. [Vận hành hàng ngày](#9-vận-hành-hàng-ngày)
10. [Xử lý sự cố](#10-xử-lý-sự-cố)
11. [Toàn bộ API Reference](#11-toàn-bộ-api-reference)

---

## 1. Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────────────────┐
│  Khách hàng gửi email tới:  inbox@your-platform.com            │
└────────────────────────────┬────────────────────────────────────┘
                             │ (IMAP poll mỗi 30 giây)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Email Gateway (FastAPI)                      │
│                                                                 │
│   1. Đọc email mới từ hộp thư                                  │
│   2. Lưu metadata vào PostgreSQL                               │
│   3. Tải attachment → lưu vào storage/email_{id}/              │
│   4. Gửi webhook đến các hệ thống đăng ký                      │
└──────────┬─────────────────┬───────────────────────────────────┘
           │                 │
           ▼                 ▼
    PostgreSQL          Local Storage
    (metadata)          (files)
           │
           ▼ Webhook POST
┌──────────────────────────────┐
│   Hệ thống của khách hàng   │
│   (OCR / ERP / AI / ETL)    │
│                              │
│   → Nhận webhook event       │
│   → Gọi GET /attachments/    │
│     {id}/download            │
│   → Xử lý file               │
└──────────────────────────────┘
```

**Luồng hoàn chỉnh:**

```
Email gửi đến  →  Platform poll  →  Lưu DB + file  →  Webhook fired
      ↑                                                      ↓
  Khách hàng                                         OCR system nhận
                                                     → tải file về
                                                     → xử lý nội dung
```

---

## 2. Cấu hình lần đầu

### Bước 1 — Tạo file `.env`

```bash
cp .env.example .env
```

Mở `.env` và điền đầy đủ:

```bash
# ─── URL công khai của platform ───────────────────────────────────────────────
# QUAN TRỌNG: BASE_URL phải là địa chỉ mà hệ thống downstream có thể gọi được
# để tải file. Nếu deploy lên server thật, đổi thành domain của bạn.
BASE_URL=https://email-gateway.company.com

# ─── Database ─────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/email_gateway

# ─── Hộp thư hệ thống ─────────────────────────────────────────────────────────
EMAIL_PROVIDER=imap                         # hoặc "gmail" nếu dùng Gmail API
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USERNAME=inbox.myplatform@gmail.com    # địa chỉ hộp thư hệ thống
IMAP_PASSWORD=abcd efgh ijkl mnop           # Gmail App Password (16 ký tự)

# ─── Lưu trữ file ─────────────────────────────────────────────────────────────
STORAGE_PATH=/app/storage

# ─── Polling ──────────────────────────────────────────────────────────────────
POLL_INTERVAL_SECONDS=30                    # kiểm tra hộp thư mỗi N giây

# ─── Webhook ──────────────────────────────────────────────────────────────────
WEBHOOK_TIMEOUT_SECONDS=30
```

### Bước 2 — Khởi động

```bash
docker compose up --build -d
```

Kiểm tra hệ thống đã sẵn sàng:

```bash
curl http://localhost:8000/api/health
# Kết quả mong đợi:
# {"status": "ok"}
```

Xem logs realtime:

```bash
docker compose logs -f app
```

---

## 3. Đăng ký hộp thư hệ thống

Hệ thống cần **một Gmail (hoặc email bất kỳ) riêng** để nhận email từ khách hàng.

### Gmail — Thiết lập App Password (khuyến nghị cho PoC)

| Bước | Thao tác |
|------|----------|
| 1 | Tạo Gmail account mới, ví dụ `inbox.myplatform@gmail.com` |
| 2 | Bật 2-Step Verification: **Account → Security → 2-Step Verification** |
| 3 | Tạo App Password: **Security → App passwords → Create** → copy 16 ký tự |
| 4 | Bật IMAP: **Gmail Settings → Forwarding and POP/IMAP → Enable IMAP** |
| 5 | Điền vào `.env`: `IMAP_USERNAME` và `IMAP_PASSWORD` |

> **Địa chỉ này chính là nơi khách hàng sẽ gửi email vào.**  
> Ví dụ: thông báo cho khách hàng "Vui lòng gửi hóa đơn tới inbox.myplatform@gmail.com"

---

## 4. Đăng ký Webhook

Webhook là cơ chế platform **chủ động thông báo** tới hệ thống của bạn mỗi khi có email mới.

### Đăng ký một webhook

```bash
curl -X POST http://localhost:8000/api/webhooks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "OCR System Production",
    "url": "https://ocr.company.com/webhook/email-intake",
    "secret": "chon-mot-chuoi-bi-mat-du-manh"
  }'
```

**Kết quả:**
```json
{"id": 1, "status": "created"}
```

### Các thao tác quản lý webhook

```bash
# Xem tất cả webhook đã đăng ký
curl http://localhost:8000/api/webhooks

# Xem chi tiết một webhook
curl http://localhost:8000/api/webhooks/1

# Tắt webhook (không xóa, chỉ dừng gửi)
curl -X PUT http://localhost:8000/api/webhooks/1 \
  -H "Content-Type: application/json" \
  -d '{"active": false}'

# Đổi URL webhook
curl -X PUT http://localhost:8000/api/webhooks/1 \
  -H "Content-Type: application/json" \
  -d '{"url": "https://new-url.company.com/hook"}'

# Xóa webhook
curl -X DELETE http://localhost:8000/api/webhooks/1
```

### Có thể đăng ký nhiều webhook cùng lúc

```bash
# Webhook 1: Hệ thống OCR
curl -X POST http://localhost:8000/api/webhooks \
  -H "Content-Type: application/json" \
  -d '{"name": "OCR System", "url": "https://ocr.company.com/hook", "secret": "secret-ocr"}'

# Webhook 2: Hệ thống ERP
curl -X POST http://localhost:8000/api/webhooks \
  -H "Content-Type: application/json" \
  -d '{"name": "ERP System", "url": "https://erp.company.com/hook", "secret": "secret-erp"}'

# → Mỗi email mới sẽ gửi notification tới CẢ HAI hệ thống trên
```

---

## 5. Khách hàng gửi email

Không cần làm gì thêm ở phía khách hàng. Họ chỉ cần gửi email bình thường:

```
To:      inbox.myplatform@gmail.com
Subject: Hóa đơn tháng 6/2026
Body:    Kính gửi, đính kèm hóa đơn tháng 6.
Attach:  invoice_june.pdf
         contract.docx
```

**Các loại file được chấp nhận:**

| Loại | Extension |
|------|-----------|
| PDF | `.pdf` |
| Word | `.docx` |
| Excel | `.xlsx` |
| CSV | `.csv` |
| Text | `.txt` |
| ZIP | `.zip` |
| Ảnh | `.png`, `.jpg`, `.jpeg` |

Các file khác (`.exe`, `.sh`, ...) sẽ bị bỏ qua tự động.

---

## 6. Theo dõi email đã nhận

### Xem danh sách email (có phân trang)

```bash
curl "http://localhost:8000/api/emails?page=1&size=20"
```

```json
{
  "items": [
    {
      "id": 1,
      "message_id": "<abc123@mail.gmail.com>",
      "sender_email": "customer@company.com",
      "sender_name": "Nguyen Van A",
      "recipient_email": "inbox.myplatform@gmail.com",
      "subject": "Hóa đơn tháng 6",
      "received_at": "2026-06-03T10:00:00+00:00",
      "processed_at": "2026-06-03T10:00:02+00:00",
      "created_at": "2026-06-03T10:00:02+00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "size": 20,
  "pages": 1
}
```

### Lọc email theo điều kiện

```bash
# Lọc theo người gửi
curl "http://localhost:8000/api/emails?sender_email=customer@company.com"

# Lọc theo từ khóa trong tiêu đề
curl "http://localhost:8000/api/emails?subject=invoice"

# Lọc theo khoảng thời gian
curl "http://localhost:8000/api/emails?date_from=2026-06-01T00:00:00&date_to=2026-06-30T23:59:59"

# Kết hợp nhiều filter
curl "http://localhost:8000/api/emails?sender_email=company.com&subject=invoice&page=1&size=10"
```

### Xem chi tiết email + danh sách attachment

```bash
curl http://localhost:8000/api/emails/1
```

```json
{
  "id": 1,
  "sender_email": "customer@company.com",
  "subject": "Hóa đơn tháng 6",
  "body": "Kính gửi, đính kèm hóa đơn tháng 6.",
  "received_at": "2026-06-03T10:00:00+00:00",
  "attachments": [
    {
      "id": 1,
      "filename": "invoice_june.pdf",
      "mime_type": "application/pdf",
      "file_size": 102400,
      "checksum": "sha256:abc123...",
      "download_url": "http://localhost:8000/api/attachments/1/download"
    },
    {
      "id": 2,
      "filename": "contract.docx",
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "file_size": 45056,
      "download_url": "http://localhost:8000/api/attachments/2/download"
    }
  ]
}
```

---

## 7. Tải file đính kèm

### Tải bằng curl (lưu thành file local)

```bash
curl -O http://localhost:8000/api/attachments/1/download
# → tải về invoice_june.pdf

# Hoặc chỉ định tên file
curl -o my-invoice.pdf http://localhost:8000/api/attachments/1/download
```

### Tải bằng Python (phía hệ thống downstream)

```python
import requests

def download_attachment(attachment_id: int, save_path: str):
    url = f"http://localhost:8000/api/attachments/{attachment_id}/download"
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)

download_attachment(1, "/tmp/invoice_june.pdf")
```

### Tải bằng Node.js

```javascript
const fs = require("fs");
const https = require("https");

function downloadAttachment(attachmentId, savePath) {
  const file = fs.createWriteStream(savePath);
  https.get(
    `http://localhost:8000/api/attachments/${attachmentId}/download`,
    (res) => res.pipe(file)
  );
}

downloadAttachment(1, "/tmp/invoice_june.pdf");
```

---

## 8. Quản lý Webhook Deliveries

Mỗi lần platform gửi webhook là một **Delivery record** — có thể theo dõi và retry.

### Xem tất cả delivery

```bash
curl http://localhost:8000/api/webhook-deliveries
```

**Status có thể là:**

| Status | Ý nghĩa |
|--------|---------|
| `pending` | Đang xử lý lần đầu |
| `success` | Gửi thành công (HTTP 2xx) |
| `retrying` | Thất bại, đang chờ retry |
| `failed` | Thất bại sau 4 lần thử |

### Lọc delivery

```bash
# Chỉ xem các delivery thất bại
curl "http://localhost:8000/api/webhook-deliveries?status=failed"

# Delivery của một webhook cụ thể
curl "http://localhost:8000/api/webhook-deliveries?webhook_id=1"

# Delivery của một email cụ thể
curl "http://localhost:8000/api/webhook-deliveries?email_id=5"
```

### Xem chi tiết một delivery

```bash
curl http://localhost:8000/api/webhook-deliveries/1
```

```json
{
  "id": 1,
  "webhook_id": 1,
  "email_id": 1,
  "status": "failed",
  "attempt_count": 4,
  "response_code": 503,
  "response_body": "Service Unavailable",
  "last_attempt_at": "2026-06-03T10:15:00+00:00",
  "next_retry_at": null,
  "created_at": "2026-06-03T10:00:02+00:00"
}
```

### Retry thủ công

```bash
# Khi hệ thống downstream đã hoạt động trở lại, retry thủ công
curl -X POST http://localhost:8000/api/webhook-deliveries/1/retry
```

```json
{"id": 1, "status": "success", "attempt_count": 5}
```

---

## 9. Vận hành hàng ngày

### Kiểm tra hệ thống đang chạy

```bash
# Health check
curl http://localhost:8000/api/health

# Trạng thái polling
curl http://localhost:8000/api/crawl/status
```

```json
{
  "is_running": false,
  "last_run_at": "2026-06-03T10:30:00+00:00",
  "last_run_status": "success",
  "emails_processed_last_run": 3,
  "total_emails_processed": 47,
  "last_error": null
}
```

### Trigger poll thủ công (không chờ 30 giây)

```bash
curl -X POST http://localhost:8000/api/crawl
# → {"status": "triggered", "message": "Email crawl has been triggered"}
```

Hữu ích khi:
- Vừa nhận được email quan trọng, muốn xử lý ngay
- Test hệ thống
- Sau khi fix lỗi muốn reprocess

### Xem logs

```bash
# Logs realtime
docker compose logs -f app

# 100 dòng gần nhất
docker compose logs --tail=100 app

# Lọc logs lỗi
docker compose logs app 2>&1 | grep ERROR
```

### Các thông báo log quan trọng

```
# Email xử lý thành công
INFO  Saved email id=5 from=customer@company.com subject='Invoice' attachments=2

# Webhook gửi thành công
INFO  Webhook 1 → email 5: HTTP 200

# Webhook thất bại, sẽ retry
WARNING  Webhook 1 network error: Connection refused

# Delivery bị retry
INFO  Delivery 3 scheduled for retry in 60s (attempt 2)

# Delivery thất bại hẳn
ERROR  Delivery 3 permanently failed after 4 attempts

# Lỗi kết nối IMAP
ERROR  IMAP error: [SSL: CERTIFICATE_VERIFY_FAILED]
```

### Khởi động lại sau lỗi

```bash
# Restart chỉ app (không restart DB)
docker compose restart app

# Rebuild và restart toàn bộ
docker compose up --build -d
```

---

## 10. Xử lý sự cố

### Hệ thống không nhận email mới

**Kiểm tra:**
```bash
# 1. Xem poll status
curl http://localhost:8000/api/crawl/status
# Nếu last_run_status = "error" → xem last_error

# 2. Trigger thủ công và xem logs
curl -X POST http://localhost:8000/api/crawl
docker compose logs -f app
```

**Nguyên nhân thường gặp:**

| Triệu chứng trong log | Nguyên nhân | Giải pháp |
|----------------------|-------------|-----------|
| `IMAP error: LOGIN failed` | Sai username/password | Kiểm tra lại `.env`, tạo lại App Password |
| `IMAP error: [SSL]` | Sai host/port | Kiểm tra `IMAP_HOST=imap.gmail.com`, `IMAP_PORT=993` |
| `Connection refused` | App Password bị thu hồi | Tạo App Password mới trong Google Account |
| `Less secure app` warning | Gmail block | Phải dùng App Password, không dùng password thường |

---

### Webhook không được gửi

```bash
# Kiểm tra webhook có active không
curl http://localhost:8000/api/webhooks

# Xem delivery logs
curl "http://localhost:8000/api/webhook-deliveries?status=failed"

# Xem chi tiết lỗi
curl http://localhost:8000/api/webhook-deliveries/1
# → xem response_code và response_body
```

**Nguyên nhân thường gặp:**

| response_code | Nguyên nhân | Giải pháp |
|---------------|-------------|-----------|
| `null` (timeout) | URL không reachable | Kiểm tra firewall, URL đúng chưa |
| `404` | URL sai endpoint | Sửa URL webhook |
| `401` / `403` | Auth sai | Kiểm tra hệ thống downstream |
| `500`-`503` | Downstream đang lỗi | Chờ downstream recover → retry thủ công |

---

### File attachment không được lưu

```bash
# Kiểm tra thư mục storage
ls -la storage/

# Kiểm tra quyền ghi
docker compose exec app ls -la /app/storage

# Nếu thiếu quyền
docker compose exec app chmod 755 /app/storage
```

---

### Database connection failed

```bash
# Kiểm tra postgres đang chạy
docker compose ps

# Kết nối thử vào DB
docker compose exec db psql -U postgres -d email_gateway -c "\dt"

# Reset DB (cẩn thận: xóa toàn bộ dữ liệu)
docker compose down -v
docker compose up --build -d
```

---

## 11. Toàn bộ API Reference

Base URL: `http://localhost:8000`

Interactive docs (Swagger UI): `http://localhost:8000/docs`

---

### Health & Operations

```
GET  /api/health                  Kiểm tra hệ thống sống
GET  /api/crawl/status            Trạng thái polling hiện tại
POST /api/crawl                   Trigger poll thủ công ngay lập tức
```

---

### Webhooks

```
POST   /api/webhooks              Đăng ký webhook mới
GET    /api/webhooks              Danh sách tất cả webhook
GET    /api/webhooks/{id}         Chi tiết một webhook
PUT    /api/webhooks/{id}         Cập nhật webhook (url/name/secret/active)
DELETE /api/webhooks/{id}         Xóa webhook
```

**Body cho POST/PUT:**
```json
{
  "name": "Tên hệ thống",
  "url":  "https://your-system.com/webhook",
  "secret": "shared-secret-string"
}
```

---

### Emails

```
GET  /api/emails                  Danh sách email (phân trang + filter)
GET  /api/emails/{id}             Chi tiết email + attachments

Query params:
  sender_email  string    Lọc theo email người gửi (partial match)
  subject       string    Lọc theo tiêu đề (partial match)
  date_from     datetime  ISO 8601, ví dụ: 2026-06-01T00:00:00
  date_to       datetime  ISO 8601
  page          int       Mặc định: 1
  size          int       Mặc định: 20, tối đa: 100
```

---

### Attachments

```
GET  /api/attachments             Danh sách attachment
GET  /api/attachments/{id}        Metadata của một attachment
GET  /api/attachments/{id}/download   Stream download file

Query params (cho GET /api/attachments):
  email_id  int    Lọc theo email
  page      int    Mặc định: 1
  size      int    Mặc định: 50, tối đa: 200
```

---

### Webhook Deliveries

```
GET  /api/webhook-deliveries              Lịch sử gửi webhook
GET  /api/webhook-deliveries/{id}         Chi tiết một delivery
POST /api/webhook-deliveries/{id}/retry   Retry thủ công

Query params (cho GET /api/webhook-deliveries):
  webhook_id  int     Lọc theo webhook
  email_id    int     Lọc theo email
  status      string  pending | retrying | success | failed
  page        int     Mặc định: 1
  size        int     Mặc định: 50
```

---

### Payload webhook nhận được (phía downstream)

```json
POST https://your-system.com/webhook
Headers:
  Content-Type: application/json
  X-Signature: sha256=<hmac_hex>
  X-Email-Gateway-Event: email.received

Body:
{
  "event": "email.received",
  "email_id": 1,
  "message_id": "<abc@mail.gmail.com>",
  "sender_email": "customer@company.com",
  "subject": "Hóa đơn tháng 6",
  "received_at": "2026-06-03T10:00:00+00:00",
  "attachments": [
    {
      "id": 1,
      "filename": "invoice_june.pdf",
      "mime_type": "application/pdf",
      "file_size": 102400,
      "download_url": "https://email-gateway.company.com/api/attachments/1/download"
    }
  ]
}
```

**Xác thực chữ ký tại phía receiver:**

```python
# Python
import hashlib, hmac
from fastapi import Request, HTTPException

async def verify_and_handle(request: Request, secret: str):
    body = await request.body()
    sig  = request.headers.get("X-Signature", "")
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(401, "Invalid signature")

    payload = await request.json()
    # xử lý payload...
```

```javascript
// Node.js / Express
const crypto = require("crypto");

function verify(secret, rawBody, sigHeader) {
  const expected = "sha256=" + crypto
    .createHmac("sha256", secret).update(rawBody).digest("hex");
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(sigHeader));
}
```

---

## Luồng hoàn chỉnh — ví dụ thực tế

```
1. Thông báo cho khách hàng gửi hóa đơn tới: inbox.myplatform@gmail.com

2. Khách hàng gửi:
   To: inbox.myplatform@gmail.com
   Subject: Invoice Q2 2026
   Attach: invoice.pdf

3. Platform poll sau tối đa 30s (hoặc gọi POST /api/crawl để ngay lập tức)

4. Platform tự động:
   ✅ Lưu email vào DB           → email.id = 5
   ✅ Lưu file vào disk          → storage/email_5/invoice.pdf
   ✅ Gửi webhook tới OCR system

5. OCR system nhận webhook:
   POST /webhook
   Body: {"email_id": 5, "attachments": [{"id": 9, "download_url": "..."}]}

6. OCR system gọi download:
   GET /api/attachments/9/download  →  nhận file invoice.pdf

7. OCR system thực hiện OCR → lưu kết quả vào hệ thống của họ

8. Kiểm tra kết quả:
   curl http://localhost:8000/api/emails/5
   curl http://localhost:8000/api/webhook-deliveries?email_id=5
```
