"""Time guard for scheduled runs. Manual runs always pass.

Scheduled runs are accepted during Lisbon hours 05-06 (GitHub cron delays
are common and can push the 05:00 trigger well into the next hour), and
only if today's edition has not already been published (double-send
protection when both cron slots get through).
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
    if now.hour not in (config.SEND_HOUR_LOCAL - 1, config.SEND_HOUR_LOCAL):
        return False, f"outside the 05-06 Lisbon window (now {now:%H:%M})"
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
