# Hướng dẫn cấu hình Gmail IMAP cho Email Gateway

Tài liệu này hướng dẫn kết nối platform với một Gmail account dùng làm hộp thư nhận.  
Khách hàng gửi email → platform tự động poll → xử lý → gửi webhook.

---

## Tổng quan

```
Khách hàng                Platform (Docker)             Hệ thống của bạn
     │                          │                              │
     │── gửi email ──────────▶  │  poll IMAP mỗi 30s          │
     │   inbox@gmail.com        │── lưu DB + file ──────────▶  │
     │                          │── POST webhook ──────────▶   │
     │                          │                              │── tải file về
     │                          │                              │── xử lý (OCR...)
```

---

## Phần 1 — Chuẩn bị Gmail account

### Bước 1 — Tạo Gmail account riêng cho hệ thống

Tạo một Gmail **mới hoàn toàn** để làm hộp thư nhận của platform.  
Không dùng Gmail cá nhân — nên đặt tên gợi nhớ vai trò, ví dụ:

```
inbox.myplatform@gmail.com
documents.intake@gmail.com
khainqk981@gmail.com          ← ví dụ trong dự án này
```

---

### Bước 2 — Bật 2-Step Verification

> **Bắt buộc.** App Password chỉ hoạt động khi 2FA đã bật.

1. Đăng nhập Gmail account vừa tạo
2. Vào: [myaccount.google.com/security](https://myaccount.google.com/security)
3. Tìm mục **"2-Step Verification"** → click vào
4. Click **"Get started"** → chọn phương thức xác minh:
   - **Google prompt** (điện thoại nhận thông báo) — dễ nhất
   - SMS về số điện thoại
   - Authenticator app
5. Làm theo hướng dẫn → **Turn On**

Kết quả: trang Security hiện **"2-Step Verification: On"**

---

### Bước 3 — Tạo App Password

> App Password là mật khẩu 16 ký tự dùng riêng cho ứng dụng — thay cho mật khẩu Gmail thật.

1. Vào thẳng link: **[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)**
2. Đăng nhập lại nếu được yêu cầu
3. Ô **"App name"**: gõ tên bất kỳ, ví dụ `email-gateway`
4. Click **"Create"**
5. Một khung vàng hiện ra với **16 ký tự**:

```
┌──────────────────────────────────────────┐
│  Your app password                       │
│                                          │
│   abcd  efgh  ijkl  mnop                │  ← copy toàn bộ
│                                          │
│  Use this instead of your password       │
│  when signing in from another app.       │
│                                          │
│                [ Done ]                  │
└──────────────────────────────────────────┘
```

6. **Copy ngay** — mật khẩu này chỉ hiện một lần duy nhất
7. Click **Done**

---

### Bước 4 — Bật IMAP trong Gmail

1. Vào Gmail của account hệ thống
2. Click **⚙️** (góc phải trên) → **"See all settings"**
3. Chọn tab **"Forwarding and POP/IMAP"**
4. Tìm mục **"IMAP access"**:

```
IMAP access:
  ○ Disable IMAP
  ● Enable IMAP        ← chọn cái này
```

5. Click **"Save Changes"** ở cuối trang

---

## Phần 2 — Cấu hình Platform

### Bước 5 — Cập nhật file `.env`

```bash
cd /home/khai/Desktop/email-gateway
```

Mở file `.env` và điền:

```bash
# ── App ───────────────────────────────────────────────────────────────────────
APP_HOST=0.0.0.0
APP_PORT=8000
BASE_URL=http://localhost:8000       # ← đổi thành domain thật khi deploy

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/email_gateway

# ── Email IMAP ────────────────────────────────────────────────────────────────
EMAIL_PROVIDER=imap
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USERNAME=khainqk981@gmail.com       # ← Gmail account hệ thống
IMAP_PASSWORD=abcd efgh ijkl mnop        # ← App Password 16 ký tự (có khoảng trắng cũng được)

# ── Storage ───────────────────────────────────────────────────────────────────
STORAGE_PATH=/app/storage

# ── Polling ───────────────────────────────────────────────────────────────────
POLL_INTERVAL_SECONDS=30

# ── Webhook ───────────────────────────────────────────────────────────────────
WEBHOOK_TIMEOUT_SECONDS=30
```

---

### Bước 6 — Khởi động platform

```bash
# Build image và start tất cả containers
docker compose up --build -d

# Xem log để kiểm tra kết nối
docker compose logs -f app
```

**Log thành công** — thấy `Poll complete`:

```
INFO  Email poller started (interval=30s, provider=imap)
INFO  Webhook retry worker started (checks every 10s)
INFO  Application startup complete.
INFO  Poll complete. Processed 0 emails.   ← inbox đang rỗng, bình thường
```

**Log thất bại** — cần kiểm tra lại:

```
# Sai App Password
ERROR  IMAP error: [AUTHENTICATIONFAILED] Invalid credentials

# Chưa bật IMAP trong Gmail settings
ERROR  IMAP error: [UNAVAILABLE] IMAP is not enabled

# Sai host/port
ERROR  IMAP error: [SSL: CERTIFICATE_VERIFY_FAILED]
```

---

## Phần 3 — Test luồng thực tế

### Bước 7 — Chạy Mock Webhook Server (Terminal 1)

Mở terminal riêng, giữ chạy trong suốt quá trình test:

```bash
cd /home/khai/Desktop/email-gateway
python3 scripts/mock_webhook_server.py
```

Output:
```
Mock Webhook Server
  Listening : http://0.0.0.0:9000
  Secret    : test-secret-123

Đăng ký webhook với URL:
  http://host.docker.internal:9000  ← từ bên trong Docker
  http://localhost:9000             ← nếu test không qua Docker

Waiting for webhooks...  (Ctrl+C để dừng)
```

---

### Bước 8 — Đăng ký Webhook (Terminal 2)

```bash
curl -X POST http://localhost:8000/api/webhooks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Mock Receiver",
    "url": "http://host.docker.internal:9000",
    "secret": "test-secret-123"
  }'
```

Kết quả: `{"id": 1, "status": "created"}`

---

### Bước 9 — Gửi email test có attachment

Từ **một Gmail khác** (không phải khainqk981@gmail.com), gửi tới `khainqk981@gmail.com`:

```
To:      khainqk981@gmail.com
Subject: Test Invoice tháng 6
Body:    Kính gửi, đính kèm hóa đơn.
Attach:  invoice.pdf  (hoặc bất kỳ file PDF/PNG/DOCX nào)
```

---

### Bước 10 — Trigger Poll + Xem kết quả

Sau khi gửi email xong, không cần chờ 30s:

```bash
# Trigger poll ngay lập tức
curl -X POST http://localhost:8000/api/crawl
```

Xem log realtime:

```bash
docker compose logs -f app
```

**Log khi email được xử lý thành công:**

```
INFO  Saved email id=11 from=khiemnguyen.hye@gmail.com subject='Test Invoice tháng 6' attachments=1
INFO  Webhook 1 → email 11: HTTP 200
```

**Mock server (Terminal 1) in ra:**

```
════════════════════════════════════════════════════════════
[10:30:15] Webhook received  →  /
  Signature : ✓ VALID

  Event   : email.received
  Email ID: 11
  From    : khiemnguyen.hye@gmail.com
  Subject : Test Invoice tháng 6
  Attachments (1):
    • invoice.pdf  (102 KB)
      http://localhost:8000/api/attachments/11/download
════════════════════════════════════════════════════════════
```

---

### Bước 11 — Kiểm tra qua API

```bash
# Xem email vừa nhận
curl http://localhost:8000/api/emails | python3 -m json.tool

# Xem chi tiết email kèm attachments
curl http://localhost:8000/api/emails/11 | python3 -m json.tool

# Tải file đính kèm về máy
curl -O http://localhost:8000/api/attachments/11/download

# Kiểm tra webhook đã gửi thành công
curl "http://localhost:8000/api/webhook-deliveries?email_id=11" | python3 -m json.tool

# Xem trạng thái polling
curl http://localhost:8000/api/crawl/status | python3 -m json.tool
```

---

### Bước 12 — Chạy script test tự động

```bash
bash scripts/test_flow.sh
```

Script này tự động kiểm tra 7 bước: health check → đăng ký webhook → inject email giả → xem DB → filter → download file → xác nhận webhook delivery.

---

## Phần 4 — Swagger UI (tùy chọn)

Mở trình duyệt vào địa chỉ:

```
http://localhost:8000/docs
```

Toàn bộ API có thể gọi thử trực tiếp từ giao diện web này.

---

## Xử lý sự cố thường gặp

### Lỗi: `[AUTHENTICATIONFAILED] Invalid credentials`

```
Nguyên nhân : App Password sai hoặc chưa tạo
Kiểm tra    : Vào https://myaccount.google.com/apppasswords
              Xem danh sách App passwords đã tạo
Giải pháp   : Xóa app password cũ → tạo lại → cập nhật .env → rebuild
```

```bash
docker compose up --build -d
```

---

### Lỗi: `[UNAVAILABLE] IMAP is not enabled`

```
Nguyên nhân : Chưa bật IMAP trong Gmail settings
Giải pháp   : Gmail → ⚙️ → See all settings → Forwarding and POP/IMAP
              → Enable IMAP → Save Changes
```

---

### Lỗi: Port 5432 already in use

```
Nguyên nhân : PostgreSQL local đang chạy trùng port
Giải pháp   : Đã config docker-compose.yml dùng port 5433 cho host
              Container vẫn dùng 5432 nội bộ → không ảnh hưởng
```

---

### Webhook delivery status = `retrying` hoặc `failed`

```
Nguyên nhân : Mock server chưa chạy hoặc URL sai
Kiểm tra    : curl http://localhost:9000 (phải trả lời 501)
Giải pháp   : python3 scripts/mock_webhook_server.py
              Sau đó retry thủ công:
```

```bash
# Xem delivery nào đang failed
curl "http://localhost:8000/api/webhook-deliveries?status=failed"

# Retry thủ công
curl -X POST http://localhost:8000/api/webhook-deliveries/1/retry
```

---

### Email gửi đến nhưng không thấy trong platform

```
Nguyên nhân : Chỉ lấy email UNSEEN (chưa đọc)
              Nếu bạn mở Gmail web xem email → Gmail đánh dấu đã đọc → platform bỏ qua

Giải pháp   : Gửi email mới và KHÔNG mở trong Gmail web trước khi poll
              Hoặc dùng Gmail filter để giữ email là UNREAD
```

---

## Cấu trúc file khi có email với attachment

```
storage/
└── email_11/
    └── invoice.pdf          ← file gốc từ email
```

```sql
-- emails table
id=11, sender_email='khiemnguyen.hye@gmail.com',
       subject='Test Invoice tháng 6',
       processed_at='2026-06-03T10:30:15Z'

-- attachments table
id=11, email_id=11,
       filename='invoice.pdf',
       filepath='/app/storage/email_11/invoice.pdf',
       mime_type='application/pdf',
       file_size=104448,
       checksum='sha256:abc123...'

-- webhook_deliveries table
id=X, webhook_id=1, email_id=11,
      status='success', attempt_count=1,
      response_code=200
```

---

## Lệnh vận hành hàng ngày

```bash
# Xem log
docker compose logs -f app

# Trigger poll thủ công
curl -X POST http://localhost:8000/api/crawl

# Kiểm tra trạng thái polling
curl http://localhost:8000/api/crawl/status

# Xem email mới nhất
curl "http://localhost:8000/api/emails?page=1&size=5"

# Xem webhook deliveries thất bại
curl "http://localhost:8000/api/webhook-deliveries?status=failed"

# Restart nếu có lỗi
docker compose restart app

# Dừng toàn bộ
docker compose down

# Dừng và xóa dữ liệu DB (cẩn thận)
docker compose down -v
```
