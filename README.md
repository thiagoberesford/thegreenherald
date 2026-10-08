# The Green Herald

A one-page daily sustainability newspaper (Folha de Sao Paulo / The Times style),
generated automatically every morning and emailed at 06:00 Europe/Lisbon.

News window: yesterday 00:00 -> today 05:00 Lisbon (closes one hour before send).

## What's inside

- Lead story + the 3 strongest themes of the day (from 7 candidate sections in `config.py`)
- Big Tech, Cloud and AI watch: SAP, Microsoft, Amazon, Google, IBM, OpenAI, Anthropic, Meta, Nvidia, Apple, Tesla, ByteDance, Alibaba
- On the Agenda: upcoming sustainability events until the end of the quarter
- From the Journals: latest sustainability papers (Semantic Scholar, 7-day lookback, with abstracts)
- Joke of the day
- Daily mini-crossword: interactive on the web edition, printable in the email,
  with a "Play online" link pointing at the web edition
- No-repeat memory: stories, events and papers published in recent editions never reappear
  (registry kept in `data/published.json`)

## Pipeline

```
05:00 Lisbon  scripts/guard.py         (skips the wrong DST cron trigger)
              scripts/fetch_sources.py Google News RSS + Semantic Scholar -> out/raw.json
              scripts/compose.py       Mistral API curates + writes -> out/edition.json
              scripts/render.py       docs/YYYY-MM-DD.html + out/email.html + archive
              scripts/send.py         Gmail SMTP -> subscribers (BCC)
              commit + push docs/     -> published on GitHub Pages
06:00 Lisbon  email lands
```

Zero third-party Python dependencies. Runs on the GitHub Actions free tier.

## Setup

1. **Create the GitHub repo** (public, so Pages + Actions are free) and push
   this directory to `main`.
2. **Subscribers:** copy `subscribers.txt.example` to `subscribers.txt` and add
   your team's emails, one per line.
3. **Secrets and variables** (repo Settings -> Secrets and variables -> Actions):
   - `RESEND_API_KEY` — primary sender. Create an account at https://resend.com,
     add + verify the domain `thegreenherald.com` (records in `DNS.md`, step 5),
     then create an API key.
   - `SUBSCRIBERS` (variable, not secret) — comma-separated recipient emails;
     each subscriber gets an individual email.
   - `MISTRAL_API_KEY` — from https://console.mistral.ai (La Plateforme)
   - Optional Gmail fallback (`GMAIL_USER` + `GMAIL_APP_PASSWORD` from
     https://myaccount.google.com/apppasswords, requires 2FA): used only if
     `RESEND_API_KEY` is missing.
4. **GitHub Pages:** Settings -> Pages -> Deploy from branch `main` / `/docs`,
   then set the custom domain per `DNS.md`.
5. **Cloudflare DNS:** follow `DNS.md`.
6. **Test run:** Actions tab -> "Daily edition" -> Run workflow. The time guard
   blocks manual runs outside 05:00 Lisbon; for a test run add a temporary
   repository variable or set `GUARD_BYPASS` (see `scripts/guard.py`). The first
   edition takes ~2 minutes.

## Configuration

Everything lives in `config.py`: sections and their news queries, tracked
companies, papers query, counts, LLM model, timezone, send hour.

## Adding crossword puzzles

`puzzles.py` holds hand-verified mini-crosswords, rotated by day-of-year.
Each puzzle must have consistent row/column crossings. To add one:
1. Design a 5x5 grid with 4 black cells (pattern in the existing puzzle).
2. Fill `solution`, `blacks`, `numbers`, `clues`.
3. Verify: every word's letters match at all crossings.

The LLM writes the joke and stories; the crossword stays hand-verified so it
is always actually solvable.

## Costs

- GitHub Actions + Pages: free (public repo)
- Google News RSS + Semantic Scholar: free
- Mistral: free tier / Pro credits (~1-2 EUR/mo at most at this volume)
- Resend: free tier, branded sender via the verified domain (100 emails/day)
- Gmail SMTP fallback: free (limit 500 recipients/day)
- Domain: ~10 EUR/year (the only real cost)

## Notes

- Email rendering: the pipeline generates a table-based, email-safe layout;
  the interactive puzzle lives only on the web edition (email clients strip JS).
- Legal: keep the unsubscribe footer; bulk mail needs a real opt-out and a
  postal address in many jurisdictions.
