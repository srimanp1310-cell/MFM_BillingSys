# Deployment to Railway

## Pre-deployment (already done)

- Dev database reset to a clean state; schema builds from migrations alone
- Real shop details (Murali Furniture Mall) baked in as defaults — invoices
  print correctly on a fresh database, editable later in Admin → Settings
- `Procfile` runs `flask db upgrade` automatically before starting gunicorn,
  so migrations apply on every deploy
- `.env.example` documents every variable; production requirements slimmed
- Security audit passed (CSRF on all POST forms, auth on all private routes,
  hashed passwords, no hardcoded secrets, ORM-only queries, secure cookies)
- 26 automated tests + full manual workflow verified

## Steps to deploy (you do these)

### 1. Push to GitHub

Create an empty **private** repository on GitHub (e.g. `mfm-billing`), then:

```bash
git remote add origin https://github.com/<your-username>/mfm-billing.git
git push -u origin main
```

### 2. Create the Railway project

- Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
- Authorize Railway and pick the repository
- Railway detects Python, installs `requirements.txt`, and uses the `Procfile`

### 3. Add PostgreSQL

- In the project canvas: **+ New** → **Database** → **PostgreSQL**
- Then on the **app service** → Variables → **Add Variable Reference** →
  select `DATABASE_URL` from the Postgres service. (postgres:// URLs are
  normalized automatically by the app.)

### 4. Set environment variables (app service → Variables)

```
SECRET_KEY=<run locally: python -c "import secrets; print(secrets.token_hex(32))">
SECURE_COOKIES=1
FLASK_APP=wsgi.py
TIMEZONE=Asia/Kolkata
VAPID_PUBLIC_KEY=<from: flask gen-vapid>
VAPID_PRIVATE_KEY=<from: flask gen-vapid>
VAPID_CLAIM_EMAIL=mailto:srimanp1310@gmail.com
```

Notes:
- Do **not** set `FLASK_DEBUG` in production.
- The app refuses to start in production without a real `SECRET_KEY`.
- The VAPID keys enable low-stock push notifications; run `flask gen-vapid`
  locally once and paste both values.

### 5. First deploy + admin user

Migrations run automatically on deploy (see `Procfile`). Once the deploy is
green, create the admin account with the Railway CLI:

```bash
railway login
railway link          # pick the project + app service
railway run flask seed-admin --username admin
# you'll be prompted for a password — pick a strong one
```

(No `--password` flag on the command line keeps it out of shell history.)

### 6. Generate the public domain

- App service → **Settings** → **Networking** → **Generate Domain**
- You'll get e.g. `mfm-billing-production.up.railway.app` (HTTPS automatic)

### 7. Install on staff phones (PWA)

1. Open the URL in Chrome (Android) or Safari (iPhone)
2. Android: tap the **"Install app" / "Add to Home screen"** prompt.
   iPhone: Share button → **Add to Home Screen**
3. The app opens fullscreen with the MFM icon, like a native app
4. Staff register via **"Register here"** on the login page; you approve them
   in **Admin → Users**
5. Tap the **bell icon** in the app to enable low-stock notifications

## Backups (set up on day one)

Billing data is irreplaceable. Two layers:

1. **Railway's built-in backups**: Postgres service → **Backups** tab →
   enable daily backups.
2. **Off-site dump (recommended)**: run `scripts/backup.sh` daily from any
   machine with the Railway CLI:
   ```bash
   railway run --service <postgres-service> bash -c 'pg_dump "$DATABASE_URL"' | gzip > backup_$(date +%F).sql.gz
   ```
   or schedule `scripts/backup.sh` with `DATABASE_URL` set to the **public**
   connection string from the Postgres service's Connect tab.

## Ongoing

- Every `git push` to `main` auto-redeploys (~1–2 min); migrations run first
- Logs: app service → **Deployments** → latest → **View Logs**
  (the app logs to stdout — no log files to manage)
- Costs: Hobby plan $5/month includes usage credit; this app + Postgres
  typically stays within it
