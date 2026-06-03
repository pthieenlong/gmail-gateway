#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# test_flow.sh — Kiểm tra toàn bộ luồng Email Gateway
#
# Chạy:
#   Terminal 1:  python3 scripts/mock_webhook_server.py
#   Terminal 2:  bash scripts/test_flow.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

BASE="http://localhost:8000/api"
WEBHOOK_URL="http://host.docker.internal:9000"
WEBHOOK_SECRET="test-secret-123"

# ── màu (ghi ra stderr để không lẫn vào capture) ────────────────────────────
GRN="\033[92m"; YLW="\033[93m"; RED="\033[91m"; CYN="\033[96m"
BLD="\033[1m";  RST="\033[0m"

step()  { echo -e "\n${BLD}${CYN}══ $* ${RST}" >&2; }
ok()    { echo -e "  ${GRN}✓ $*${RST}" >&2; }
info()  { echo -e "  ${YLW}→ $*${RST}" >&2; }
fail()  { echo -e "  ${RED}✗ $*${RST}" >&2; }
HR()    { echo -e "${BLD}${GRN}══ $* ══${RST}" >&2; }

# Gọi API và trả về body; exit nếu status không khớp
api() {
  local method="$1"; shift
  local url="$1"; shift
  local expect="${1:-200}"; shift || true

  local tmp; tmp=$(mktemp)
  local code
  code=$(curl -s -o "$tmp" -w "%{http_code}" -X "$method" "$url" "$@")
  local body; body=$(cat "$tmp"); rm -f "$tmp"

  if [ "$code" != "$expect" ]; then
    fail "HTTP $code (expected $expect)"
    echo "$body" | python3 -m json.tool >&2 2>/dev/null || echo "$body" >&2
    exit 1
  fi
  ok "HTTP $code"
  echo "$body"
}

jq_get() {
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d$1)" 2>/dev/null
}

# ─────────────────────────────────────────────────────────────────────────────
step "1 / 7  Health check"
api GET "$BASE/health" 200 | python3 -m json.tool >&2
ok "System is up"

# ─────────────────────────────────────────────────────────────────────────────
step "2 / 7  Đăng ký webhook → mock server"
body=$(api POST "$BASE/webhooks" 201 \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Mock Server\",\"url\":\"$WEBHOOK_URL\",\"secret\":\"$WEBHOOK_SECRET\"}")
echo "$body" | python3 -m json.tool >&2
WEBHOOK_ID=$(echo "$body" | jq_get "['id']")
ok "Webhook ID = $WEBHOOK_ID"

# ─────────────────────────────────────────────────────────────────────────────
step "3 / 7  Inject email giả + kích hoạt webhook"
info "POST /api/dev/inject-email"
body=$(api POST "$BASE/dev/inject-email" 200)
echo "$body" | python3 -m json.tool >&2
EMAIL_ID=$(echo "$body"  | jq_get "['email_id']")
ATT_ID=$(echo "$body"    | jq_get "['attachment_id']")
ok "Email ID=$EMAIL_ID  |  Attachment ID=$ATT_ID"

# ─────────────────────────────────────────────────────────────────────────────
step "4 / 7  Xem email vừa lưu trong DB"
body=$(api GET "$BASE/emails/$EMAIL_ID" 200)
echo "$body" | python3 -m json.tool >&2
ok "Email có trong DB với attachments"

# ─────────────────────────────────────────────────────────────────────────────
step "5 / 7  List + filter emails theo sender"
body=$(api GET "$BASE/emails?sender_email=test-customer" 200)
total=$(echo "$body" | jq_get "['total']")
echo "$body" | python3 -m json.tool >&2
ok "Tổng cộng $total email khớp filter"

# ─────────────────────────────────────────────────────────────────────────────
step "6 / 7  Download attachment"
DEST="/tmp/test_invoice_${ATT_ID}.pdf"
info "GET /api/attachments/$ATT_ID/download → $DEST"
HTTP_CODE=$(curl -s -o "$DEST" -w "%{http_code}" "$BASE/attachments/$ATT_ID/download")
if [ "$HTTP_CODE" = "200" ]; then
  SZ=$(wc -c < "$DEST")
  ok "File tải về: $DEST (${SZ} bytes)"
  file "$DEST" >&2 2>/dev/null || true
else
  fail "Download failed — HTTP $HTTP_CODE"
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
step "7 / 7  Kiểm tra Webhook Delivery status"
sleep 1
body=$(api GET "$BASE/webhook-deliveries?email_id=$EMAIL_ID" 200)
echo "$body" | python3 -m json.tool >&2
STATUS=$(echo "$body" | python3 -c "
import sys, json
items = json.load(sys.stdin)
print(items[0]['status'] if items else 'no_record')
" 2>/dev/null)

case "$STATUS" in
  success)
    ok "Webhook delivery: SUCCESS ✓"
    info "Mock server đã nhận event 'email.received'"
    ;;
  retrying)
    info "Webhook delivery: RETRYING"
    info "→ Chắc chắn mock_webhook_server.py đang chạy chưa?"
    info "  python3 scripts/mock_webhook_server.py"
    info "  Sau đó: curl -X POST $BASE/webhook-deliveries/1/retry"
    ;;
  failed)
    fail "Webhook delivery FAILED — xem response_body ở trên"
    ;;
  *)
    info "Status: $STATUS"
    ;;
esac

# ─────────────────────────────────────────────────────────────────────────────
HR "Tất cả bước đã pass"
echo -e "  Swagger UI  : ${YLW}http://localhost:8000/docs${RST}" >&2
echo -e "  Emails      : ${YLW}$BASE/emails${RST}" >&2
echo -e "  Deliveries  : ${YLW}$BASE/webhook-deliveries${RST}" >&2
echo "" >&2
