"""Send the email edition via Gmail SMTP (free tier). Requires:
  - GMAIL_USER          your Gmail address
  - GMAIL_APP_PASSWORD  an app password (https://myaccount.google.com/apppasswords)
  - subscribers.txt     one email per line (or SUBSCRIBERS env var, comma-separated)
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


def main():
    subscribers = load_subscribers()
    if not subscribers:
        print("no subscribers configured; skipping send")
        return

    meta = json.loads((OUT / "edition.json").read_text())["meta"]
    date_str = meta["date"]
    pretty = f"{date_str} edition"
    html = (OUT / "email.html").read_text()

    msg = EmailMessage()
    msg["Subject"] = f"{config.BRAND} — {pretty}"
    msg["From"] = os.environ["GMAIL_USER"]
    msg["To"] = os.environ["GMAIL_USER"]          # sender; recipients hidden in BCC
    msg["Reply-To"] = f"reply@{config.DOMAIN}"
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=config.DOMAIN)
    msg["List-Unsubscribe"] = f"<mailto:unsubscribe@{config.DOMAIN}?subject=unsubscribe>"
    msg.set_content(f"{config.BRAND} — {pretty}. View online: {config.EDITION_URL_BASE}/{date_str}.html")
    msg.add_alternative(html, subtype="html")
    msg["Bcc"] = ", ".join(subscribers)

    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"])
        s.send_message(msg)
    print(f"sent to {len(subscribers)} subscriber(s)")


if __name__ == "__main__":
    main()
