# Deploy the crop recommendation project

## Run locally

Use Python 3.12. From the repository root:

```sh
python -m venv .venv
# Windows Command Prompt:
.venv\Scripts\activate.bat
pip install -r backend/requirements.txt
python app.py
```

Open http://127.0.0.1:5000. Flask serves the static frontend locally. The frontend initializes its session through /api/session before enabling sign-in.

## Render backend

1. In Render, select New > Web Service and connect this GitHub repository. Grant access to the private repository if prompted.
2. Choose branch main and Python runtime. Leave Root Directory empty (the repository root).
3. Build command: `pip install -r backend/requirements.txt`.
4. Start command: `gunicorn --workers 1 --bind 0.0.0.0:$PORT 'backend.app:create_app()'`.
5. Set PYTHON_VERSION to 3.12.8. Set SECRET_KEY to a random secret generated locally with `python -c "import secrets; print(secrets.token_hex(32))"`. Do not commit that value.
6. Set COOKIE_SECURE=1 and DATABASE_PATH=/var/data/users.sqlite3.
7. Select a paid instance supporting a persistent disk, attach a disk mounted at /var/data, and deploy. Only files under the mount persist. Do not use /var/data without configuring the disk.
8. Set Health Check Path to /health. Check that https://YOUR-SERVICE.onrender.com/health returns {"status":"ok"}.
9. Save the service URL for the next step.

SQLite accounts require this persistent disk. For a temporary free demo only, omit DATABASE_PATH and the disk; accounts and sessions can disappear on restart/redeployment. For durable free hosting, use the PostgreSQL backend described below.

## Render with PostgreSQL (recommended for free tier)

Render's free instances have ephemeral file systems, so SQLite data is lost on every deploy/restart. PostgreSQL is the recommended backend for persistent accounts on the free tier.

### Setup

1. In Render, create a **New PostgreSQL** database (free tier is sufficient for a demo).
2. Copy the **Internal Database URL** from the PostgreSQL dashboard (starts with `postgresql://` or `postgres://`).
3. Create a **New Web Service** for the Flask backend. Set the environment variables:
   - `DATABASE_URL` — paste the Internal Database URL from step 2.
   - `SECRET_KEY` — a random secret: `python -c "import secrets; print(secrets.token_hex(32))"`.
   - `COOKIE_SECURE=1` — required for HTTPS.
   - `TRUSTED_PROXY=1` — enables proxy-aware rate limiting (see below).
4. Build command: `pip install -r backend/requirements.txt`.
5. Start command: `gunicorn --workers 1 --bind 0.0.0.0:$PORT 'backend.app:create_app()'`.
6. Set PYTHON_VERSION to 3.12.8. Deploy.
7. The app auto-creates tables on first startup. No manual migration is needed.

When `DATABASE_URL` is set, the app ignores `DATABASE_PATH` and uses PostgreSQL for all account, session, and rate-limit storage. When `DATABASE_URL` is **not** set, the app falls back to SQLite — no configuration changes are needed for local development.

### Proxy-aware rate limiting (`TRUSTED_PROXY`)

When deployed behind a reverse proxy (Vercel → Render), the backend sees the proxy's IP for every request. Set `TRUSTED_PROXY=1` so the rate limiter reads the original client IP from the `X-Forwarded-For` header (leftmost entry).

> **Security:** Never set `TRUSTED_PROXY=1` when the app is directly internet-facing. An attacker can spoof `X-Forwarded-For` to bypass rate limiting. Only enable it when a trusted edge proxy (Vercel, Cloudflare, etc.) controls the header.

## Vercel frontend

1. In frontend/vercel.json replace both occurrences of https://YOUR-RENDER-SERVICE.onrender.com with your actual Render service URL. Keep the paths following the hostname intact. Commit and push this edit.
2. In Vercel, choose Add New > Project and import this repository.
3. Set Framework Preset to Other and Root Directory to frontend.
4. Leave Build Command empty; set Output Directory to `.` if the interface requires a value. No frontend package installation is needed.
5. Deploy and open the assigned HTTPS URL.
6. Create a new test account, predict rice using 90,42,43,20.5,82,6.5,200, refresh, log out, and sign in again.

The Vercel rewrites proxy /api/* and /predict to Render. Requests remain same-origin from the browser's perspective, avoiding cross-site cookie/CORS configuration. The /login path serves index.html. Static images are served by Vercel. API responses are marked no-store.

Render may see Vercel's proxy IP instead of the original browser IP. Set `TRUSTED_PROXY=1` on the Render service to enable proxy-aware rate limiting (see the PostgreSQL section above). Never blindly trust arbitrary X-Forwarded-For values without this explicit opt-in.

## Testing and retraining

```sh
pip install -r requirements-dev.txt
python -m pytest -q
npm ci
python tests/run_ui.py
python backend/train.py
```

The DOM integration test uses a temporary database. It is not visual browser QA. Run the notebook from notebooks/; experiments write to evaluation/ and trained artifacts to backend/models/.

## Folder map

- frontend/: static HTML UI, images, Vercel rewrite configuration.
- backend/: Flask authentication/inference, requirements and training script.
- backend/models/: trusted model, scaler and label encoder.
- backend/data/: supplied training CSV.
- tests/: API and DOM integration tests.
- evaluation/: recorded metrics and confusion matrix.
- docs/: faculty requirements and submission checklist.
- notebooks/: interactive entry point to training.
- legacy/: unused files retained from the original project; not needed for deployment.

Original project: https://github.com/jahnaviveeramallu/Crop-Recommendation-System. Dataset/image attribution still needs confirmation from the team.

References: https://render.com/docs/deploy-flask ; https://render.com/docs/disks ; https://vercel.com/docs/rewrites
