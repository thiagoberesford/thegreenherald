"""Send the email edition.

Primary: Resend SMTP (branded sender, requires a verified domain + RESEND_API_KEY).
Fallback: Gmail SMTP (requires GMAIL_USER + GMAIL_APP_PASSWORD).

Recipients come from the SUBSCRIBERS env var (comma-separated) or
subscribers.txt (one per line, gitignored).
"""

import json
import os
import smtplib
import sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"


def load_subscribers():
    env = os.environ.get("SUBSCRIBERS", "")
    if env:
        return [s.strip() for s in env.split(",") if s.strip()]
    path = ROOT / "subscribers.txt"
    if path.exists():
        return [line.strip() for line in path.read_text().splitlines()
                if line.strip() and not line.startswith("#")]
    return []


def send_via_resend(subscribers, subject, html, text):
    """Resend SMTP (smtp.resend.com) — avoids Cloudflare's HTTP bot filter
    on api.resend.com, which blocks Python's TLS signature with error 1010."""
    import smtplib
    from email.message import EmailMessage
    from email.utils import formatdate, make_msgid

    sent, failed = 0, []
    with smtplib.SMTP("smtp.resend.com", 587) as s:
        s.starttls()
        s.login("resend", os.environ["RESEND_API_KEY"])
        for recipient in subscribers:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = f"{config.SENDER_NAME} <{config.SENDER_EMAIL}>"
            msg["To"] = recipient
            msg["Reply-To"] = config.REPLY_TO
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = make_msgid(domain=config.DOMAIN)
            msg["List-Unsubscribe"] = f"<mailto:{config.UNSUBSCRIBE_TO}>"
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
            msg.set_content(text)
            msg.add_alternative(html, subtype="html")
            try:
                s.send_message(msg)
                sent += 1
            except smtplib.SMTPException as e:
                failed.append(f"{recipient}: {e}")
    if failed:
        raise SystemExit("send failures:\n" + "\n".join(failed))
    print(f"sent via Resend SMTP to {sent} subscriber(s)")


def send_via_gmail(subscribers, subject, html, text):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ["GMAIL_USER"]
    msg["To"] = os.environ["GMAIL_USER"]          # sender; recipients hidden in BCC
    msg["Reply-To"] = config.REPLY_TO
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=config.DOMAIN)
    msg["List-Unsubscribe"] = f"<mailto:{config.UNSUBSCRIBE_TO}>"
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    msg["Bcc"] = ", ".join(subscribers)

    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"])
        s.send_message(msg)
    print(f"sent via Gmail SMTP to {len(subscribers)} subscriber(s) (BCC)")


def main():
    subscribers = load_subscribers()
    if not subscribers:
        print("no subscribers configured; skipping send")
        return

    meta = json.loads((OUT / "edition.json").read_text())["meta"]
    date_str = meta["date"]
    subject = f"{config.BRAND} — {date_str} edition"
    html = (OUT / "email.html").read_text()
    text = (f"{config.BRAND} — {date_str} edition.\n"
            f"View online: {config.EDITION_URL_BASE}/{date_str}.html\n\n"
            f"To unsubscribe, email {config.UNSUBSCRIBE_TO}.")

    if os.environ.get("RESEND_API_KEY"):
        send_via_resend(subscribers, subject, html, text)
    elif os.environ.get("GMAIL_USER") and os.environ.get("GMAIL_APP_PASSWORD"):
        send_via_gmail(subscribers, subject, html, text)
    else:
        raise SystemExit("no sender configured: set RESEND_API_KEY "
                         "or GMAIL_USER + GMAIL_APP_PASSWORD")


if __name__ == "__main__":
    main()
