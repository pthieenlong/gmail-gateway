# Gmail API Setup Guide

## Bước 1 — Tạo Google Cloud Project

1. Vào https://console.cloud.google.com
2. New Project → đặt tên "email-gateway"
3. Select project vừa tạo

## Bước 2 — Enable Gmail API

APIs & Services → Library → tìm "Gmail API" → Enable

## Bước 3 — Tạo OAuth2 Credentials

1. APIs & Services → Credentials → Create Credentials → OAuth client ID
2. Application type: **Desktop app**
3. Name: "email-gateway-local"
4. Download JSON → đổi tên thành `credentials.json`
5. Đặt file vào root của project

## Bước 4 — Configure OAuth Consent Screen

1. APIs & Services → OAuth consent screen
2. User Type: External (hoặc Internal nếu dùng Workspace)
3. App name, support email → điền
4. Scopes → Add: `https://www.googleapis.com/auth/gmail.modify`
5. Test users → thêm Gmail account của hộp thư hệ thống

## Bước 5 — Cập nhật .env

```
EMAIL_PROVIDER=gmail
GMAIL_CREDENTIALS_FILE=credentials.json
GMAIL_TOKEN_FILE=token.json
```

## Bước 6 — Lần đầu chạy (lấy token)

Chạy LOCAL (không phải Docker) để browser có thể mở:

```bash
uvicorn app.main:app --reload
```

Browser sẽ tự mở → đăng nhập Gmail account hộp thư → Allow
→ `token.json` được tạo tự động.

Sau đó có thể chạy bằng Docker bình thường (mount token.json vào container).

## Docker với token.json đã có

docker-compose.yml đã mount sẵn:
```yaml
volumes:
  - ./token.json:/app/token.json
```

Chỉ cần đảm bảo `token.json` có trong thư mục project trước khi `docker compose up`.
