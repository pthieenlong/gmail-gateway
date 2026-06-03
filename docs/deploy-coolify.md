# Deploy lên Coolify

Dùng đúng một file `docker-compose.yml` cho cả local lẫn production.  
Không cần sửa code — chỉ cần set biến môi trường trong Coolify UI.

---

## Yêu cầu

| Thứ | Yêu cầu |
|-----|---------|
| VPS | RAM ≥ 2 GB, Ubuntu 22.04+ |
| Coolify | Đã cài, truy cập được dashboard |
| Domain | A record trỏ về IP của VPS |
| GitHub | Code đã push lên repository |
| Gmail | Đã có App Password (xem [setup-gmail-imap.md](setup-gmail-imap.md)) |

---

## Bước 1 — Push code lên GitHub

```bash
cd /home/khai/Desktop/email-gateway

git init
git add .
git commit -m "feat: email ingestion gateway"

git remote add origin https://github.com/your-username/email-gateway.git
git push -u origin main
```

> `.env` đã có trong `.gitignore` — credentials không bao giờ lên GitHub.

---

## Bước 2 — Tạo project trong Coolify

```
Coolify Dashboard
→ Projects → + New Project
→ Name: email-gateway
→ Create
```

---

## Bước 3 — Thêm resource

```
Projects → email-gateway → + New Resource
→ Docker Compose
→ Source: GitHub  (kết nối GitHub account nếu chưa)
→ Repository: your-username/email-gateway
→ Branch: main
→ Docker Compose file: docker-compose.yml    ← file duy nhất
→ Continue
```

---

## Bước 4 — Cấu hình Domain

```
Domains: api.your-domain.com
→ Generate SSL Certificate: ✓  (Coolify tự cấp Let's Encrypt)
→ Save
```

---

## Bước 5 — Điền Environment Variables

Vào tab **Environment Variables** trong Coolify, điền từng dòng:

```
APP_PORT=8000
BASE_URL=https://api.your-domain.com

POSTGRES_PASSWORD=<mật-khẩu-mạnh-ngẫu-nhiên>

EMAIL_PROVIDER=imap
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USERNAME=khainqk981@gmail.com
IMAP_PASSWORD=ndnh slnx yaqh jtgz

POLL_INTERVAL_SECONDS=30
WEBHOOK_TIMEOUT_SECONDS=30
```

> Bật **"Is Secret"** cho `POSTGRES_PASSWORD` và `IMAP_PASSWORD` để Coolify mã hóa.

**Điểm khác duy nhất giữa local và production:**

| Biến | Local | Production |
|------|-------|------------|
| `BASE_URL` | `http://localhost:8000` | `https://api.your-domain.com` |
| `POSTGRES_PASSWORD` | `postgres` | mật khẩu mạnh |

---

## Bước 6 — Deploy

```
Coolify → email-gateway → Deploy
```

Coolify sẽ:
1. Pull code từ GitHub
2. Build Docker image
3. Chạy `alembic upgrade head` (tạo tables)
4. Start PostgreSQL + App
5. Cấp SSL, cấu hình reverse proxy

Xem build log realtime trong Coolify UI.

---

## Bước 7 — Kiểm tra

```bash
# Health check
curl https://api.your-domain.com/api/health
# → {"status": "ok"}

# Trạng thái polling
curl https://api.your-domain.com/api/crawl/status
# → {"last_run_status": "success", ...}

# Swagger UI
open https://api.your-domain.com/docs
```

**Log thành công** (xem trong Coolify → Logs):

```
INFO  Email Gateway started
INFO  Email poller started (interval=30s, provider=imap)
INFO  Poll complete. Processed 0 emails.
```

---

## Bước 8 — Đăng ký webhook cho client

```bash
curl -X POST https://api.your-domain.com/api/webhooks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "OCR System",
    "url": "https://ocr.client-domain.com/webhook",
    "secret": "secret-riêng-cho-từng-client"
  }'
```

Mỗi client đăng ký một webhook riêng với secret riêng.

---

## Auto Deploy khi push code mới

```
Coolify → email-gateway → Settings → Auto Deploy → Enable
```

Từ đó: `git push origin main` → Coolify tự build và deploy lại.

---

## Backup

```bash
# SSH vào VPS, chạy:

# Backup database
docker exec $(docker ps --filter name=email-gateway-db -q) \
  pg_dump -U postgres email_gateway > backup_$(date +%Y%m%d).sql

# Xem volume storage nằm ở đâu
docker volume inspect email-gateway_email_storage
```

---

## Xử lý sự cố

| Triệu chứng | Kiểm tra | Giải pháp |
|-------------|----------|-----------|
| `{"status": "ok"}` không trả về | Coolify Logs → app | Xem lỗi cụ thể |
| `last_run_status: "error"` | `GET /api/crawl/status` | Xem `last_error` — thường là IMAP auth |
| IMAP auth failed | App Password hết hạn hoặc sai | Tạo App Password mới → cập nhật biến trong Coolify → Redeploy |
| Webhook delivery failed | `GET /api/webhook-deliveries?status=failed` | Xem `response_body` → fix URL hoặc client → retry |
| Domain không truy cập được | DNS chưa propagate | Chờ 5–30 phút sau khi thêm A record |

---

## So sánh local vs production

| | Local | Coolify Production |
|--|-------|--------------------|
| Khởi động | `docker compose up --build -d` | Click Deploy trong UI |
| URL | `http://localhost:8000` | `https://api.your-domain.com` |
| SSL | Không | Tự động (Let's Encrypt) |
| File config | `.env` | Environment Variables trong UI |
| docker-compose.yml | **Cùng một file** | **Cùng một file** |
| Storage | `email_storage` volume | `email_storage` volume |
| DB | `postgres_data` volume | `postgres_data` volume |
