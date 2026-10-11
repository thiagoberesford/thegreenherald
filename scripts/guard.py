"""Time guard for scheduled runs. Manual runs always pass.

Scheduled runs are accepted from 05:00 to 11:59 Lisbon: GitHub's free-tier
scheduler can delay cron triggers by hours, so a late trigger still prints
the edition (catch-up) instead of skipping it. The published-edition check
prevents double sends when several delayed triggers go through.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

ROOT = Path(__file__).resolve().parents[1]


def decision(now, edition_already_published):
    """Returns (run: bool, reason: str)."""
    if now.hour < config.SEND_HOUR_LOCAL - 1:
        return False, f"too early ({now:%H:%M}, the edition trigger starts at 05:00)"
    if now.hour >= 12:
        return False, f"too late for a catch-up ({now:%H:%M}; next edition is tomorrow)"
    if edition_already_published:
        return False, "today's edition is already published"
    return True, "go"


def main():
    if os.environ.get("GUARD_BYPASS") == "1":
        print("GUARD_BYPASS=1: running regardless of time")
        return
    if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        print("Manual run: skipping time guard (scheduled runs are still guarded)")
        return

    now = datetime.now(ZoneInfo(config.TIMEZONE))
    edition_day = config.get_time_windows(now)["edition_day"]
    edition_file = ROOT / "docs" / f"{edition_day:%Y-%m-%d}.html"
    ok, reason = decision(now, edition_file.exists())
    if not ok:
        print(f"Skipping this scheduled trigger: {reason}.")
        sys.exit(78)
    print(f"Go for {now:%Y-%m-%d %H:%M} {config.TIMEZONE} "
          f"(edition {edition_day:%Y-%m-%d})")


if __name__ == "__main__":
    main()
