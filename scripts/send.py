"""Send the email edition.

Primary: Resend API (branded sender, requires a verified domain + RESEND_API_KEY).
Fallback: Gmail SMTP (requires GMAIL_USER + GMAIL_APP_PASSWORD).

Recipients come from the SUBSCRIBERS env var (comma-separated) or
subscribers.txt (one per line, gitignored).
"""

import json
import os
import smtplib
import sys
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
RESEND_API_URL = "https://api.resend.com/emails"


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
    """One individual email per subscriber (better deliverability + privacy)."""
    api_key = os.environ["RESEND_API_KEY"]
    sent, failed = 0, []
    for recipient in subscribers:
        payload = {
            "from": f"{config.SENDER_NAME} <{config.SENDER_EMAIL}>",
            "to": [recipient],
            "subject": subject,
            "html": html,
            "text": text,
            "reply_to": config.REPLY_TO,
            "headers": {
                "List-Unsubscribe": f"<mailto:{config.UNSUBSCRIBE_TO}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
        }
        req = urllib.request.Request(
            RESEND_API_URL,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": "Bearer " + api_key,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                r.read()
            sent += 1
        except urllib.error.HTTPError as e:
            failed.append(f"{recipient}: {e.code} {e.read().decode()[:200]}")
    if failed:
        raise SystemExit("send failures:\n" + "\n".join(failed))
    print(f"sent via Resend to {sent} subscriber(s)")


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
