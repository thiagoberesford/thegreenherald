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
(several days old at most, already filtered to today's window) and recent academic papers.

Compose today's edition. Rules:
- Pick ONE lead story: the most important of the window. Write a headline, a one-line deck, \
and exactly 2 short paragraphs (2-3 sentences each). Quotes are welcome if present in the item.
- For each section ({sections}): pick the {stories_per_section} strongest items. Write headline, \
short italic deck (optional, may be empty), and a 2-3 sentence body for each.
- "Big Tech & Cloud" section: pick the {bigtech_stories} strongest items about {companies} \
and sustainability/climate/data centres. Headline + 2-3 sentence body each. Also write one \
"briefs" line mentioning notable other company items (or state there were none).
- Papers: select the {papers_n} most relevant from the list. Keep title, authors, journal, url, date exactly as given. \
If the papers list is empty, return an empty papers array.
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

    # compact the raw items for the prompt
    items = []
    for n in raw["news"]:
        items.append({
            "section": n["section"], "title": n["title"], "source": n["source"],
            "url": n["link"], "date": n["date"][:16],
        })
    payload = json.dumps({"news": items, "papers": raw["papers"]})

    prompt = PROMPT.format(
        brand=config.BRAND,
        sections=", ".join(config.SECTIONS),
        stories_per_section=config.STORIES_PER_SECTION,
        bigtech_n=len(config.BIGTECH_STORIES) if isinstance(config.BIGTECH_STORIES, list) else config.BIGTECH_STORIES,
        bigtech_stories=config.BIGTECH_STORIES,
        companies=", ".join(config.BIGTECH_COMPANIES),
        papers_n=config.PAPERS_PER_EDITION,
    )

    content = call_mistral(prompt, payload)
    edition = json.loads(content)
    edition["meta"] = {
        "brand": config.BRAND,
        "date": raw["fetched_at"][:10],
        "window_start": raw["window_start"],
        "window_close": raw["window_close"],
    }
    (OUT / "edition.json").write_text(json.dumps(edition, indent=1))
    print("edition composed:", edition.get("lead", {}).get("title", "?"))


if __name__ == "__main__":
    main()
