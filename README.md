# MFM Billing & Stock

Internal billing and stock-management web app (installable PWA) for a single
furniture shop. Flask + SQLAlchemy, server-rendered with Bootstrap 5.

**Core guarantee:** billing and stock never drift. Every stock change writes a
`StockMovement` ledger row and updates the product's cached quantity inside one
database transaction. The ledger is the source of truth; an admin "recompute"
utility can rebuild the cache from it at any time.

## Features

- **Billing** — line items, discount, optional tax (% or amount), customer +
  payment method, gap-free sequential bill numbers (`INV-2026-0001`) with
  manual override, A4 print view. Insufficient stock warns but allows
  (negative stock possible by policy).
- **Billing history** — filter by date range, customer/phone, bill number,
  status, product; reprint any bill; admin can void (stock restored) and
  record returns.
- **Stock status** — search/filters, low-stock highlighting + navbar badge,
  per-product movement ledger, admin adjustments with mandatory note.
- **Stock entry** — record purchases against supplier invoices; create new
  products/brands/categories inline (e.g. add "Dining Set" on the fly).
  Categories can track sizes (mattresses) or not (chairs).
- **Roles** — admin (everything) and staff (billing, history, stock, entry).
- **PWA** — installable on phones, offline shell, Web Push low-stock alerts.

## Local development

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows; use bin/activate on Linux/macOS
pip install -r requirements.txt
copy .env.example .env            # then edit SECRET_KEY etc.
flask db upgrade
flask seed-admin                  # creates the admin login
flask gen-vapid                   # optional: paste output into .env for push
flask run
```

Dev database is SQLite at `instance/app.db`. Run tests with `pytest`.

## Deployment (Render or Railway)

Both give HTTPS automatically (required for the PWA) and managed Postgres.

1. Create a **PostgreSQL** instance and copy its connection string.
2. Create a **web service** from this repo.
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn wsgi:app --workers 2` (Railway reads the `Procfile`)
3. Environment variables:
   - `SECRET_KEY` — long random string
   - `DATABASE_URL` — the Postgres URL (postgres:// is auto-normalized)
   - `SECURE_COOKIES=1`
   - `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIM_EMAIL` — from
     `flask gen-vapid` (for push notifications)
4. Run once: `flask db upgrade && flask seed-admin` (Render "release" runs
   `flask db upgrade` automatically via the Procfile release phase).
5. **Backups (day one!):** schedule `scripts/backup.sh` daily via a cron
   job/scheduled service and copy the dump off-server. Billing data is
   irreplaceable.

## Architecture notes

- `app/services/stock_service.py` — the only code path that mutates stock
  (sales, purchases, returns, voids, adjustments, recompute).
- `app/services/billing_service.py` — bill save/void + gap-free numbering via
  a row-locked per-year sequence.
- Bills and purchases are never deleted; bills are voided, products are
  deactivated. Line items snapshot product name and price at sale time.
- All money uses `Decimal` (`Numeric(12,2)` columns).
