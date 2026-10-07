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

To send from `editor@thegreenherald.com` instead of Gmail (better deliverability
at scale), sign up for Resend and add the SPF/DKIM/DMARC records it provides;
then swap `scripts/send.py` for a Resend API call. The domain work above stays
unchanged.
