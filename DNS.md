# DNS setup — Cloudflare (thegreenherald.com)

Two jobs: point the domain at GitHub Pages (web edition), and set up email
routing (replies). Total time: ~15 minutes.

## 1. GitHub Pages first

In the GitHub repo: **Settings → Pages → Custom domain** → `thegreenherald.com`,
then check **Enforce HTTPS** once the certificate is issued.

## 2. Cloudflare DNS records

In Cloudflare: **thegreenherald.com → DNS → Records**, add:

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | `@` | `185.199.108.153` | **DNS only** (grey cloud) |
| A | `@` | `185.199.109.153` | DNS only |
| A | `@` | `185.199.110.153` | DNS only |
| A | `@` | `185.199.111.153` | DNS only |
| CNAME | `www` | `<your-github-username>.github.io` | DNS only |

Important:
- **Proxy status must be "DNS only" (grey cloud).** GitHub Pages needs to serve
  the SSL certificate itself; Cloudflare's orange-cloud proxy breaks the
  certificate issuance.
- Delete any pre-existing A/CNAME records for `@` or `www` that conflict.

Propagation is usually minutes; the HTTPS certificate can take up to an hour.

## 3. Email routing (replies)

The newsletter is sent from your Gmail address (free tier), with `Reply-To`
and `List-Unsubscribe` pointing at the domain. Route those to your inbox:

In Cloudflare: **Email → Email Routing → Enable** (it creates the needed MX/SPF
records automatically), then add routes:

| Address | Action |
|---------|--------|
| `reply@thegreenherald.com` | Forward to your Gmail |
| `hello@thegreenherald.com` | Forward to your Gmail |
| `unsubscribe@thegreenherald.com` | Forward to your Gmail (you handle removals) |

## 4. Verify

- `https://thegreenherald.com` → archive page listing editions
- `https://thegreenherald.com/2026-10-07.html#puzzle` → the interactive puzzle
- Reply to a sent email → lands in your Gmail via routing

## Later: branded sending (optional upgrade)

~~~SUPERSEDED: branded sending is now the primary method — see the Resend
section in the README and step 5 below.~~

## 5. Branded sending with Resend (recommended)

Now that you own the domain, send as `editor@thegreenherald.com` instead of
from a Gmail address. Free tier: 100 emails/day, 3,000/month.

1. Create an account at https://resend.com
2. Domains -> Add domain: `thegreenherald.com`
3. Resend shows you DNS records (SPF, DKIM, DMARC). Add them in Cloudflare
   exactly as given — the DKIM record name/value comes from the dashboard;
   don't copy them from anywhere else. Proxy status: DNS only.
4. Click Verify in Resend (usually minutes).
5. Create an API key and add it as the repo secret `RESEND_API_KEY`.

`scripts/send.py` uses Resend automatically when `RESEND_API_KEY` is present,
and falls back to Gmail SMTP otherwise.

The email-routing addresses from step 3 (reply@, hello@, unsubscribe@)
stay exactly as configured above.
