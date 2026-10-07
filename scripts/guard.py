"""Time guard: the workflow runs at two cron slots (04:00 and 05:00 UTC) so that
exactly one of them equals 05:00 in Europe/Lisbon across DST changes.
Exits with code 78 (neutral skip) if it is not the 05:00-05:59 local window yet.

Usage in the workflow: run this first; exit code 78 skips the later steps.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

HOUR_TO_RUN = config.SEND_HOUR_LOCAL - 1  # compose at 05:00 for a 06:00 delivery


def main():
    if os.environ.get("GUARD_BYPASS") == "1":
        print("GUARD_BYPASS=1: running regardless of time")
        return
    now = datetime.now(ZoneInfo(config.TIMEZONE))
    if now.hour != HOUR_TO_RUN:
        print(f"Not {HOUR_TO_RUN:02d}:00 in {config.TIMEZONE} yet (now {now:%H:%M}); skipping this trigger.")
        sys.exit(78)
    print(f"Go for {now:%Y-%m-%d %H:%M} {config.TIMEZONE}")


if __name__ == "__main__":
    main()
