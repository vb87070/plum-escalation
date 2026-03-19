"""
Gmail IMAP Poller — polls UNSEEN emails every 2 minutes.
Requires Gmail address + App Password (not OAuth).

To generate App Password:
  myaccount.google.com → Security → 2-Step Verification → App Passwords
"""
import asyncio
import imaplib
import email
import email.header
import email.utils
import datetime
import re
import httpx
import os

import sources_config


API_BASE = "http://localhost:8000"
POLL_INTERVAL = 120  # seconds


def decode_header_str(raw: str) -> str:
    """Decode RFC2047-encoded email header strings."""
    parts = email.header.decode_header(raw or "")
    decoded = []
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded).strip()


def extract_body(msg: email.message.Message) -> str:
    """Extract plaintext body from email, falling back to HTML stripped of tags."""
    body_parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if ctype == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body_parts.append(payload.decode(charset, errors="replace"))
            elif ctype == "text/html" and not body_parts:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    # Strip HTML tags
                    text = re.sub(r"<[^>]+>", " ", html)
                    text = re.sub(r"\s+", " ", text).strip()
                    body_parts.append(text)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body_parts.append(payload.decode(charset, errors="replace"))

    return "\n".join(body_parts).strip()[:4000]  # cap at 4000 chars


def parse_sender(from_header: str):
    """Return (sender_name, sender_email) from a From: header."""
    name, addr = email.utils.parseaddr(from_header or "")
    name = decode_header_str(name) if name else addr.split("@")[0]
    return name.strip(), addr.strip()


def ingest_message(source_channel, source_message_id, received_at, sender_name, sender_contact, raw_message):
    """POST one message to our own /webhook/ingest endpoint (sync — runs inside thread executor)."""
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{API_BASE}/webhook/ingest", json={
                "source_channel": source_channel,
                "source_message_id": source_message_id,
                "received_at": received_at,
                "sender_name": sender_name,
                "sender_contact": sender_contact,
                "raw_message": raw_message,
            })
            return resp.status_code == 201
    except Exception as e:
        print(f"[Gmail] Ingest error: {e}")
        return False


def poll_account(account: dict) -> int:
    """Poll one Gmail account for UNSEEN messages. Returns count ingested."""
    ingested = 0
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    try:
        mail.login(account["email"], account["app_password"])
        mail.select("inbox")

        _, data = mail.search(None, "UNSEEN")
        uids = data[0].split() if data[0] else []

        if not uids:
            return 0

        print(f"[Gmail] {account['email']} — {len(uids)} new email(s)")

        for uid in uids:
            try:
                _, msg_data = mail.fetch(uid, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                subject = decode_header_str(msg.get("Subject", ""))
                sender_name, sender_email = parse_sender(msg.get("From", ""))
                date_str = msg.get("Date", "")
                body = extract_body(msg)

                # Include subject in message for better AI classification
                full_message = f"Subject: {subject}\n\n{body}" if subject else body

                if not full_message.strip():
                    continue

                # Parse date
                try:
                    parsed_date = email.utils.parsedate_to_datetime(date_str)
                    received_at = parsed_date.isoformat()
                except Exception:
                    received_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

                message_id = msg.get("Message-ID", f"gmail-uid-{uid.decode()}")

                ok = ingest_message(
                    source_channel="gmail",
                    source_message_id=message_id,
                    received_at=received_at,
                    sender_name=sender_name,
                    sender_contact=sender_email,
                    raw_message=full_message,
                )

                if ok:
                    # Mark as seen so we don't re-process
                    mail.store(uid, "+FLAGS", "\\Seen")
                    ingested += 1

            except Exception as e:
                print(f"[Gmail] Error processing UID {uid}: {e}")

    finally:
        try:
            mail.logout()
        except Exception:
            pass

    return ingested


async def poll_gmail_forever():
    """Background task: poll all configured Gmail accounts indefinitely."""
    print("[Gmail] Poller started.")
    while True:
        config = sources_config.load_config()
        accounts = config.get("gmail", [])

        for i, account in enumerate(accounts):
            if not account.get("email") or not account.get("app_password"):
                continue
            try:
                count = await asyncio.get_event_loop().run_in_executor(
                    None, poll_account, account
                )
                accounts[i]["is_connected"] = True
                accounts[i]["error"] = None
                accounts[i]["last_polled_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                accounts[i]["messages_fetched"] = accounts[i].get("messages_fetched", 0) + count
                if count:
                    print(f"[Gmail] Ingested {count} message(s) from {account['email']}")
            except imaplib.IMAP4.error as e:
                accounts[i]["is_connected"] = False
                accounts[i]["error"] = f"Auth failed: {str(e)}"
                print(f"[Gmail] Auth error for {account['email']}: {e}")
            except Exception as e:
                accounts[i]["is_connected"] = False
                accounts[i]["error"] = str(e)
                print(f"[Gmail] Error for {account['email']}: {e}")

        config["gmail"] = accounts
        sources_config.save_config(config)
        await asyncio.sleep(POLL_INTERVAL)
