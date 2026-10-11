"""Noon watchdog: if today's edition is missing by ~12:30 Lisbon, alert the owner.

Runs after the catch-up window closes (noon), so it only fires when the
edition is genuinely missed — not merely late. A manual "Run workflow" in
the afternoon still prints today's edition (dated today, today's news).
"""

import os
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

ROOT = Path(__file__).resolve().parents[1]


def main():
    now = datetime.now(config.LISBON_TZ)
    date_str = now.strftime("%Y-%m-%d")
    edition_file = ROOT / "docs" / f"{date_str}.html"

    if edition_file.exists():
        print(f"watchdog: edition {date_str} present; all good")
        return

    print(f"watchdog: edition {date_str} MISSING at {now:%H:%M} Lisbon")

    to = (os.environ.get("ALERT_EMAIL", "").strip()
          or os.environ.get("SUBSCRIBERS", "").split(",")[0].strip())
    if not to:
        print("no alert recipient (ALERT_EMAIL/SUBSCRIBERS); logging only")
        return

    msg = EmailMessage()
    msg["Subject"] = f"[The Green Herald] Edition {date_str} is missing"
    msg["From"] = f"{config.SENDER_NAME} Watchdog <{config.SENDER_EMAIL}>"
    msg["To"] = to
    msg.set_content(
        f"Today's edition ({date_str}) has not been published by noon Lisbon.\n\n"
        f"Check the runs: https://github.com/thiagoberesford/thegreenherald/actions\n"
        f"Likely cause: a very late GitHub cron trigger, or a failed run.\n"
        f"Fix: open the Actions tab and click 'Run workflow' - an afternoon\n"
        f"run still prints today's edition with today's news.\n\n"
        f"-- The Green Herald watchdog"
    )

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        print(f"no RESEND_API_KEY; cannot send. ALERT TEXT: {msg['Subject']}")
        return
    with smtplib.SMTP("smtp.resend.com", 587) as s:
        s.starttls()
        s.login("resend", api_key)
        s.send_message(msg)
    print(f"alert sent to {to}")


if __name__ == "__main__":
    main()
