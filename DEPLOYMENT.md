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
ALLOWED_HOSTS=shop.example.com
CORS_ALLOWED_ORIGINS=https://admin.example.com
CSRF_TRUSTED_ORIGINS=https://shop.example.com
TRUST_PROXY_HEADERS=true  # only when behind a trusted HTTPS reverse proxy
WHATSAPP_NUMBER=977XXXXXXXXX
SHIPPING_FLAT=150
DATABASE_CONN_MAX_AGE=60
DATABASE_CONNECT_TIMEOUT=5
```

`DATABASE_URL` is required when `DEBUG=False`; production cannot silently fall
back to SQLite. Use a managed PostgreSQL database with automated backups.

## Release commands

```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy
python manage.py test tests
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
