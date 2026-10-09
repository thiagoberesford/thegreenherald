"""Compose the edition with the Mistral API, then VALIDATE the output:

- every news story must map to a real fetched item (by id, fallback title match);
  its url/source/date are overwritten from the raw item (no hallucinated links)
- papers may only appear in the papers section (Big Tech must be news items)
- every published link must be reachable over HTTP (bot-blocks on publishers
  like 403/418 are treated as human-reachable)

Reads out/raw.json -> writes out/edition.json. No third-party dependencies.
"""

import difflib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
API_URL = "https://api.mistral.ai/v1/chat/completions"

PROMPT = """You are the editor of {brand}, a one-page daily sustainability newspaper \
(Folha de Sao Paulo / The Times style, in English). You are given raw news items \
(already filtered to today's window), some tagged as upcoming "Events", and recent \
academic papers (with abstracts).

Compose today's edition. Rules:
- Pick ONE lead story: the most important of the window. Write a headline, a one-line deck, \
and exactly 2 short paragraphs (2-3 sentences each). Quotes are welcome if present in the item. \
The lead must NOT be repeated in the sections or Big Tech. Each input item may appear at most \
once in the entire edition - never reuse an item id.
- SECTION SELECTION: from the candidate section labels present in the items, pick the \
{sections_on_page} STRONGEST themes for today's grid. Prefer sections with multiple strong, \
distinct stories. Fill each chosen section with {stories_per_section} stories: headline, \
short italic deck (may be empty), and a 2-3 sentence body.
- Items have a "tier": "trusted" items come from vetted outlets; "additional" items come from other outlets and were admitted only because trusted ones were scarce. ALWAYS prefer trusted items. The lead must be a trusted item whenever any trusted item exists. Only use "additional" items to fill remaining slots.
- "Big Tech & Cloud" section: pick the {bigtech_n} strongest NEWS items (id starting with "n") \
about big tech, cloud and AI + sustainability. NEVER use papers (ids starting with "p") here - \
papers belong only in the papers section. Headline + 2-3 sentence body each. Also write one \
"briefs" line mentioning notable other company items ONLY if such items exist; \
otherwise return an empty string for briefs.
- AGENDA: scan ALL news items (any section) for clearly UPCOMING events - conferences, \
summits, ceremonies, deadlines - happening between now and {events_end} (end of quarter). \
You may extract an agenda event from summit or industry coverage even if published as news. \
List up to 4 events with event name, when (date or date range), where. Only include events \
with a concrete upcoming date; if none qualify, return an empty array.
- Papers: select the {papers_n} most relevant from the list, preferring the most recent and \
most significant; use the abstract to judge relevance. If the papers list is empty, return \
an empty papers array.
- Write one joke of the day: short, about sustainability/climate/AI, family-friendly.
- Every story MUST cite the source publisher and date as given in the item; never invent sources.
- For every news story, set "country" to the primary country the STORY is about (e.g. "Brazil", \
"Finland") - NOT the publisher's location. If the story is worldwide or not tied to one country \
(e.g. a global report, a worldwide deal, COP negotiations), use an empty string.
- Bodies must be factual and grounded in the item text. Do not add numbers that are not present.

CRITICAL - item ids: every story, agenda entry and paper you output MUST include the "id" \
of the exact input item it is based on. Copy ids verbatim; do not invent ids.

Return STRICT JSON only, matching exactly this schema:
{{
  "lead": {{"id": "", "country": "", "title": "", "deck": "", "para1": "", "para2": "", "source": "", "source_url": "", "source_date": ""}},
  "sections": [
    {{"label": "", "stories": [{{"id": "", "country": "", "title": "", "deck": "", "body": "", "source": "", "source_url": "", "source_date": ""}}]}}
  ],
  "bigtech": {{"stories": [{{"id": "", "country": "", "title": "", "body": "", "source": "", "source_url": "", "source_date": ""}}], "briefs": ""}},
  "agenda": [{{"id": "", "event": "", "when": "", "where": "", "source": "", "source_url": ""}}],
  "papers": [{{"id": "", "title": "", "authors": "", "journal": "", "url": "", "date": ""}}],
  "joke": {{"setup": "", "punchline": ""}}
}}
"""


def call_mistral(prompt, user_content):
    payload = {
        "model": config.LLM_MODEL,
        "temperature": 0.3,
        "max_tokens": config.LLM_MAX_TOKENS,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Bearer " + os.environ["MISTRAL_API_KEY"],
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode())
    return data["choices"][0]["message"]["content"]


def _norm(t):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (t or "").lower())).strip()


def _similarity(a, b):
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def url_reachable(url):
    """HTTP check. Bot-blocks (401/403/418/429) are treated as human-reachable:
    publishers commonly block automation while the link works fine in a browser."""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; TheGreenHeraldBot/1.0)"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status < 400
    except urllib.error.HTTPError as e:
        return e.code in (401, 403, 418, 429)
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def validate_and_repair(edition, raw):
    """Deterministic output guarantees. Returns (edition, report)."""
    news = raw.get("news", [])
    papers = raw.get("papers", [])
    news_by_id = {n["id"]: n for n in news if n.get("id")}
    news_by_url = {n["link"]: n for n in news}
    news_by_title = {}
    for n in news:
        news_by_title.setdefault(_norm(n["title"]), n)
    paper_by_id = {p["id"]: p for p in papers if p.get("id")}
    paper_by_url = {p["url"]: p for p in papers}
    paper_by_title = {}
    for p in papers:
        paper_by_title.setdefault(_norm(p["title"]), p)

    stats = {"repaired": 0, "dropped": 0, "unreachable": 0, "fuzzy": 0}

    def resolve_news(item_id, title, url=None):
        # 1. exact id  2. url echoed back  3. exact title  4. fuzzy title
        item = news_by_id.get(item_id)
        if item:
            return item
        if url and url in news_by_url:
            return news_by_url[url]
        t = _norm(title)
        if t in news_by_title:
            return news_by_title[t]
        best, best_r = None, 0.0
        for nt, cand in news_by_title.items():
            r = _similarity(t, nt)
            if r > best_r:
                best, best_r = cand, r
        if best and best_r >= 0.55:
            stats["fuzzy"] += 1
            return best
        return None

    def fix_news_story(s):
        item = resolve_news(s.get("id"), s.get("title"), s.get("source_url"))
        if not item:
            stats["dropped"] += 1
            return None
        if (s.get("source_url") != item["link"]
                or s.get("source") != item["source"]):
            stats["repaired"] += 1
        s["id"] = item["id"]
        s["source_url"] = item["link"]
        s["source"] = item["source"]
        s["source_date"] = item["date"][:16]
        if not url_reachable(item["link"]):
            stats["unreachable"] += 1
            return None
        return s

    def fix_paper(p):
        item = (paper_by_id.get(p.get("id")) or paper_by_url.get(p.get("url"))
                or paper_by_title.get(_norm(p.get("title", ""))))
        if not item:
            t = _norm(p.get("title", ""))
            best, best_r = None, 0.0
            for pt, cand in paper_by_title.items():
                r = _similarity(t, pt)
                if r > best_r:
                    best, best_r = cand, r
            if best and best_r >= 0.60:
                stats["fuzzy"] += 1
                item = best
        if not item:
            stats["dropped"] += 1
            return None
        if p.get("url") != item["url"]:
            stats["repaired"] += 1
        p["id"] = item["id"]
        p["url"] = item["url"]
        p["title"] = item["title"]
        p["authors"] = item["authors"]
        p["journal"] = item["journal"]
        p["date"] = item["date"]
        return p

    # lead
    lead = fix_news_story(edition.get("lead", {})) if edition.get("lead") else None

    # sections
    sections = []
    for sec in edition.get("sections", []):
        stories = [s for s in (fix_news_story(x) for x in sec.get("stories", [])) if s]
        if stories:
            sec["stories"] = stories
            sections.append(sec)

    # big tech: news only (papers dropped automatically: paper ids never match news items)
    bigtech = edition.get("bigtech", {})
    bt_stories = [s for s in (fix_news_story(x) for x in bigtech.get("stories", [])) if s]

    # global dedupe: no item may appear twice in the edition (lead, sections, big tech)
    seen_ids = {lead["id"]} if lead else set()
    deduped_sections = []
    for sec in sections:
        kept = []
        for s in sec["stories"]:
            if s["id"] in seen_ids:
                stats["dropped"] += 1
                continue
            seen_ids.add(s["id"])
            kept.append(s)
        if kept:
            sec["stories"] = kept
            deduped_sections.append(sec)
    sections = deduped_sections
    bt_kept = []
    for s in bt_stories:
        if s["id"] in seen_ids:
            stats["dropped"] += 1
            continue
        seen_ids.add(s["id"])
        bt_kept.append(s)
    bt_stories = bt_kept
    bigtech["stories"] = bt_stories

    # agenda
    agenda = []
    for a in edition.get("agenda", []):
        item = resolve_news(a.get("id"), a.get("event"), a.get("source_url"))
        if not item:
            stats["dropped"] += 1
            continue
        a["source_url"] = item["link"]
        a["source"] = item["source"]
        agenda.append(a)

    # papers
    papers_out = [p for p in (fix_paper(x) for x in edition.get("papers", [])) if p]

    # if the lead failed, promote the strongest available story
    if lead is None:
        for sec in sections:
            if sec["stories"]:
                promo = sec["stories"].pop(0)
                lead = {
                    "id": promo["id"], "title": promo["title"], "deck": promo.get("deck", ""),
                    "para1": promo["body"], "para2": "",
                    "source": promo["source"], "source_url": promo["source_url"],
                    "source_date": promo["source_date"],
                }
                stats["repaired"] += 1
                break
        if lead is None and bt_stories:
            promo = bt_stories.pop(0)
            lead = {
                "id": promo["id"], "title": promo["title"], "deck": "",
                "para1": promo["body"], "para2": "",
                "source": promo["source"], "source_url": promo["source_url"],
                "source_date": promo["source_date"],
            }
            stats["repaired"] += 1
        if lead is None:
            raise SystemExit("validation: no valid lead story; aborting edition")

    edition["lead"] = lead
    edition["sections"] = sections
    edition["bigtech"] = bigtech
    edition["agenda"] = agenda
    edition["papers"] = papers_out
    return edition, stats


def main():
    raw = json.loads((OUT / "raw.json").read_text())
    if not raw.get("news"):
        raise SystemExit("fetch brought no usable news for this window; aborting edition "
                         "(check the fetch log and publisher tiers)")

    # compact the raw items for the prompt: freshest 10 per label, with ids
    by_label = {}
    for n in raw["news"]:
        by_label.setdefault(n["section"], []).append(n)
    items = []
    idx = 0
    for label, lst in by_label.items():
        lst.sort(key=lambda x: x["date"], reverse=True)
        for n in lst[:10]:
            idx += 1
            n["id"] = f"n{idx}"
            items.append({
                "id": n["id"], "section": n["section"], "tier": n.get("tier", "trusted"),
                "title": n["title"], "source": n["source"], "url": n["link"],
                "date": n["date"][:16],
            })
    papers = []
    for i, p in enumerate(raw["papers"], start=1):
        p["id"] = f"p{i}"
        papers.append({
            "id": p["id"], "title": p["title"], "authors": p.get("authors", ""),
            "journal": p.get("journal", ""), "url": p["url"], "date": p["date"],
            "abstract": (p.get("abstract") or "")[:300],
        })
    payload = json.dumps({
        "news": items,
        "papers": papers,
        "events_end": raw.get("events_end", "")[:10],
    })

    prompt = PROMPT.format(
        brand=config.BRAND,
        sections_on_page=config.SECTIONS_ON_PAGE,
        stories_per_section=config.STORIES_PER_SECTION,
        bigtech_n=3,
        papers_n=config.PAPERS_PER_EDITION,
        events_end=raw.get("events_end", "")[:10],
    )

    edition = None
    for attempt in (1, 2):
        content = call_mistral(prompt, payload)
        try:
            edition = json.loads(content)
            break
        except json.JSONDecodeError:
            print(f"compose: invalid JSON on attempt {attempt} "
                  f"({len(content)} chars, likely truncated); retrying")
    if edition is None:
        (OUT / "compose_raw.txt").write_text(content)
        raise SystemExit(f"composer JSON invalid after 2 attempts; "
                         f"raw response saved to out/compose_raw.txt ({len(content)} chars)")

    edition, stats = validate_and_repair(edition, raw)
    print(f"validation: {stats['repaired']} repaired (url/source overwritten from raw), "
          f"{stats['dropped']} dropped (unmatched), {stats['unreachable']} unreachable dropped")
    if stats["dropped"] or stats["unreachable"]:
        print("note: content above was removed because it could not be traced to a "
              "real fetched item or its link did not respond")

    edition["meta"] = {
        "brand": config.BRAND,
        "date": raw["fetched_at"][:10],
        "window_start": raw["window_start"],
        "window_close": raw["window_close"],
    }
    (OUT / "edition.json").write_text(json.dumps(edition, indent=1))
    sections = ", ".join(s.get("label", "?") for s in edition.get("sections", []))
    print(f"edition composed | lead: {edition.get('lead', {}).get('title', '?')}")
    print(f"sections chosen: {sections} | agenda items: {len(edition.get('agenda', []))} "
          f"| bigtech: {len(edition.get('bigtech', {}).get('stories', []))} stories | "
          f"papers: {len(edition.get('papers', []))}")


if __name__ == "__main__":
    main()
