"""
Email fetching backends.

IMAPEmailFetcher  – works with any IMAP server (Gmail, Outlook, …).
                    For Gmail use an App Password (Settings → Security → App passwords).

GmailAPIFetcher   – uses the Gmail REST API with OAuth 2.0.
                    Requires credentials.json from Google Cloud Console.
                    On first run the OAuth flow opens a browser tab; after that
                    token.json is reused automatically.
"""
import asyncio
import email
import imaplib
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any, Dict, List

from app.config import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────── helpers ────────────────────────────────────

def _decode_str(value: str) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    result = []
    for raw, enc in parts:
        if isinstance(raw, bytes):
            result.append(raw.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(raw)
    return " ".join(result)


def _get_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get_content_disposition() or "")
            if ctype == "text/plain" and "attachment" not in disp:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return ""


def _cc_emails(msg) -> str | None:
    """Comma-separated CC addresses from an email.message, or None."""
    cc = [addr for _, addr in getaddresses(msg.get_all("Cc", [])) if addr]
    return ", ".join(cc) or None


def _get_attachments(msg) -> List[Dict[str, Any]]:
    results = []
    for part in msg.walk():
        disp = str(part.get_content_disposition() or "")
        fname = part.get_filename()
        if not fname:
            continue
        fname = _decode_str(fname)
        content = part.get_payload(decode=True)
        if content is None:
            continue
        results.append(
            {
                "filename": fname,
                "content": content,
                "mime_type": part.get_content_type(),
            }
        )
    return results


# ─────────────────────────────── IMAP ───────────────────────────────────────

def _imap_fetch() -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    try:
        conn = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
        conn.login(settings.IMAP_USERNAME, settings.IMAP_PASSWORD)
        conn.select("INBOX")
        _, nums = conn.search(None, "UNSEEN")
        if not nums[0]:
            conn.close()
            conn.logout()
            return results

        for num in nums[0].split():
            try:
                _, data = conn.fetch(num, "(RFC822)")
                raw = data[0][1]
                msg = email.message_from_bytes(raw)

                from_hdr = msg.get("From", "")
                addrs = getaddresses([from_hdr])
                sender_name = addrs[0][0] if addrs else ""
                sender_email = addrs[0][1] if addrs else ""

                to_hdr = msg.get("To", "")
                to_addrs = getaddresses([to_hdr])
                recipient = to_addrs[0][1] if to_addrs else settings.IMAP_USERNAME

                try:
                    received_at = parsedate_to_datetime(msg.get("Date", ""))
                except Exception:
                    received_at = datetime.now(timezone.utc)

                results.append(
                    {
                        "message_id": msg.get("Message-ID", f"imap-{num.decode()}").strip(),
                        "sender_email": sender_email,
                        "sender_name": sender_name,
                        "recipient_email": recipient,
                        "cc_emails": _cc_emails(msg),
                        "subject": _decode_str(msg.get("Subject", "")),
                        "body": _get_body(msg),
                        "received_at": received_at,
                        "attachments": _get_attachments(msg),
                    }
                )
                conn.store(num, "+FLAGS", "\\Seen")

            except Exception as exc:
                logger.error("Failed to parse email %s: %s", num, exc)

        conn.close()
        conn.logout()

    except Exception as exc:
        logger.error("IMAP error: %s", exc)
        raise

    return results


class IMAPEmailFetcher:
    def __init__(self):
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="imap")

    async def fetch_unread_emails(self) -> List[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._pool, _imap_fetch)

    def close(self):
        self._pool.shutdown(wait=False)


# ─────────────────────────────── Gmail API ──────────────────────────────────

class GmailAPIFetcher:
    """
    OAuth 2.0 Gmail API fetcher.

    First-run setup:
      1. Go to Google Cloud Console → APIs & Services → Credentials
      2. Create OAuth 2.0 Client ID (Desktop app)
      3. Download credentials.json and place it in the project root
      4. Start the app once locally; a browser tab will open for consent
      5. token.json is saved automatically for future runs
    """

    _SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

    def _get_service(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        import os

        creds = None
        token_path = settings.GMAIL_TOKEN_FILE
        creds_path = settings.GMAIL_CREDENTIALS_FILE

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, self._SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, self._SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as f:
                f.write(creds.to_json())

        return build("gmail", "v1", credentials=creds)

    def _fetch(self) -> List[Dict[str, Any]]:
        import base64

        service = self._get_service()
        results: List[Dict[str, Any]] = []

        response = (
            service.users()
            .messages()
            .list(userId="me", q="is:unread in:inbox", maxResults=50)
            .execute()
        )
        messages = response.get("messages", [])

        for msg_ref in messages:
            try:
                msg_data = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_ref["id"], format="raw")
                    .execute()
                )
                raw = base64.urlsafe_b64decode(msg_data["raw"])
                msg = email.message_from_bytes(raw)

                from_hdr = msg.get("From", "")
                addrs = getaddresses([from_hdr])
                sender_name = addrs[0][0] if addrs else ""
                sender_email = addrs[0][1] if addrs else ""

                to_hdr = msg.get("To", "")
                to_addrs = getaddresses([to_hdr])
                recipient = to_addrs[0][1] if to_addrs else settings.IMAP_USERNAME

                try:
                    received_at = parsedate_to_datetime(msg.get("Date", ""))
                except Exception:
                    received_at = datetime.now(timezone.utc)

                results.append(
                    {
                        "message_id": msg.get("Message-ID", msg_ref["id"]).strip(),
                        "sender_email": sender_email,
                        "sender_name": sender_name,
                        "recipient_email": recipient,
                        "cc_emails": _cc_emails(msg),
                        "subject": _decode_str(msg.get("Subject", "")),
                        "body": _get_body(msg),
                        "received_at": received_at,
                        "attachments": _get_attachments(msg),
                    }
                )

                # Mark as read
                service.users().messages().modify(
                    userId="me",
                    id=msg_ref["id"],
                    body={"removeLabelIds": ["UNREAD"]},
                ).execute()

            except Exception as exc:
                logger.error("Failed to parse Gmail message %s: %s", msg_ref["id"], exc)

        return results

    def __init__(self):
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gmail")

    async def fetch_unread_emails(self) -> List[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._pool, self._fetch)

    def close(self):
        self._pool.shutdown(wait=False)


# ─────────────────────────── Microsoft Graph API ────────────────────────────

class GraphAPIFetcher:
    """
    Microsoft Graph API fetcher for Outlook / Microsoft 365 mailboxes.

    Uses app-only (client credentials) OAuth 2.0 — no interactive login, suited
    for an unattended service. Microsoft has retired Basic Auth for IMAP/POP on
    Exchange Online, so Graph is the supported way to read an M365 mailbox.

    Azure setup:
      1. Entra admin center → App registrations → New registration
      2. Certificates & secrets → New client secret  → GRAPH_CLIENT_SECRET
      3. API permissions → Microsoft Graph → Application → Mail.ReadWrite
         → Grant admin consent
      4. Set GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_USER_ID (the mailbox).

    Note: app-only Mail.ReadWrite grants access to *all* mailboxes by default.
    To scope it to a single mailbox, configure an Application Access Policy in
    Exchange Online.
    """

    _SCOPE = ["https://graph.microsoft.com/.default"]
    _GRAPH = "https://graph.microsoft.com/v1.0"

    def _token(self) -> str:
        import msal

        app = msal.ConfidentialClientApplication(
            client_id=settings.GRAPH_CLIENT_ID,
            client_credential=settings.GRAPH_CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{settings.GRAPH_TENANT_ID}",
        )
        # MSAL caches the token internally and only hits the IdP on cache miss.
        result = app.acquire_token_for_client(scopes=self._SCOPE)
        if "access_token" not in result:
            raise RuntimeError(
                "Graph auth failed: "
                f"{result.get('error')} — {result.get('error_description')}"
            )
        return result["access_token"]

    @staticmethod
    def _allowed_extensions() -> set:
        raw = settings.GRAPH_ATTACHMENT_TYPES.strip()
        if not raw:
            return set()
        return {ext.strip().lower() for ext in raw.split(",")}

    def _fetch_mailbox(
        self,
        requests_mod,
        headers: dict,
        mailbox: str,
        allowed_exts: set,
        graph_filter: str,
    ) -> List[Dict[str, Any]]:
        from pathlib import Path

        base = f"{self._GRAPH}/users/{mailbox}"
        results: List[Dict[str, Any]] = []

        resp = requests_mod.get(
            f"{base}/mailFolders/inbox/messages",
            headers=headers,
            params={
                "$filter": graph_filter,
                "$orderby": "receivedDateTime desc",
                "$top": "50",
                "$select": (
                    "id,internetMessageId,subject,body,bodyPreview,"
                    "from,toRecipients,ccRecipients,receivedDateTime,hasAttachments"
                ),
            },
            timeout=30,
        )
        resp.raise_for_status()

        for msg in resp.json().get("value", []):
            try:
                from_addr = (msg.get("from") or {}).get("emailAddress") or {}

                def _addrs(key: str) -> List[str]:
                    return [
                        addr
                        for r in (msg.get(key) or [])
                        if (addr := (r.get("emailAddress") or {}).get("address"))
                    ]

                to_emails = _addrs("toRecipients")
                cc_emails = _addrs("ccRecipients")
                recipient = to_emails[0] if to_emails else mailbox

                # Was the scanned mailbox addressed directly (To) or only CC'd?
                mailbox_l = mailbox.lower()
                if any(a.lower() == mailbox_l for a in to_emails):
                    delivered_via = "to"
                elif any(a.lower() == mailbox_l for a in cc_emails):
                    delivered_via = "cc"
                else:
                    delivered_via = None  # bcc / forwarded / group alias

                # Only keep mail where this mailbox is a direct recipient (To).
                # CC-only / bcc / alias mail is skipped — if it was To'd to another
                # configured mailbox, that mailbox's own scan will pick it up.
                if delivered_via != "to":
                    logger.debug(
                        "Skipping message %s — mailbox %s is not a To recipient "
                        "(delivered_via=%s)",
                        msg.get("id"), mailbox, delivered_via,
                    )
                    continue

                try:
                    received_at = datetime.fromisoformat(
                        msg["receivedDateTime"].replace("Z", "+00:00")
                    )
                except Exception:
                    received_at = datetime.now(timezone.utc)

                attachments = (
                    self._fetch_attachments(base, headers, msg["id"])
                    if msg.get("hasAttachments")
                    else []
                )

                if allowed_exts and not any(
                    Path(a["filename"]).suffix.lower() in allowed_exts
                    for a in attachments
                ):
                    logger.debug(
                        "Skipping message %s — no matching attachment extensions (%s)",
                        msg.get("id"), settings.GRAPH_ATTACHMENT_TYPES,
                    )
                    continue

                results.append(
                    {
                        "message_id": (
                            msg.get("internetMessageId") or msg["id"]
                        ).strip(),
                        "sender_email": from_addr.get("address", ""),
                        "sender_name": from_addr.get("name", ""),
                        "recipient_email": recipient,
                        "cc_emails": ", ".join(cc_emails) or None,
                        "delivered_via": delivered_via,
                        "subject": msg.get("subject", ""),
                        "body": (msg.get("body") or {}).get(
                            "content", msg.get("bodyPreview", "")
                        ),
                        "received_at": received_at,
                        "attachments": attachments,
                    }
                )

                # No mark-as-read: the app only has Mail.Read (read-only). Re-fetching
                # within the lookback window is deduped by the message_id guard in the DB.

            except Exception as exc:
                logger.error(
                    "Failed to parse Graph message %s (mailbox=%s): %s",
                    msg.get("id"), mailbox, exc,
                )

        return results

    def _fetch(self) -> List[Dict[str, Any]]:
        import requests
        from datetime import timedelta

        headers = {"Authorization": f"Bearer {self._token()}"}
        allowed_exts = self._allowed_extensions()

        # Read-only: filter by receivedDateTime (last N minutes) instead of isRead,
        # since we can't mark messages read without write permission.
        since = (
            datetime.now(timezone.utc) - timedelta(minutes=settings.GRAPH_LOOKBACK_MINUTES)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        graph_filter = f"receivedDateTime ge {since}"
        if allowed_exts:
            graph_filter += " AND hasAttachments eq true"

        mailboxes = [m.strip() for m in settings.GRAPH_USER_ID.split(",") if m.strip()]
        results: List[Dict[str, Any]] = []

        for mailbox in mailboxes:
            try:
                results.extend(
                    self._fetch_mailbox(requests, headers, mailbox, allowed_exts, graph_filter)
                )
            except Exception as exc:
                logger.error("Failed to fetch mailbox %s: %s", mailbox, exc)

        return results

    @staticmethod
    def _fetch_attachments(base: str, headers: dict, msg_id: str) -> List[Dict[str, Any]]:
        import base64
        import requests

        resp = requests.get(
            f"{base}/messages/{msg_id}/attachments",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()

        out: List[Dict[str, Any]] = []
        for att in resp.json().get("value", []):
            # Only fileAttachment carries inline bytes; skip itemAttachment / reference.
            if att.get("@odata.type") != "#microsoft.graph.fileAttachment":
                continue
            content_bytes = att.get("contentBytes")
            if not content_bytes:
                continue
            out.append(
                {
                    "filename": att.get("name", "attachment"),
                    "content": base64.b64decode(content_bytes),
                    "mime_type": att.get("contentType"),
                }
            )
        return out

    def __init__(self):
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="graph")

    async def fetch_unread_emails(self) -> List[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._pool, self._fetch)

    def close(self):
        self._pool.shutdown(wait=False)
