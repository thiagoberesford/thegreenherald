"""Noon watchdog: if today's edition is missing by ~12:30 Lisbon, alert the owner.

Runs hourly from ~12:30 Lisbon. GitHub's scheduler delays triggers
unpredictably, so this is dense scheduling with a dedupe marker: the first
run to land after a missed edition sends the alert and commits
data/alerts/YYYY-MM-DD.txt; subsequent runs see the marker and stay silent.
A manual "Run workflow" in the afternoon still prints today's edition.
"""

import os
import smtplib
import sys
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

ROOT = Path(__file__).resolve().parents[1]


def main():
    now = datetime.now(config.LISBON_TZ)
    date_str = now.strftime("%Y-%m-%d")
    edition_file = ROOT / "docs" / f"{date_str}.html"
    markers = ROOT / "data" / "alerts"

    if edition_file.exists():
        print(f"watchdog: edition {date_str} present; all good")
        return

    marker = markers / f"{date_str}.txt"
    if marker.exists():
        print(f"watchdog: edition {date_str} missing, but alert already sent today")
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

    # dedupe marker + prune, committed so all future runs see it
    markers.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"alerted {now.isoformat()}\n")
    cutoff = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    for m in markers.glob("*.txt"):
        if m.stem < cutoff:
            m.unlink()
    if os.environ.get("GITHUB_ACTIONS") == "true":
        os.system('git config user.name "green-herald-bot"')
        os.system('git config user.email "actions@users.noreply.github.com"')
        os.system("git add data/alerts/")
        os.system('git diff --cached --quiet || '
                  '(git commit -m "Watchdog alert ' + date_str + '" && '
                  'git pull --rebase -X theirs origin main && git push)')


if __name__ == "__main__":
    main()
