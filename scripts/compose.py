"""Compose the edition with the Mistral API: pick stories, write summaries, the joke.

Reads out/raw.json -> writes out/edition.json. No third-party dependencies.
"""

import json
import os
import sys
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
and exactly 2 short paragraphs (2-3 sentences each). Quotes are welcome if present in the item.
- SECTION SELECTION: from the candidate section labels present in the items, pick the \
{sections_on_page} STRONGEST themes for today's grid. Prefer sections with multiple strong, \
distinct stories. Fill each chosen section with {stories_per_section} stories: headline, \
short italic deck (may be empty), and a 2-3 sentence body.
- "Big Tech & Cloud" section: pick the {bigtech_n} strongest items about big tech, cloud and \
AI + sustainability (data centres, energy, water, policy). Headline + 2-3 sentence body each. \
Also write one "briefs" line mentioning notable other company items (or state there were none).
- AGENDA: from items tagged "Events", list up to 4 events happening between now and \
{events_end} (end of quarter). For each: event name, when (date or date range), where. \
Only include clearly upcoming events with enough detail. If none qualify, return an empty array.
- Papers: select the {papers_n} most relevant from the list, preferring the most recent and \
most significant; use the abstract to judge relevance. Keep title, authors, journal, url, date \
exactly as given. If the papers list is empty, return an empty papers array.
- Write one joke of the day: short, about sustainability/climate/AI, family-friendly.
- Every story MUST cite the source publisher and date as given in the item; never invent sources.
- Bodies must be factual and grounded in the item text. Do not add numbers that are not present.

Return STRICT JSON only, matching exactly this schema:
{{
  "lead": {{"title": "", "deck": "", "para1": "", "para2": "", "source": "", "source_url": "", "source_date": ""}},
  "sections": [
    {{"label": "", "stories": [{{"title": "", "deck": "", "body": "", "source": "", "source_url": "", "source_date": ""}}]}}
  ],
  "bigtech": {{"stories": [{{"title": "", "body": "", "source": "", "source_url": "", "source_date": ""}}], "briefs": ""}},
  "agenda": [{{"event": "", "when": "", "where": "", "source": "", "source_url": ""}}],
  "papers": [{{"title": "", "authors": "", "journal": "", "url": "", "date": ""}}],
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


def main():
    raw = json.loads((OUT / "raw.json").read_text())

    # compact the raw items for the prompt: freshest 10 per label (bounds input size)
    by_label = {}
    for n in raw["news"]:
        by_label.setdefault(n["section"], []).append(n)
    items = []
    for label, lst in by_label.items():
        lst.sort(key=lambda x: x["date"], reverse=True)
        for n in lst[:10]:
            items.append({
                "section": n["section"], "title": n["title"], "source": n["source"],
                "url": n["link"], "date": n["date"][:16],
            })
    papers = []
    for p in raw["papers"]:
        papers.append({
            "title": p["title"], "authors": p.get("authors", ""),
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

    edition["meta"] = {
        "brand": config.BRAND,
        "date": raw["fetched_at"][:10],
        "window_start": raw["window_start"],
        "window_close": raw["window_close"],
    }
    (OUT / "edition.json").write_text(json.dumps(edition, indent=1))
    sections = ", ".join(s.get("label", "?") for s in edition.get("sections", []))
    print(f"edition composed | lead: {edition.get('lead', {}).get('title', '?')}")
    print(f"sections chosen: {sections} | agenda items: {len(edition.get('agenda', []))}")


if __name__ == "__main__":
    main()
