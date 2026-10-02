"""Production deployment contract for the Django storefront."""

This project intentionally keeps the QR payment workflow:

1. Customer scans the existing QR and pays the displayed total.
2. Customer places the order.
3. Customer sends the transaction reference/screenshot on WhatsApp or optionally
   uploads the screenshot on the order page.
4. Staff verifies the payment in the dashboard/admin and confirms the order.

Do not replace this with an automated payment gateway without a separate payment
security review.

## Production configuration

Set environment variables outside the repository:

```text
DEBUG=False
SECRET_KEY=<long random value>
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DATABASE
# Himalayan Host MySQL alternative:
# DATABASE_URL=mysql://USER:PASSWORD@localhost:3306/DATABASE
ALLOWED_HOSTS=nismitacraftstudio.com,www.nismitacraftstudio.com
CORS_ALLOWED_ORIGINS=https://admin.example.com
CSRF_TRUSTED_ORIGINS=https://shop.example.com
TRUST_PROXY_HEADERS=true  # only when behind a trusted HTTPS reverse proxy
WHATSAPP_NUMBER=977XXXXXXXXX
SHIPPING_FLAT=150
DATABASE_CONN_MAX_AGE=60
DATABASE_CONNECT_TIMEOUT=5
```

## SEO configuration

Canonical, Open Graph, sitemap and JSON-LD URLs are always built from the
canonical domain — they are never generated from the incoming request host:

```text
SEO_CANONICAL_DOMAIN=nismitacraftstudio.com
SEO_SITE_URL=https://nismitacraftstudio.com
# Keep false in production. Only enable for a local preview tunnel.
SEO_ALLOW_DEV_HOSTS=false
```

* `SEO_CANONICAL_DOMAIN` must be the **non-www** host. `www.` is permanently
  redirected to it by `storefront.middleware.CanonicalDomainMiddleware`, and
  is added to `ALLOWED_HOSTS` automatically so the redirect can be served
  instead of a 400.
* The web server (or Cloudflare) should additionally 301 `http://` to
  `https://`; Django's `SECURE_SSL_REDIRECT` does this when `DEBUG=False`.
* Do not set `SEO_ALLOW_DEV_HOSTS=true` on the production host: it would let a
  local request host leak into canonical URLs.

`DATABASE_URL` is required when `DEBUG=False`; production cannot silently fall
back to SQLite. Use a managed PostgreSQL database with automated backups.

## Release commands

```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy
python manage.py test tests
python manage.py test storefront   # SEO regression suite
```

Serve with a production WSGI/ASGI server behind HTTPS. Do not use Django's
`runserver` in production. Configure the web server to:

- Serve `staticfiles/` with long-lived immutable caching.
- Serve product images from `media/products/`.
- Keep `media/payment_screenshots/` private; do not expose payment screenshots
  as public static files. Stream them only through an authenticated staff route
  or a private object-storage bucket.
- Block dotfiles, source files, `.env`, and backup files.
- Forward the client IP and the original HTTPS protocol only from a trusted proxy.
- Set request/body/upload limits at the proxy as an additional layer.
## Automated deployment

Since this commit, `git push origin main` deploys automatically: CI runs the
test suite first, and only a green build is released to the server over SSH.

See **[CI_CD.md](CI_CD.md)** for the one-time setup (deploy key, repository
secrets, server authorisation) and troubleshooting.

Quick reference:

```bash
git push origin main                                   # CI, then auto-deploy
```

## Release commands

## Health checks

- `GET /healthz/` checks that the Django process is alive.
- `GET /readyz/` checks database connectivity and returns HTTP 503 when the DB
  is unavailable.

## Operations

- Keep `.env`, `db.sqlite3`, `media/`, `logs/`, and `staticfiles/` out of source
  control; the repository `.gitignore` already excludes them.
- Back up PostgreSQL and the media volume/bucket regularly.
- Configure centralized logs, uptime monitoring, error reporting, dependency
  updates, and disk/database alerts before accepting real orders.
- Rotate `SECRET_KEY` only with a planned session invalidation strategy.
- Rotate admin credentials and payment/QR account details when staff changes.
