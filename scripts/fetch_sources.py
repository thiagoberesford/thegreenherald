"""Fetch raw news, events and papers for today's edition.

Outputs JSON to out/raw.json. No third-party dependencies.
"""

import email.utils
import json
import re
import sys
import time
import urllib.error
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
TZ = config.LISBON_TZ


def normalize_title(t):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (t or "").lower())).strip()


def load_recent_history(edition_date):
    """URLs and normalized titles published in the last HISTORY_EDITIONS editions."""
    path = ROOT / "data" / "published.json"
    urls, titles = set(), set()
    if not path.exists():
        return urls, titles
    try:
        hist = json.loads(path.read_text())
    except json.JSONDecodeError:
        return urls, titles
    for ed_date, entry in hist.items():
        try:
            age = (edition_date - datetime.strptime(ed_date, "%Y-%m-%d").date()).days
        except ValueError:
            continue
        if 0 < age <= config.HISTORY_EDITIONS:
            urls.update(entry.get("urls", []))
            titles.update(entry.get("titles", []))
    return urls, titles


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
        publisher = source or (title.rsplit(" - ", 1)[-1] if " - " in title else "")
        try:
            date = email.utils.parsedate_to_datetime(pub).astimezone(TZ)
        except (TypeError, ValueError):
            continue
        items.append({
            "title": title.rsplit(" - ", 1)[0] if " - " in title else title,
            "link": link, "source": publisher,
            "date": date.isoformat(), "timestamp": date.timestamp(),
        })
    return items


def publisher_ok(source_name):
    """Publisher allow/block filter (word-boundary, case-insensitive)."""
    name = (source_name or "").strip()
    if not name:
        return False
    for b in config.PUBLISHERS_BLOCK:
        if re.search(r"\b" + re.escape(b) + r"\b", name, re.I):
            return False
    if config.PUBLISHERS_ALLOW:
        return any(re.search(r"\b" + re.escape(a) + r"\b", name, re.I)
                   for a in config.PUBLISHERS_ALLOW)
    return True


def collect_news(queries, label, start, close):
    """Items published inside the [start, close] window (all outlets)."""
    seen, items = set(), []
    for q in queries:
        for it in fetch_rss(q)[:config.RSS_ITEMS_PER_QUERY]:
            key = (it["title"][:80], it["link"])
            if key in seen or not (start.timestamp() <= it["timestamp"] <= close.timestamp()):
                continue
            seen.add(key)
            it["section"] = label
            items.append(it)
        time.sleep(0.4)
    return items


def split_by_trust(items):
    """Partition into trusted (allow-list) and additional tiers."""
    trusted, additional = [], []
    for it in items:
        if publisher_ok(it["source"]):
            it["tier"] = "trusted"
            trusted.append(it)
        else:
            it["tier"] = "additional"
            additional.append(it)
    if len(trusted) >= config.MIN_TRUSTED_NEWS:
        return trusted, additional, False
    return trusted + additional, additional, True


def fetch_papers(start_ts):
    """Papers from all queries, published within PAPER_MAX_AGE_DAYS; abstracts trimmed."""
    now = datetime.now(TZ)
    cutoff = (now - timedelta(days=config.PAPER_MAX_AGE_DAYS)).date()
    papers, seen = [], set()
    for query in config.PAPER_QUERIES:
        url = ("https://api.semanticscholar.org/graph/v1/paper/search/bulk"
               "?query=" + urllib.parse.quote(query)
               + "&sort=publicationDate:desc"
               + "&fields=" + urllib.parse.quote(config.PAPER_FIELDS)
               + f"&year={now.year}-{now.year}")
        headers = {"User-Agent": "TheGreenHerald/1.0 (mailto:editor@thegreenherald.com)"}
        data = None
        for attempt, delay in enumerate((0, 10, 30), start=1):
            if delay:
                print(f"Semantic Scholar 429 on '{query}'; retry {attempt - 1} in {delay}s")
                time.sleep(delay)
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = json.loads(r.read().decode())
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 3:
                    continue
                print(f"Semantic Scholar unavailable for '{query}' (HTTP {e.code}); skipping")
                data = None
                break
        if data:
            for p in data.get("data", []):
                doi = (p.get("externalIds") or {}).get("DOI")
                pub = p.get("publicationDate")
                if not doi or doi in seen or not pub:
                    continue
                try:
                    pub_date = datetime.strptime(pub, "%Y-%m-%d").date()
                except ValueError:
                    continue
                # lower bound: too old; upper bound: future-dated metadata errors
                if pub_date < cutoff or pub_date > now.date():
                    continue
                seen.add(doi)
                abstract = (p.get("abstract") or "")[:config.SNIPPET_MAX_CHARS]
                papers.append({
                    "title": p["title"],
                    "authors": ", ".join(a["name"] for a in (p.get("authors") or [])[:4]),
                    "journal": p.get("venue") or "",
                    "date": pub,
                    "url": "https://doi.org/" + doi,
                    "doi": doi,
                    "abstract": abstract,
                })
        time.sleep(2)
    papers.sort(key=lambda p: p["date"], reverse=True)
    return papers[:30]


def main():
    OUT.mkdir(exist_ok=True)
    wins = config.get_time_windows()
    raw = {
        "fetched_at": datetime.now(TZ).isoformat(),
        "window_start": wins["news_start"].isoformat(),
        "window_close": wins["news_end"].isoformat(),
        "events_end": wins["events_end"].isoformat(),
    }
    start, close = wins["news_start"], wins["news_end"]

    all_news = []
    for label, queries in config.SECTIONS.items():
        all_news.extend(collect_news(queries, label, start, close))
    all_news.extend(collect_news(config.LEAD_QUERIES, "Lead", start, close))
    all_news.extend(collect_news(config.BIGTECH_QUERIES, "Big Tech & Cloud", start, close))
    events = collect_news(config.EVENTS_QUERIES, "Events", start, close)

    # dedupe across labels (same link), keep first
    seen, deduped = set(), []
    for it in all_news + events:
        if it["link"] in seen:
            continue
        seen.add(it["link"])
        deduped.append(it)
    deduped.sort(key=lambda x: -x["timestamp"])
    events_deduped = [it for it in deduped if it["section"] == "Events"]

    # never repeat what a recent edition already published
    hist_urls, hist_titles = load_recent_history(datetime.now(TZ).date())
    fresh_all = [n for n in deduped
                 if n["link"] not in hist_urls
                 and normalize_title(n["title"]) not in hist_titles]
    fresh, additional, fallback_engaged = split_by_trust(fresh_all)
    papers = [p for p in fetch_papers(start.timestamp())
              if p["url"] not in hist_urls
              and normalize_title(p["title"]) not in hist_titles]

    raw["news"] = fresh
    raw["papers"] = papers
    (OUT / "raw.json").write_text(json.dumps(raw, indent=1))
    n_events = len([n for n in fresh if n["section"] == "Events"])
    n_trusted = len([n for n in fresh if n.get("tier") == "trusted"])
    print(f"news items: {len(fresh)} (of {len(deduped)} in window, "
          f"{len(deduped) - len(fresh_all)} already published) | trusted: {n_trusted} "
          f"| additional: {len(fresh) - n_trusted} | events: {n_events} | papers: {len(papers)}")
    if fallback_engaged and additional:
        dropped = sorted({n["source"] for n in additional})
        print(f"FALLBACK engaged (fewer than {config.MIN_TRUSTED_NEWS} trusted items); "
              f"admitting: {', '.join(dropped[:10])}")
    print(f"window: {raw['window_start']} -> {raw['window_close']} | events until: {raw['events_end']}")


if __name__ == "__main__":
    main()
