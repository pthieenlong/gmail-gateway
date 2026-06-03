#!/usr/bin/env python3
"""
Mock Webhook Receiver — chạy trên máy host để nhận webhook từ Email Gateway.

Chạy:
    python3 scripts/mock_webhook_server.py

Sau đó đăng ký webhook URL:
    http://host.docker.internal:9000   (từ trong Docker container)
    http://localhost:9000              (nếu test local không qua Docker)
"""
import hashlib
import hmac
import json
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

SECRET = "test-secret-123"   # phải khớp với secret khi đăng ký webhook
PORT = 9000

RESET  = "\033[0m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        ts = datetime.now().strftime("%H:%M:%S")

        sig_header = self.headers.get("X-Signature", "")
        expected   = "sha256=" + hmac.new(
            SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        valid = hmac.compare_digest(expected, sig_header) if sig_header else False

        print(f"\n{BOLD}{'═'*60}{RESET}")
        print(f"{CYAN}[{ts}] Webhook received  →  {self.path}{RESET}")
        print(f"  Signature : {GREEN}✓ VALID{RESET}" if valid else f"  Signature : {RED}✗ INVALID{RESET}")
        print(f"  X-Signature header : {sig_header[:40]}...")

        try:
            payload = json.loads(body)
            event = payload.get("event", "?")
            email_id = payload.get("email_id", "?")
            sender = payload.get("sender_email", "?")
            subject = payload.get("subject", "?")
            atts = payload.get("attachments", [])

            print(f"\n  {BOLD}Event   :{RESET} {event}")
            print(f"  Email ID: {email_id}")
            print(f"  From    : {sender}")
            print(f"  Subject : {subject}")
            print(f"  Attachments ({len(atts)}):")
            for a in atts:
                size_kb = (a.get("file_size") or 0) // 1024
                print(f"    • {a['filename']}  ({size_kb} KB)")
                print(f"      {YELLOW}{a['download_url']}{RESET}")

        except Exception as e:
            print(f"  {RED}Could not parse JSON: {e}{RESET}")
            print(f"  Raw body: {body[:200]}")

        print(f"{BOLD}{'═'*60}{RESET}")

        # Trả về HTTP 200 để platform đánh dấu delivery thành công
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"received"}')

    def log_message(self, *_):
        pass  # tắt log mặc định


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print(f"{BOLD}Mock Webhook Server{RESET}")
    print(f"  Listening : http://0.0.0.0:{PORT}")
    print(f"  Secret    : {SECRET}")
    print(f"\nĐăng ký webhook với URL:")
    print(f"  {GREEN}http://host.docker.internal:{PORT}{RESET}  ← từ bên trong Docker")
    print(f"  {GREEN}http://localhost:{PORT}{RESET}             ← nếu test không qua Docker")
    print(f"\nWaiting for webhooks...  (Ctrl+C để dừng)\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)
