# Outlook / Microsoft 365 — Tích hợp đọc email qua Microsoft Graph API

Tài liệu này mô tả cách kết nối **Email Ingestion Gateway** với một hòm thư
Outlook / Microsoft 365 để tự động đọc email và trích xuất file đính kèm.

Tài liệu gồm 2 phần:

1. **[Phần A — Gửi cho IT / Admin](#phần-a--yêu-cầu-gửi-cho-it--admin)**: những gì cần admin
   tenant cấp (vì user thường không có quyền tự làm).
2. **[Phần B — Cấu hình ứng dụng](#phần-b--cấu-hình-ứng-dụng)**: sau khi đã có credentials thì
   điền vào đâu để chạy.

---

## Vì sao phải dùng Graph API (không dùng IMAP + mật khẩu)?

Microsoft đã **ngừng hỗ trợ Basic Authentication** (đăng nhập bằng
username + password / app password) cho IMAP, POP và SMTP trên Exchange Online.
Bản thân giao thức IMAP/POP vẫn còn, nhưng **bắt buộc phải dùng OAuth 2.0**.

→ Cách được Microsoft khuyến nghị để một service đọc hòm thư M365 là
**Microsoft Graph API** với luồng **app-only (client credentials)** — service tự
lấy access token bằng client secret, không cần ai đăng nhập tương tác.

| | IMAP + App Password | Microsoft Graph (app-only) |
|---|---|---|
| Còn dùng được với M365? | ❌ Đã bị tắt | ✅ Được khuyến nghị |
| Cần người đăng nhập? | Có (mật khẩu) | Không (chạy nền) |
| Quyền cấp ở đâu | — | Azure App registration |

---

## Phần A — Yêu cầu gửi cho IT / Admin

> **Bối cảnh:** User thường (vd `anh.huynh@satoricomp...`) **không có quyền** truy cập
> Microsoft Entra admin center để tự tạo App registration (sẽ gặp màn hình
> "không có quyền truy cập"). Các bước dưới đây **cần admin tenant** thực hiện
> hoặc uỷ quyền.

### Mục tiêu
Tạo một **App registration** trong Microsoft Entra ID cho phép service
"Email Ingestion Gateway" đọc email (và đánh dấu đã đọc) từ một hòm thư cụ thể.

### Các bước admin cần làm

1. Vào **[Microsoft Entra admin center](https://entra.microsoft.com)** →
   **Identity → Applications → App registrations → + New registration**
   - Name: `email-ingestion-gateway`
   - Supported account types: **Accounts in this organizational directory only (Single tenant)**
   - Redirect URI: **để trống** (app-only, không có login tương tác)
   - Bấm **Register**

2. Tại trang **Overview**, copy lại 2 giá trị:
   - **Application (client) ID**
   - **Directory (tenant) ID**

3. **Certificates & secrets → Client secrets → + New client secret**
   - Đặt thời hạn (vd 12–24 tháng) → **Add**
   - Copy ngay giá trị ở cột **Value** (⚠️ chỉ hiện 1 lần, mất là phải tạo lại)

4. **API permissions → + Add a permission → Microsoft Graph →
   Application permissions** → tick **`Mail.ReadWrite`** → **Add permissions**
   - Sau đó bấm **Grant admin consent for <tenant>** → trạng thái phải là ✅ *Granted*
   - *(Nếu chỉ cần đọc, không cần đánh dấu đã đọc, có thể dùng `Mail.Read` thay cho
     `Mail.ReadWrite` — xem mục lưu ý bảo mật bên dưới.)*

5. **(Khuyến nghị mạnh) Giới hạn phạm vi truy cập** bằng
   **Application Access Policy** trong Exchange Online — xem mục bảo mật bên dưới.

### Thông tin admin cần bàn giao lại

| Giá trị | Dùng cho biến |
|---|---|
| Directory (tenant) ID | `GRAPH_TENANT_ID` |
| Application (client) ID | `GRAPH_CLIENT_ID` |
| Client secret **Value** | `GRAPH_CLIENT_SECRET` |
| Địa chỉ hòm thư cần đọc (vd `inbox@satoricomp...`) | `GRAPH_USER_ID` |

---

## Lưu ý bảo mật (quan trọng — nên đưa vào phần xin phép)

- **Quyền app-only `Mail.ReadWrite` mặc định cho phép đọc/ghi MỌI hòm thư trong
  tenant.** Đây là rủi ro lớn nếu không giới hạn.
- **Cần cấu hình [Application Access Policy](https://learn.microsoft.com/en-us/graph/auth-limit-mailbox-access)**
  trong Exchange Online để giới hạn app chỉ truy cập **đúng một (hoặc vài) hòm thư**
  được chỉ định. Admin chạy PowerShell:

  ```powershell
  New-ApplicationAccessPolicy `
    -AppId <CLIENT_ID> `
    -PolicyScopeGroupId <địa-chỉ-mailbox-hoặc-mail-enabled-security-group> `
    -AccessRight RestrictAccess `
    -Description "Email Gateway: chỉ đọc hòm thư ingestion"
  ```

- **Quyền tối thiểu:** nếu service không cần đánh dấu email là đã đọc, dùng
  `Mail.Read` thay vì `Mail.ReadWrite`. *(Lưu ý: code hiện tại có gọi
  `PATCH isRead=true` để tránh xử lý lại email cũ — nếu chỉ cấp `Mail.Read` thì cần
  điều chỉnh code, ví dụ chuyển sang lọc theo thời gian nhận.)*
- **Client secret là thông tin nhạy cảm** — chỉ lưu trong `.env` / secret manager,
  **không commit** vào git. File `.env` đã nằm trong `.gitignore`.
- Đặt **lịch xoay (rotate) client secret** trước ngày hết hạn để tránh gián đoạn.

---

## Phần B — Cấu hình ứng dụng

Sau khi có đủ 4 giá trị từ admin, mở file `.env` và điền:

```bash
EMAIL_PROVIDER=graph
GRAPH_TENANT_ID=<Directory (tenant) ID>
GRAPH_CLIENT_ID=<Application (client) ID>
GRAPH_CLIENT_SECRET=<Client secret Value>
GRAPH_USER_ID=inbox@your-domain.com   # hòm thư cần đọc (email hoặc object id)
```

### Nếu chạy bằng Docker

Hiện `docker-compose.yml` chưa truyền các biến `GRAPH_*` vào service `app`.
Cần thêm vào phần `environment:` của service `app`:

```yaml
      EMAIL_PROVIDER: ${EMAIL_PROVIDER:-imap}
      GRAPH_TENANT_ID: ${GRAPH_TENANT_ID:-}
      GRAPH_CLIENT_ID: ${GRAPH_CLIENT_ID:-}
      GRAPH_CLIENT_SECRET: ${GRAPH_CLIENT_SECRET:-}
      GRAPH_USER_ID: ${GRAPH_USER_ID:-}
```

(Chạy local bằng `uvicorn` thì không cần — app đọc trực tiếp từ `.env`.)

### Khởi động

```bash
# Docker
docker compose up --build

# hoặc local
uvicorn app.main:app --reload
```

Khi `EMAIL_PROVIDER=graph`, email poller sẽ tự dùng `GraphAPIFetcher`.

---

## Cơ chế hoạt động (tóm tắt kỹ thuật)

1. **Lấy token**: dùng thư viện `msal` với `ConfidentialClientApplication`
   → `acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])`.
   MSAL tự cache token và chỉ gọi lại Identity Provider khi hết hạn.
2. **Đọc email chưa đọc**:
   `GET /users/{GRAPH_USER_ID}/mailFolders/inbox/messages?$filter=isRead eq false`
3. **Tải đính kèm**: `GET /messages/{id}/attachments` — lấy `contentBytes` (base64),
   chỉ xử lý loại `fileAttachment`.
4. **Đánh dấu đã đọc**: `PATCH /messages/{id}` với body `{"isRead": true}`
   (để lần poll sau không xử lý lại).

Code: [`GraphAPIFetcher`](../app/services/email_fetcher.py). Fetcher này có cùng
interface (`fetch_unread_emails()` + `close()`) với IMAP/Gmail, nên phần còn lại
của pipeline (lưu DB, lưu file, gửi webhook, retry) **không đổi**.

---

## Checklist nhanh

- [ ] Admin tạo App registration (single tenant)
- [ ] Có `tenant ID` + `client ID`
- [ ] Tạo client secret, lưu lại **Value**
- [ ] Cấp `Mail.ReadWrite` (Application) + **Grant admin consent**
- [ ] Cấu hình Application Access Policy giới hạn hòm thư
- [ ] Điền 4 biến `GRAPH_*` vào `.env`, đặt `EMAIL_PROVIDER=graph`
- [ ] (Docker) thêm biến `GRAPH_*` vào `docker-compose.yml`
- [ ] Khởi động và kiểm tra log poller đọc được email
