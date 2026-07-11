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
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env            # then edit SECRET_KEY etc.
flask db upgrade
flask seed-admin                  # creates the admin login
flask gen-vapid                   # optional: paste output into .env for push
flask run
```

Dev database is SQLite at `instance/app.db`. Run tests with `pytest`.

## Deployment

Target host is **Railway** — see [DEPLOYMENT.md](DEPLOYMENT.md) for the full
step-by-step guide (GitHub push, Postgres, env vars, admin seeding, PWA
install on staff phones, and daily backups). Migrations run automatically on
every deploy via the `Procfile`.

## Architecture notes

- `app/services/stock_service.py` — the only code path that mutates stock
  (sales, purchases, returns, voids, adjustments, recompute).
- `app/services/billing_service.py` — bill save/void + gap-free numbering via
  a row-locked per-year sequence.
- Bills and purchases are never deleted; bills are voided, products are
  deactivated. Line items snapshot product name and price at sale time.
- All money uses `Decimal` (`Numeric(12,2)` columns).
