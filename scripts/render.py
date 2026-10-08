"""Render out/edition.json into:
  - docs/YYYY-MM-DD.html        (web edition, interactive puzzle)
  - out/email.html              (email edition, static puzzle + play-online link)
  - docs/index.html             (archive page)

No third-party dependencies.
"""

import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
import puzzles as puzzles_lib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
DOCS = ROOT / "docs"
TZ = ZoneInfo(config.TIMEZONE)


def esc(s):
    return html.escape(s or "", quote=True)


CSS = """
  @page { size: A4 portrait; margin: 8mm; }
  body { font-family: "Times New Roman", Times, Georgia, serif; background: #ffffff; color: #111; margin: 0; padding: 12px; }
  a { color: inherit; text-decoration: none; }
  .pcell { width: 24px; height: 24px; border: 0; text-align: center; font-family: "Times New Roman", Times, Georgia, serif; font-size: 13px; font-weight: 700; text-transform: uppercase; padding: 0; margin: 0; outline: none; background: transparent; display: block; }
  .pcell:focus { background: #fdf6d8; }
  .pnum { position: absolute; top: 0; left: 2px; font-size: 6px; color: #666; line-height: 1; }
"""

SCRIPT = """
<script>
(function () {
  var cells = Array.prototype.slice.call(document.querySelectorAll('.pcell'));
  if (!cells.length) return;
  cells.forEach(function (c, i) {
    c.addEventListener('input', function () {
      c.value = c.value.toUpperCase().replace(/[^A-Z]/g, '');
      if (c.value && i < cells.length - 1) cells[i + 1].focus();
    });
    c.addEventListener('keydown', function (e) {
      if (e.key === 'Backspace' && !c.value && i > 0) {
        cells[i - 1].focus(); cells[i - 1].value = ''; e.preventDefault();
      }
    });
  });
  var check = document.getElementById('pcheck');
  if (check) check.addEventListener('click', function () {
    cells.forEach(function (c) {
      if (!c.value) return;
      c.style.background = (c.value === c.getAttribute('data-sol')) ? '#d9f2d9' : '#f6d9d9';
    });
  });
  var clear = document.getElementById('pclear');
  if (clear) clear.addEventListener('click', function () {
    cells.forEach(function (c) { c.value = ''; c.style.background = 'transparent'; });
    cells[0].focus();
  });
})();
</script>
"""


# ---------- building blocks ----------

def src_line(story):
    src = story.get("source") or "Wire"
    url = story.get("source_url") or ""
    date = story.get("source_date") or ""
    label = f'<a href="{esc(url)}" target="_blank" style="color:#1a3d6e;">{esc(src)}</a>' if url else esc(src)
    extra = f" — {esc(date)}" if date else ""
    return f'<div style="font-size:8.5px;color:#666;margin-top:2px;">Source: {label}{extra}</div>'


def story_block(s, first=False):
    parts = ['<div style="margin-bottom:6px;"' if first else
             '<div style="border-top:1px dotted #999;padding-top:5px;margin-top:6px;margin-bottom:6px;"']
    parts.append(">")
    parts.append(f'<a href="{esc(s.get("source_url", ""))}" target="_blank" '
                 f'style="font-size:12px;font-weight:700;line-height:1.12;color:#111;">{esc(s["title"])}</a>')
    deck = s.get("deck") or ""
    if deck:
        parts.append(f'<div style="font-size:9px;font-style:italic;color:#444;margin:1px 0 2px 0;">{esc(deck)}</div>')
    parts.append(f'<div style="font-size:10.5px;line-height:1.35;text-align:justify;margin-top:2px;">{esc(s["body"])}</div>')
    parts.append(src_line(s))
    parts.append("</div>")
    return "".join(parts)


def grid_columns(sections):
    tds = []
    for i, sec in enumerate(sections):
        pad_left = "padding:7px 10px 0 0;" if i == 0 else (
            "padding:7px 10px 0 10px;" if i < len(sections) - 1 else "padding:7px 0 0 10px;")
        border = "border-right:1px solid #bbb;" if i < len(sections) - 1 else ""
        stories = "".join(story_block(s, first=(j == 0)) for j, s in enumerate(sec["stories"]))
        tds.append(
            f'<td width="{100 // len(sections)}%" valign="top" style="{pad_left}{border}">'
            f'<div style="font-size:9px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;'
            f'text-align:center;border-bottom:2px solid #111;padding-bottom:1px;margin-bottom:5px;">{esc(sec["label"])}</div>'
            f"{stories}</td>"
        )
    return "<tr>" + "".join(tds) + "</tr>"


def bigtech_band(bt):
    stories = bt.get("stories", [])
    if not stories:
        return ""
    n = max(1, len(stories))
    story_tds = []
    for i, s in enumerate(stories):
        border = "border-right:1px solid #999;" if i < n - 1 else ""
        pad = "padding-right:12px;" if i == 0 else ("padding:0 12px;" if i < n - 1 else "padding-left:12px;")
        story_tds.append(
            f'<td width="{100 // n}%" valign="top" style="{pad}{border}">'
            f'<a href="{esc(s.get("source_url", ""))}" target="_blank" '
            f'style="font-size:11.5px;font-weight:700;line-height:1.12;color:#111;">{esc(s["title"])}</a>'
            f'<div style="font-size:10.5px;line-height:1.35;text-align:justify;margin-top:2px;">{esc(s["body"])}</div>'
            f"{src_line(s)}</td>"
        )
    briefs = bt.get("briefs") or ""
    if re.match(r"^\s*(no\b|none\b|nothing\b|no other\b|no material\b)", briefs, re.I):
        briefs = ""
    briefs_html = (f'<div style="font-size:8.5px;color:#555;font-style:italic;margin-top:4px;">{esc(briefs)}</div>'
                   if briefs.strip() else "")
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;margin-top:7px;">'
        '<tr><td style="border:1.5px solid #111;background:#f0f0f0;padding:6px 10px;">'
        '<div style="font-size:9px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;'
        'text-align:center;border-bottom:1.5px solid #111;padding-bottom:1px;margin-bottom:2px;">Big Tech, Cloud and AI</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;"><tr>' + "".join(story_tds) + "</tr></table>"
        f"{briefs_html}</td></tr></table>"
    )


def agenda_band(items):
    """Compact band of upcoming events until the end of the quarter."""
    if not items:
        return ""
    rows = []
    n = len(items)
    for i, a in enumerate(items[:4]):
        border = "border-bottom:1px dotted #bbb;" if i < n - 1 and i < 3 else ""
        where = f", {esc(a.get('where', ''))}" if a.get("where") else ""
        src = a.get("source") or ""
        src_html = (f' <span style="font-size:8px;color:#666;">(<a href="{esc(a.get("source_url", ""))}" '
                    f'target="_blank" style="color:#1a3d6e;">{esc(src)}</a>)</span>') if src else ""
        rows.append(
            f'<div style="{border}padding:2px 0;font-size:9.5px;line-height:1.35;">'
            f'<b>{esc(a["event"])}</b> &mdash; {esc(a.get("when", ""))}{where}{src_html}</div>'
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;margin-top:7px;">'
        '<tr><td style="border-top:2px solid #111;padding:4px 0 1px 0;">'
        '<div style="font-size:9px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;'
        'text-align:center;border-bottom:1px solid #111;padding-bottom:1px;margin-bottom:2px;">'
        'On the Agenda &mdash; Sustainability Events This Quarter</div>'
        + "".join(rows) + "</td></tr></table>"
    )


def papers_rows(papers):
    if not papers:
        return ('<tr><td style="padding:3px 0;font-size:9px;line-height:1.3;color:#555;'
                'font-style:italic;">No new sustainability papers indexed in today&rsquo;s window.</td></tr>')
    rows = []
    n = len(papers)
    for i, p in enumerate(papers):
        border = "border-bottom:1px dotted #bbb;" if i < n - 1 else ""
        rows.append(
            f'<tr><td style="{border}padding:2px 0;font-size:10.5px;line-height:1.35;">'
            f'<a href="{esc(p["url"])}" target="_blank" style="font-weight:700;color:#111;">{esc(p["title"])}</a>'
            f' &mdash; {esc(p.get("authors", ""))} &middot; '
            f'<a href="{esc(p["url"])}" target="_blank" style="color:#1a3d6e;">{esc(p.get("journal", ""))}</a>'
            f', {esc(p.get("date", ""))}</td></tr>'
        )
    return "".join(rows)


def puzzle_html(pz):
    size = pz["size"]
    nums = pz["numbers"]
    sol = pz["solution"]
    blacks = pz["blacks"]
    rows = []
    for r in range(1, size + 1):
        cells = []
        for c in range(1, size + 1):
            if (r, c) in blacks:
                cells.append('<td style="width:26px;height:26px;border:1px solid #111;background:#222;">&nbsp;</td>')
                continue
            num = nums.get((r, c))
            num_html = f'<span class="pnum">{num}</span>' if num else ""
            letter = sol[r - 1][c - 1]
            cells.append(
                f'<td style="width:26px;height:26px;border:1px solid #111;position:relative;">{num_html}'
                f'<input type="text" class="pcell" maxlength="1" data-sol="{letter}"></td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    grid = ('<table role="presentation" cellpadding="0" cellspacing="0" '
            'style="border-collapse:collapse;margin:0 auto;">' + "".join(rows) + "</table>")

    across = "".join(f"{num}. {esc(clue)}<br>" for num, clue in pz["clues"]["across"])
    down = "".join(f"{num}. {esc(clue)}<br>" for num, clue in pz["clues"]["down"])
    buttons = (
        '<div style="text-align:center;margin-top:5px;">'
        '<button id="pcheck" type="button" style="font-family:inherit;font-size:8px;letter-spacing:1px;'
        'text-transform:uppercase;border:1px solid #111;background:#ffffff;padding:2px 8px;cursor:pointer;">Check</button>'
        '<button id="pclear" type="button" style="font-family:inherit;font-size:8px;letter-spacing:1px;'
        'text-transform:uppercase;border:1px solid #111;background:#ffffff;padding:2px 8px;cursor:pointer;margin-left:4px;">Clear</button>'
        "</div>"
    )
    return grid, across, down, buttons


def build_web_html(ed, date_str):
    lead = ed["lead"]
    meta = ed["meta"]
    weekday = datetime.fromisoformat(meta["date"]).strftime("%A, %B %-d, %Y")
    pz = puzzles_lib.puzzle_for_date(datetime.strptime(date_str, "%Y-%m-%d").date())
    grid, across, down, buttons = puzzle_html(pz)
    joke = ed.get("joke", {})

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(config.BRAND)} — {esc(weekday)}</title>
<style>{CSS}</style>
</head>
<body>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:720px;margin:0 auto;background:#ffffff;border:1px solid #d9d9d9;padding:18px 24px;border-collapse:collapse;">
<tr><td>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-bottom:1px solid #111;border-collapse:collapse;">
    <tr>
      <td style="font-size:8.5px;letter-spacing:.5px;text-transform:uppercase;">Advocating a liveable planet since 2026</td>
      <td align="right" style="font-size:8.5px;letter-spacing:.5px;text-transform:uppercase;">Delivered daily at 06:00 (Europe/Lisbon)</td>
    </tr>
  </table>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
    <tr><td align="center" style="padding:5px 0 3px 0;">
      <span style="font-size:36px;font-weight:700;letter-spacing:1px;line-height:1;color:#556B2F;">{esc(config.BRAND)}</span><br>
      <div style="font-size:9.5px;letter-spacing:2.5px;text-transform:uppercase;color:#444;margin-top:3px;">{esc(config.MASTHEAD_KICKER)}</div>
      <span style="font-style:italic;font-size:10px;color:#333;">&ldquo;{esc(config.TAGLINE)}&rdquo;</span>
    </td></tr>
  </table>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:3px double #111;border-bottom:3px double #111;border-collapse:collapse;">
    <tr>
      <td style="font-size:8.5px;text-transform:uppercase;letter-spacing:.8px;padding:3px 0;">{esc(weekday)}</td>
      <td align="right" style="font-size:8.5px;text-transform:uppercase;letter-spacing:.8px;padding:3px 0;">Vol. 1</td>
    </tr>
  </table>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
    <tr><td align="center" style="padding:6px 20px 2px 20px;">
      <a href="{esc(lead.get('source_url', ''))}" target="_blank" style="font-size:22px;font-weight:700;line-height:1.08;color:#111;">{esc(lead["title"])}</a>
      <div style="font-style:italic;font-size:10.5px;color:#222;margin-top:3px;">{esc(lead.get("deck", ""))}</div>
    </td></tr>
    <tr><td style="padding:4px 0 0 0;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="8" style="border-collapse:separate;">
        <tr>
          <td width="50%" valign="top" style="font-size:10.5px;line-height:1.35;text-align:justify;border-right:1px solid #ccc;padding-right:12px;">{esc(lead["para1"])}</td>
          <td width="50%" valign="top" style="font-size:10.5px;line-height:1.35;text-align:justify;">{esc(lead["para2"])}</td>
        </tr>
      </table>
    </td></tr>
    <tr><td align="right" style="font-size:8.5px;color:#666;letter-spacing:.3px;padding-top:1px;">{src_line(lead)[5:-5]}</td></tr>
  </table>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #111;border-collapse:collapse;margin-top:8px;">
    {grid_columns(ed["sections"])}
  </table>
  {bigtech_band(ed["bigtech"])}
  {agenda_band(ed.get("agenda", []))}
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:2px solid #111;border-collapse:collapse;margin-top:7px;">
    <tr><td>
      <div style="font-size:9px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;text-align:center;border-bottom:2px solid #111;padding:3px 0 1px 0;margin-bottom:4px;">From the Journals — Papers Published This Week</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">{papers_rows(ed["papers"])}</table>
    </td></tr>
  </table>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:2px solid #111;border-collapse:collapse;margin-top:7px;">
    <tr>
      <td width="32%" valign="top" style="padding:4px 12px 0 0;border-right:1px solid #bbb;">
        <div style="font-size:9px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;text-align:center;border-bottom:2px solid #111;padding-bottom:1px;margin-bottom:4px;">Joke of the Day</div>
        <div style="font-size:11px;line-height:1.4;font-style:italic;text-align:justify;">{esc(joke.get("setup", ""))}<br><br>{esc(joke.get("punchline", ""))}</div>
        <div style="font-size:8.5px;color:#777;margin-top:4px;">(Groans welcome. Better jokes: reply to this email.)</div>
      </td>
      <td width="68%" valign="top" style="padding:4px 0 0 12px;" id="puzzle">
        <div style="font-size:9px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;text-align:center;border-bottom:2px solid #111;padding-bottom:1px;margin-bottom:4px;">Daily Puzzle — Sustainability Mini-Crossword</div>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
          <tr>
            <td width="40%" valign="top">{grid}{buttons}
              <div style="font-size:8px;color:#777;text-align:center;margin-top:2px;">Type your answers, or print and solve with a pen &middot; Answers in tomorrow's edition</div>
            </td>
            <td width="60%" valign="top" style="padding-left:12px;font-size:9px;line-height:1.4;">
              <b>ACROSS</b><br>{across}<br><b>DOWN</b><br>{down}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:3px double #111;border-collapse:collapse;margin-top:7px;">
    <tr>
      <td style="font-size:8px;color:#555;letter-spacing:.4px;padding-top:3px;">Compiled automatically &middot; Papers via Semantic Scholar (Scopus/DOI/arXiv records)</td>
      <td align="right" style="font-size:8px;color:#555;letter-spacing:.4px;padding-top:3px;">Reply to this email &middot; Unsubscribe anytime</td>
    </tr>
  </table>
</td></tr>
</table>
{SCRIPT}
</body>
</html>
"""


def to_email_html(web_html, edition_url):
    """Static email edition: strip inputs/script, replace buttons with play-online link."""
    out = re.sub(r'<input type="text" class="pcell" maxlength="1" data-sol="[A-Z]">', "", web_html)
    out = out.replace(
        "  .pcell { width: 24px; height: 24px; border: 0; text-align: center; font-family: \"Times New Roman\", Times, Georgia, serif; font-size: 13px; font-weight: 700; text-transform: uppercase; padding: 0; margin: 0; outline: none; background: transparent; display: block; }\n", "")
    out = out.replace("  .pcell:focus { background: #fdf6d8; }\n", "")
    out = out.replace("  .pnum { position: absolute; top: 0; left: 2px; font-size: 6px; color: #666; line-height: 1; }\n", "")
    out = re.sub(r'<div style="text-align:center;margin-top:5px;">.*?</div>',
                 f'<div style="text-align:center;margin-top:5px;">'
                 f'<a href="{edition_url}" target="_blank" style="font-size:8.5px;font-weight:700;'
                 f'letter-spacing:1px;text-transform:uppercase;color:#1a3d6e;text-decoration:underline;">'
                 f'Play this puzzle online &rarr;</a></div>', out, flags=re.S)
    out = out.replace("Type your answers, or print and solve with a pen &middot; Answers in tomorrow's edition",
                      "Solve with a pen, or play the interactive version online &middot; Answers in tomorrow's edition")
    out = re.sub(r"<script>.*?</script>\s*", "", out, flags=re.S)
    return out


def build_archive(existing_editions):
    items = "".join(
        f'<li><a href="{d}.html">{d}</a> &mdash; <a href="{d}.html#puzzle">puzzle</a></li>'
        for d in sorted(existing_editions, reverse=True)
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>{esc(config.BRAND)}</title>
<style>body{{font-family:"Times New Roman",Georgia,serif;max-width:720px;margin:40px auto;padding:0 16px;color:#111}}
h1{{font-size:32px;border-bottom:3px double #111;padding-bottom:6px}}li{{margin:4px 0}}
a{{color:#1a3d6e}}</style></head>
<body><h1>{esc(config.BRAND)}</h1>
<p>The one-page daily sustainability newspaper. Latest editions:</p>
<ul>{items}</ul></body></html>
"""


def normalize_title(t):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (t or "").lower())).strip()


def record_history(ed, date_str):
    """Append this edition's published URLs/titles to data/published.json so
    future fetches never repeat them."""
    hist_path = ROOT / "data" / "published.json"
    try:
        hist = json.loads(hist_path.read_text()) if hist_path.exists() else {}
    except json.JSONDecodeError:
        hist = {}
    urls, titles = set(), set()

    def add(url, title):
        if url:
            urls.add(url)
        if title:
            titles.add(normalize_title(title))

    lead = ed.get("lead", {})
    add(lead.get("source_url"), lead.get("title"))
    for sec in ed.get("sections", []):
        for s in sec.get("stories", []):
            add(s.get("source_url"), s.get("title"))
    for s in ed.get("bigtech", {}).get("stories", []):
        add(s.get("source_url"), s.get("title"))
    for a in ed.get("agenda", []):
        add(a.get("source_url"), a.get("event"))
    for p in ed.get("papers", []):
        add(p.get("url"), p.get("title"))

    hist[date_str] = {"urls": sorted(urls), "titles": sorted(t for t in titles if t)}
    hist = dict(sorted(hist.items())[-config.HISTORY_KEEP_EDITIONS:])
    hist_path.parent.mkdir(exist_ok=True)
    hist_path.write_text(json.dumps(hist, indent=1))


def main():
    ed = json.loads((OUT / "edition.json").read_text())
    date_str = ed["meta"]["date"]
    web = build_web_html(ed, date_str)
    DOCS.mkdir(exist_ok=True)
    (DOCS / f"{date_str}.html").write_text(web)

    edition_url = f"{config.EDITION_URL_BASE}/{date_str}.html#puzzle"
    email = to_email_html(web, edition_url)
    (OUT / "email.html").write_text(email)

    record_history(ed, date_str)

    editions = sorted(p.stem for p in DOCS.glob("*.html") if p.stem != "index")
    (DOCS / "index.html").write_text(build_archive(editions))
    print(f"rendered: docs/{date_str}.html | out/email.html | archive: {len(editions)} editions "
          f"| history recorded for {date_str}")


if __name__ == "__main__":
    main()
