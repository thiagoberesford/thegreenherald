"""Fetch raw news and papers for today's edition.

Outputs JSON to out/raw.json. No third-party dependencies.
"""

import email.utils
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
TZ = ZoneInfo(config.TIMEZONE)


def now_local():
    return datetime.now(TZ)


def window_bounds():
    """Window: yesterday 00:00 -> today (send hour - WINDOW_CLOSES_BEFORE_SEND_H) local."""
    now = now_local()
    close = now.replace(hour=config.SEND_HOUR_LOCAL - config.WINDOW_CLOSES_BEFORE_SEND_H,
                        minute=0, second=0, microsecond=0)
    start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, close


def rss_query_url(query):
    return ("https://news.google.com/rss/search?q="
            + urllib.parse.quote(query) + "&hl=en-US&gl=US&ceid=US:en")


def fetch_rss(query):
    req = urllib.request.Request(rss_query_url(query), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    root = ET.fromstring(data)
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        source = (item.findtext("source") or "").strip()
        # Google News titles end with " - Publisher"
        publisher = source or (title.rsplit(" - ", 1)[-1] if " - " in title else "")
        try:
            date = email.utils.parsedate_to_datetime(pub).astimezone(TZ)
        except (TypeError, ValueError):
            continue
        items.append({
            "title": title, "link": link, "source": publisher,
            "date": date.isoformat(), "timestamp": date.timestamp(),
        })
    return items


def collect_news(queries, label):
    start, close = window_bounds()
    seen, items = set(), []
    for q in queries:
        for it in fetch_rss(q)[:config.RSS_ITEMS_PER_QUERY]:
            key = (it["title"][:80], it["link"])
            if key in seen or not (start.timestamp() <= it["timestamp"] <= close.timestamp()):
                continue
            seen.add(key)
            it["section"] = label
            it["title"] = it["title"].rsplit(" - ", 1)[0] if " - " in it["title"] else it["title"]
            items.append(it)
    return items


def fetch_papers():
    start, _ = window_bounds()
    year = start.year
    url = ("https://api.semanticscholar.org/graph/v1/paper/search/bulk"
           "?query=" + urllib.parse.quote(config.PAPER_QUERY)
           + "&sort=publicationDate:desc"
           + "&fields=" + urllib.parse.quote(config.PAPER_FIELDS)
           + f"&year={year}-{year}")
    req = urllib.request.Request(url, headers={"User-Agent": "TheGreenHerald/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    papers = []
    cutoff = (start - timedelta(days=1)).date()
    for p in data.get("data", []):
        pub = p.get("publicationDate")
        if not pub:
            continue
        if datetime.strptime(pub, "%Y-%m-%d").date() < cutoff:
            continue
        doi = (p.get("externalIds") or {}).get("DOI")
        if not doi:
            continue
        papers.append({
            "title": p["title"],
            "authors": ", ".join(a["name"] for a in (p.get("authors") or [])[:4]),
            "journal": p.get("venue") or "",
            "date": pub,
            "url": "https://doi.org/" + doi,
            "doi": doi,
        })
        if len(papers) >= 20:
            break
    return papers


def main():
    OUT.mkdir(exist_ok=True)
    raw = {"fetched_at": now_local().isoformat(),
           "window_start": window_bounds()[0].isoformat(),
           "window_close": window_bounds()[1].isoformat()}

    all_news = []
    for label, queries in config.SECTIONS.items():
        all_news.extend(collect_news(queries, label))
    leads = collect_news(config.LEAD_QUERIES, "Lead")
    for q in config.BIGTECH_QUERIES:
        all_news.extend(collect_news([q], "Big Tech & Cloud"))

    # dedupe across sections (same link), keep first
    seen, deduped = set(), []
    for it in all_news + leads:
        if it["link"] in seen:
            continue
        seen.add(it["link"])
        deduped.append(it)
    deduped.sort(key=lambda x: -x["timestamp"])

    raw["news"] = deduped
    raw["papers"] = fetch_papers()
    (OUT / "raw.json").write_text(json.dumps(raw, indent=1))
    print(f"news items: {len(deduped)} | papers: {len(raw['papers'])}")
    print(f"window: {raw['window_start']} -> {raw['window_close']}")


if __name__ == "__main__":
    main()
