#!/usr/bin/env python3
"""
QQ Mail Manager - IMAP/SMTP client for QQ邮箱

Usage:
    python3 qqmail.py inbox [--limit N] [--folder FOLDER]
    python3 qqmail.py read --index N [--folder FOLDER]
    python3 qqmail.py send --to ADDR --subject SUBJ --body BODY [--attachment PATH]
    python3 qqmail.py search [--subject KW] [--from ADDR] [--since DATE] [--limit N]
    python3 qqmail.py folders

Environment:
    QQMAIL_USER       QQ email address (e.g. 123456789@qq.com)
    QQMAIL_AUTH_CODE   Authorization code (授权码, NOT QQ password)
"""

import argparse
import email
import email.header
import email.utils
import imaplib
import io
import os
import smtplib
import ssl
import sys
from datetime import datetime
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Fix Windows console encoding for Chinese characters
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# QQ Mail server config
IMAP_SERVER = "imap.qq.com"
IMAP_PORT = 993
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465

# Max chars for email preview in inbox listing
PREVIEW_MAX_CHARS = 200


def get_credentials():
    """Read credentials from environment variables."""
    user = os.environ.get("QQMAIL_USER", "").strip()
    auth_code = os.environ.get("QQMAIL_AUTH_CODE", "").strip()
    if not user:
        print("ERROR: QQMAIL_USER environment variable not set.")
        print("Set it to your QQ email address, e.g.: export QQMAIL_USER=123456789@qq.com")
        sys.exit(1)
    if not auth_code:
        print("ERROR: QQMAIL_AUTH_CODE environment variable not set.")
        print("Get an authorization code (授权码) from QQ Mail settings:")
        print("  mail.qq.com → 设置 → 账户 → IMAP/SMTP服务 → 生成授权码")
        sys.exit(1)
    return user, auth_code


def decode_header_value(raw):
    """Decode an email header value (handles encoded words like =?UTF-8?B?...?=)."""
    if raw is None:
        return ""
    parts = email.header.decode_header(raw)
    decoded = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return "".join(decoded)


def get_email_body(msg):
    """Extract plain text body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        # Fallback: try text/html if no plain text
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/html" and "attachment" not in disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return f"[HTML content]\n{payload.decode(charset, errors='replace')}"
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return "[No text content]"


def connect_imap():
    """Connect and authenticate to QQ Mail IMAP server."""
    user, auth_code = get_credentials()
    try:
        context = ssl.create_default_context()
        conn = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, ssl_context=context)
        conn.login(user, auth_code)
        return conn
    except imaplib.IMAP4.error as e:
        print(f"ERROR: IMAP login failed: {e}")
        print("Check your QQMAIL_USER and QQMAIL_AUTH_CODE.")
        print("Make sure IMAP is enabled in QQ Mail settings.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Cannot connect to {IMAP_SERVER}:{IMAP_PORT}: {e}")
        sys.exit(1)


def cmd_folders(_args):
    """List all mail folders."""
    conn = connect_imap()
    try:
        status, folders = conn.list()
        if status != "OK":
            print("ERROR: Failed to list folders.")
            return
        print("Mail Folders:")
        print("-" * 40)
        for folder_raw in folders:
            if isinstance(folder_raw, bytes):
                folder_str = folder_raw.decode("utf-8", errors="replace")
            else:
                folder_str = str(folder_raw)
            # Parse folder name from IMAP response like: (\\Noselect \\HasChildren) "/" "INBOX"
            parts = folder_str.rsplit('"', 2)
            if len(parts) >= 2:
                folder_name = parts[-2]
            else:
                folder_name = folder_str
            print(f"  {folder_name}")
    finally:
        conn.logout()


def cmd_inbox(args):
    """Read recent emails from inbox (or specified folder)."""
    limit = args.limit or 10
    folder = args.folder or "INBOX"

    conn = connect_imap()
    try:
        status, _ = conn.select(folder, readonly=True)
        if status != "OK":
            print(f'ERROR: Cannot open folder "{folder}".')
            print("Use 'qqmail.py folders' to list available folders.")
            return

        status, messages = conn.search(None, "ALL")
        if status != "OK":
            print("ERROR: Search failed.")
            return

        msg_ids = messages[0].split()
        if not msg_ids:
            print(f"No emails in {folder}.")
            return

        # Get the most recent N emails
        recent_ids = msg_ids[-limit:]
        recent_ids.reverse()  # newest first

        print(f"Recent emails in {folder} (showing {len(recent_ids)} of {len(msg_ids)}):")
        print("=" * 70)

        for i, msg_id in enumerate(recent_ids, 1):
            status, data = conn.fetch(msg_id, "(RFC822.HEADER)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(data[0][1])

            from_addr = decode_header_value(msg.get("From", ""))
            subject = decode_header_value(msg.get("Subject", "(no subject)"))
            date_str = msg.get("Date", "")
            date_parsed = email.utils.parsedate_to_datetime(date_str) if date_str else None
            date_display = date_parsed.strftime("%Y-%m-%d %H:%M") if date_parsed else date_str

            print(f"\n[{i}] {subject}")
            print(f"    From: {from_addr}")
            print(f"    Date: {date_display}")
    finally:
        conn.logout()


def cmd_read(args):
    """Read a specific email by index (1-based, from newest)."""
    index = args.index
    folder = args.folder or "INBOX"

    conn = connect_imap()
    try:
        status, _ = conn.select(folder, readonly=True)
        if status != "OK":
            print(f'ERROR: Cannot open folder "{folder}".')
            return

        status, messages = conn.search(None, "ALL")
        if status != "OK":
            print("ERROR: Search failed.")
            return

        msg_ids = messages[0].split()
        if not msg_ids:
            print(f"No emails in {folder}.")
            return

        # Index 1 = newest
        if index < 1 or index > len(msg_ids):
            print(f"ERROR: Index {index} out of range (1-{len(msg_ids)}).")
            return

        target_id = msg_ids[-index]
        status, data = conn.fetch(target_id, "(RFC822)")
        if status != "OK":
            print("ERROR: Failed to fetch email.")
            return

        msg = email.message_from_bytes(data[0][1])

        from_addr = decode_header_value(msg.get("From", ""))
        to_addr = decode_header_value(msg.get("To", ""))
        subject = decode_header_value(msg.get("Subject", "(no subject)"))
        date_str = msg.get("Date", "")
        date_parsed = email.utils.parsedate_to_datetime(date_str) if date_str else None
        date_display = date_parsed.strftime("%Y-%m-%d %H:%M:%S") if date_parsed else date_str

        body = get_email_body(msg)

        # List attachments
        attachments = []
        if msg.is_multipart():
            for part in msg.walk():
                disposition = str(part.get("Content-Disposition", ""))
                if "attachment" in disposition:
                    filename = decode_header_value(part.get_filename() or "unnamed")
                    attachments.append(filename)

        print("=" * 70)
        print(f"Subject: {subject}")
        print(f"From:    {from_addr}")
        print(f"To:      {to_addr}")
        print(f"Date:    {date_display}")
        if attachments:
            print(f"Attachments: {', '.join(attachments)}")
        print("-" * 70)
        print(body)
        print("=" * 70)
    finally:
        conn.logout()


def cmd_send(args):
    """Send an email via SMTP."""
    user, auth_code = get_credentials()

    to_addr = args.to
    subject = args.subject
    body = args.body
    attachment_path = args.attachment

    # Build message
    if attachment_path:
        msg = MIMEMultipart()
        msg.attach(MIMEText(body, "plain", "utf-8"))

        if not os.path.isfile(attachment_path):
            print(f"ERROR: Attachment file not found: {attachment_path}")
            sys.exit(1)

        filename = os.path.basename(attachment_path)
        with open(attachment_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        email.encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)
    else:
        msg = MIMEText(body, "plain", "utf-8")

    msg["From"] = user
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(user, auth_code)
            server.sendmail(user, [to_addr], msg.as_string())
        print(f"OK: Email sent to {to_addr}")
        print(f"  Subject: {subject}")
        if attachment_path:
            print(f"  Attachment: {os.path.basename(attachment_path)}")
    except smtplib.SMTPAuthenticationError as e:
        print(f"ERROR: SMTP authentication failed: {e}")
        print("Check your QQMAIL_USER and QQMAIL_AUTH_CODE.")
        print("Make sure SMTP is enabled in QQ Mail settings.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to send email: {e}")
        sys.exit(1)


def cmd_search(args):
    """Search emails by subject, sender, or date."""
    limit = args.limit or 20
    folder = args.folder or "INBOX"

    # Build IMAP search criteria
    criteria = []
    if args.subject:
        criteria.append(f'SUBJECT "{args.subject}"')
    if getattr(args, "from", None):
        criteria.append(f'FROM "{getattr(args, "from")}"')
    if args.since:
        try:
            date_obj = datetime.strptime(args.since, "%Y-%m-%d")
            date_imap = date_obj.strftime("%d-%b-%Y")
            criteria.append(f"SINCE {date_imap}")
        except ValueError:
            print(f"ERROR: Invalid date format '{args.since}'. Use YYYY-MM-DD.")
            sys.exit(1)

    if not criteria:
        print("ERROR: Specify at least one search criterion: --subject, --from, or --since")
        sys.exit(1)

    search_str = " ".join(criteria)

    conn = connect_imap()
    try:
        status, _ = conn.select(folder, readonly=True)
        if status != "OK":
            print(f'ERROR: Cannot open folder "{folder}".')
            return

        status, messages = conn.search(None, search_str)
        if status != "OK":
            print("ERROR: Search failed.")
            return

        msg_ids = messages[0].split()
        if not msg_ids:
            print(f"No emails matching: {search_str}")
            return

        # Show most recent matches
        recent_ids = msg_ids[-limit:]
        recent_ids.reverse()

        print(f"Search results ({len(recent_ids)} of {len(msg_ids)} matches):")
        print(f"Criteria: {search_str}")
        print("=" * 70)

        for i, msg_id in enumerate(recent_ids, 1):
            status, data = conn.fetch(msg_id, "(RFC822.HEADER)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(data[0][1])

            from_addr = decode_header_value(msg.get("From", ""))
            subject = decode_header_value(msg.get("Subject", "(no subject)"))
            date_str = msg.get("Date", "")
            date_parsed = email.utils.parsedate_to_datetime(date_str) if date_str else None
            date_display = date_parsed.strftime("%Y-%m-%d %H:%M") if date_parsed else date_str

            print(f"\n[{i}] {subject}")
            print(f"    From: {from_addr}")
            print(f"    Date: {date_display}")
    finally:
        conn.logout()


def main():
    parser = argparse.ArgumentParser(
        description="QQ Mail Manager - read, send, search emails via IMAP/SMTP"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # inbox
    p_inbox = subparsers.add_parser("inbox", help="Read recent emails")
    p_inbox.add_argument("--limit", type=int, default=10, help="Number of emails to show (default: 10)")
    p_inbox.add_argument("--folder", type=str, default="INBOX", help="Mail folder (default: INBOX)")

    # read
    p_read = subparsers.add_parser("read", help="Read a specific email")
    p_read.add_argument("--index", type=int, required=True, help="Email index (1=newest)")
    p_read.add_argument("--folder", type=str, default="INBOX", help="Mail folder (default: INBOX)")

    # send
    p_send = subparsers.add_parser("send", help="Send an email")
    p_send.add_argument("--to", required=True, help="Recipient email address")
    p_send.add_argument("--subject", required=True, help="Email subject")
    p_send.add_argument("--body", required=True, help="Email body text")
    p_send.add_argument("--attachment", help="Path to attachment file")

    # search
    p_search = subparsers.add_parser("search", help="Search emails")
    p_search.add_argument("--subject", help="Search by subject keyword")
    p_search.add_argument("--from", dest="from", help="Search by sender address")
    p_search.add_argument("--since", help="Search since date (YYYY-MM-DD)")
    p_search.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    p_search.add_argument("--folder", type=str, default="INBOX", help="Mail folder (default: INBOX)")

    # folders
    subparsers.add_parser("folders", help="List mail folders")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "inbox": cmd_inbox,
        "read": cmd_read,
        "send": cmd_send,
        "search": cmd_search,
        "folders": cmd_folders,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
