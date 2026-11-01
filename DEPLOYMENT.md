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

SQLite accounts require this persistent disk. For a temporary free demo only, omit DATABASE_PATH and the disk; accounts and sessions can disappear on restart/redeployment. For durable free hosting, migrate the account store to an external database first. The deployment in this repository does not implement Postgres.

## Vercel frontend

1. In frontend/vercel.json replace both occurrences of https://YOUR-RENDER-SERVICE.onrender.com with your actual Render service URL. Keep the paths following the hostname intact. Commit and push this edit.
2. In Vercel, choose Add New > Project and import this repository.
3. Set Framework Preset to Other and Root Directory to frontend.
4. Leave Build Command empty; set Output Directory to `.` if the interface requires a value. No frontend package installation is needed.
5. Deploy and open the assigned HTTPS URL.
6. Create a new test account, predict rice using 90,42,43,20.5,82,6.5,200, refresh, log out, and sign in again.

The Vercel rewrites proxy /api/* and /predict to Render. Requests remain same-origin from the browser's perspective, avoiding cross-site cookie/CORS configuration. The /login path serves index.html. Static images are served by Vercel. API responses are marked no-store.

Render may see Vercel's proxy IP instead of the original browser IP. The demo's IP rate limit can therefore be shared by visitors. Before broader public use, configure a trusted proxy-aware limiter; never blindly trust arbitrary X-Forwarded-For values.

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
