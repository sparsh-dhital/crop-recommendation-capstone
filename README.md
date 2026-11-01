# Crop Recommendation System Using Machine Learning

See [DEPLOYMENT.md](DEPLOYMENT.md) for the current folder layout and Render + Vercel instructions.

An educational Flask application that classifies soil and climate measurements into one of 22 crop labels. It does **not** predict crop yield, profit, or guaranteed agricultural suitability.

## Quick start

Use Python 3.12 (the tested version). In a terminal inside this repository:

```bash
python -m venv .venv
```

Activate the environment:

- Windows PowerShell: `.venv\Scripts\Activate.ps1`
- Windows Command Prompt: `.venv\Scripts\activate.bat`
- macOS/Linux: `source .venv/bin/activate`

Then run:

```bash
python -m pip install -r backend/requirements.txt
python app.py
```

Open http://127.0.0.1:5000, choose **Get Started**, then **Create an account**. Use a username of 3–32 letters, numbers or underscores and a password of 8–128 characters. Sign-up and sign-in are separate actions. There are no default credentials. `/login` opens the same working login form directly.

Accounts previously stored in the browser must be registered again. The app removes its old plaintext password registry; it never imports those passwords. Accounts persist in `instance/users.sqlite3` on the machine running Flask (or PostgreSQL when `DATABASE_URL` is set). Keep this directory if you want accounts to survive moving/restarting the application. Never commit it.

## Authentication

- Passwords are hashed with Werkzeug's scrypt implementation.
- An HttpOnly, SameSite=Lax signed cookie carries a random session token. Database stores only its hash and an eight-hour expiry.
- Logout revokes that token server-side, including a copied old cookie.
- POST requests require a CSRF token. Unknown usernames never silently create accounts.
- Login and registration are rate-limited to ten attempts per client IP in fifteen minutes, cleared after successful authentication. When behind a trusted edge proxy (Vercel), `TRUSTED_PROXY=1` ensures real client IPs are evaluated.
- Prediction history stays in the current browser, separated by username. It is not encrypted or synchronized and should not be treated as private storage on shared devices.
- Password recovery, email verification, production monitoring and multi-server deployment are outside this classroom prototype.

For HTTPS deployment, configure a strong `SECRET_KEY`, set `COOKIE_SECURE=1`, use a production WSGI server, and persist the database securely. The generated local key in `instance/secret.key` is for development. Debug mode is off by default. Do not expose the development server publicly.

## Inputs and model

Input order: Nitrogen, Phosphorus, Potassium, temperature (°C), relative humidity (%), pH, rainfall (mm). The exact nutrient units and rainfall accumulation period must be confirmed against the dataset's original source; do not invent them. The old API field `Phosporus` is accepted for compatibility.

All seven inputs are mandatory finite numbers. Nutrients and rainfall must be non-negative, humidity must be 0–100, and pH must be 0–14. These physical checks are not proof that a sample lies within the model's training distribution.

Example: N=90, P=42, K=43, temperature=20.5, humidity=82, pH=6.5, rainfall=200 returns **rice** with the supplied trained model.

## Reproduce experiments

```bash
python backend/train.py
```

The script checks missing/duplicate/non-finite data, uses a stratified 80/20 train/test split with seed 42, and fits StandardScaler only on training data. Five-fold stratified cross-validation is performed within the training set using a pipeline, so each fold learns its own scaler. Scaling is retained for compatibility with the application's inference pipeline; tree models do not generally require it.

The experiment compares a majority-class dummy baseline, Decision Tree and Random Forest (100 trees, seed 42). Random Forest is retained as the deployment model; the held-out test set is not used for tuning. The script regenerates `model.pkl`, `scaler.pkl`, and `label_encoder.pkl` together. Only load trusted pickle files.

| Model | Held-out accuracy | Macro F1 | Correct / 440 | Training CV accuracy |
|---|---:|---:|---:|---:|
| Dummy baseline | 4.55% | 0.00395 | 20 | 4.55% |
| Decision Tree | 97.95% | 0.97942 | 431 | 98.52% |
| Random Forest | 99.55% | 0.99545 | 438 | 99.26% |

Dataset: 2,200 rows, seven features, 22 balanced classes (100 rows each), no missing values or duplicate rows in the supplied CSV. The split contains 1,760 training and 440 test rows (20 per class in the test set).

Outputs in `evaluation/` include exact metrics, dependency versions, dataset hash, per-class precision/recall/F1, timings, confusion matrix and misclassified samples. The two Random Forest errors are blackgram → maize and rice → jute. Timings depend on hardware.

These results measure agreement with labels in a single dataset. They do not establish field performance, higher yields or economic benefits. Dataset provenance/license and independent regional validation remain outstanding.

The notebook now calls the same training script, avoiding a second conflicting training pipeline. The original notebook's 99.32% figure came from a different, non-stratified split with scaling performed before the split; do not mix that number with the corrected results.

## Test

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
npm install
python tests/run_ui.py
```

Tests cover account persistence, password hashing, wrong passwords, duplicate accounts, CSRF checks, session expiry, logout revocation, rate limits, proxy-aware IP handling, missing/invalid inputs, static asset routing, and an actual saved-model rice prediction.

## Project structure

- `backend/app.py`: Flask routes, authentication, PostgreSQL/SQLite database support, input checks, inference.
- `frontend/index.html`: semantic HTML shell with accessibility and live regions.
- `frontend/styles.css`: styling, responsive breakpoints, reduced-motion preferences, and focus indicators.
- `frontend/app.js`: resilient session initialization with retry logic, DOM-safe rendering, and local history management.
- `frontend/static/`: crop images allowlisted for display.
- `backend/train.py`: reproducible training and evaluation.
- `evaluation/`: measured results for the report/poster.
- `tests/test_app.py`: pytest backend unit and security tests.
- `tests/test_ui.cjs`: JSDOM-based DOM integration tests against Flask.
- `docs/CAPSTONE_REVIEW.md`: checklist against faculty guidelines and report corrections.

The original unused `minmaxscaler.pkl`, `standscaler.pkl`, `get-pip.py` and empty `landing.html` remain for compatibility/history; the application does not use them. Images for jute and mothbeans were not supplied, so those predictions show an explicit image-unavailable message. The mungbean mapping points to the existing image.

## Acknowledgements

Built on this team's existing Crop-Recommendation-System repository. Uses Flask/Werkzeug, NumPy, pandas, scikit-learn and Matplotlib. The interface uses Bootstrap, Font Awesome, Google Fonts and external background images, which need internet access. Confirm licenses/attribution for the supplied CSV and images before redistribution. AI-assisted code changes must be reviewed and understood by all team members, as required by the faculty guidelines.
