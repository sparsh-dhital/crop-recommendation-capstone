"""Crop recommendation demo with persistent accounts and revocable sessions."""
from datetime import timedelta
from pathlib import Path
import hashlib
import math
import os
import pickle
import re
import secrets
import sqlite3
import time

import pandas as pd
from flask import Flask, g, jsonify, send_from_directory, request, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
FEATURES = ['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']
FIELDS = ['Nitrogen', 'Phosphorus', 'Potassium', 'Temperature', 'Humidity', 'Ph', 'Rainfall']
IMAGE_MAP = {
    'apple': 'apple.jpg', 'banana': 'banana.jpg', 'blackgram': 'blackgram.jpg',
    'chickpea': 'chickpea.jpg', 'coconut': 'coconut.jpg.jpeg', 'coffee': 'coffee.jpg',
    'cotton': 'cotton.jpg', 'grapes': 'grapes.jpg', 'kidneybeans': 'kidneybeans.jpg',
    'lentil': 'lentil.jpg', 'maize': 'maize.jpg', 'mango': 'mango.jpeg',
    'mungbean': 'mungbean.jpg', 'muskmelon': 'muskmelon.jpeg', 'orange': 'orange.jpeg',
    'papaya': 'papaya.jpeg', 'pigeonpeas': 'pegionpeas.jpg',
    'pomegranate': 'pomegranate.jpg', 'rice': 'rice.jpeg', 'watermelon': 'watermelon.jpeg',
}


def _client_address():
    """Return the client IP for rate limiting.

    When TRUSTED_PROXY=1, use the leftmost X-Forwarded-For address
    (the original client as seen by the trusted edge proxy).
    Otherwise, use the direct connection address.

    Security note: X-Forwarded-For is trivially spoofable. Only trust it
    when the app sits behind a *known* reverse proxy (e.g. Vercel → Render)
    that overwrites or prepends the header. Set TRUSTED_PROXY=1 explicitly
    to opt in; never enable it when the app is directly internet-facing.
    """
    if os.environ.get('TRUSTED_PROXY') == '1':
        forwarded = request.headers.get('X-Forwarded-For', '')
        if forwarded:
            return forwarded.split(',')[0].strip()
    return request.remote_addr or 'unknown'


# ---------------------------------------------------------------------------
# Thin database abstraction – keeps one set of SQL with ``?`` placeholders
# and converts them to ``%s`` for PostgreSQL at execution time.
# ---------------------------------------------------------------------------

class _DBWrapper:
    """Minimal wrapper around a DB-API connection.

    * Translates ``?`` placeholders to ``%s`` for PostgreSQL.
    * Exposes ``execute``, ``commit``, ``rollback``, ``close``,
      ``executescript`` (SQLite-only shortcut, emulated on PostgreSQL).
    * ``execute().fetchone()`` returns *dict-like* rows for both backends.
    """

    def __init__(self, conn, db_type):
        self._conn = conn
        self._pg = db_type == 'postgres'

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _convert_sql(sql):
        """Replace ``?`` with ``%s`` (naively – fine for this app's SQL)."""
        return sql.replace('?', '%s')

    # -- public API --------------------------------------------------------

    def execute(self, sql, params=()):
        cur = self._conn.cursor()
        if self._pg:
            sql = self._convert_sql(sql)
        cur.execute(sql, params)
        return cur

    def executescript(self, sql):
        """Run multi-statement DDL.

        SQLite has ``executescript()``; PostgreSQL can run multiple
        statements in a single ``execute()`` call.
        """
        if self._pg:
            self._conn.cursor().execute(sql)
            self._conn.commit()
        else:
            self._conn.executescript(sql)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def create_app(test_config=None):
    app = Flask(__name__, static_folder=str(BASE_DIR.parent / 'frontend' / 'static'))

    # --- Database backend selection ----------------------------------------
    database_url = os.environ.get('DATABASE_URL')
    use_postgres = database_url is not None and database_url.startswith('postgres')

    if use_postgres:
        # Fix Heroku/Render style URLs (postgres:// → postgresql://)
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY'),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE') == '1',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=16384,
        DB_TYPE='postgres' if use_postgres else 'sqlite',
    )

    if use_postgres:
        app.config['DATABASE_URL'] = database_url
    else:
        app.config['DATABASE'] = os.environ.get(
            'DATABASE_PATH',
            str(BASE_DIR.parent / 'instance' / 'users.sqlite3'),
        )

    if test_config:
        app.config.update(test_config)

    # Ensure the SQLite parent directory exists (no-op for PostgreSQL).
    if app.config['DB_TYPE'] == 'sqlite':
        Path(app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)

    if not app.config['SECRET_KEY']:
        # Persist the local development key across restarts; never commit it.
        if app.config['DB_TYPE'] == 'sqlite':
            key_path = Path(app.config['DATABASE']).parent / 'secret.key'
        else:
            key_path = BASE_DIR.parent / 'instance' / 'secret.key'
        key_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, 'w') as stream:
                stream.write(secrets.token_hex(32))
        app.config['SECRET_KEY'] = key_path.read_text().strip()

    # --- Connection helper ------------------------------------------------

    def _connect():
        """Open a raw DB-API connection for the configured backend."""
        if app.config['DB_TYPE'] == 'postgres':
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(app.config['DATABASE_URL'])
            conn.cursor_factory = psycopg2.extras.RealDictCursor
            return conn
        else:
            conn = sqlite3.connect(app.config['DATABASE'])
            conn.row_factory = sqlite3.Row
            return conn

    def db():
        if 'db' not in g:
            g.db = _DBWrapper(_connect(), app.config['DB_TYPE'])
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        wrapper = g.pop('db', None)
        if wrapper is not None:
            wrapper.close()

    # --- Schema -----------------------------------------------------------
    # Uses REAL for timestamps (works for both SQLite and PostgreSQL).
    # SQLite auto-increment: INTEGER PRIMARY KEY.
    # PostgreSQL auto-increment: SERIAL.
    _sqlite_ddl = '''\
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS auth_attempts (
            address TEXT NOT NULL, attempted REAL NOT NULL);
    '''

    _pg_ddl = '''\
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS users_username_lower_idx ON users (LOWER(username));
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires DOUBLE PRECISION NOT NULL);
        CREATE TABLE IF NOT EXISTS auth_attempts (
            address TEXT NOT NULL, attempted DOUBLE PRECISION NOT NULL);
    '''

    with app.app_context():
        ddl = _pg_ddl if app.config['DB_TYPE'] == 'postgres' else _sqlite_ddl
        db().executescript(ddl)
        db().commit()

    # --- Helpers ----------------------------------------------------------

    def csrf_token():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_urlsafe(32)
        return session['csrf_token']

    def token_hash():
        return hashlib.sha256(session.get('auth_token', '').encode()).hexdigest()

    def current_user():
        if not session.get('auth_token'):
            return None
        row = db().execute(
            'SELECT users.id, users.username FROM sessions JOIN users ON users.id = sessions.user_id '
            'WHERE token_hash = ? AND expires > ?', (token_hash(), time.time())
        ).fetchone()
        return row

    # --- Integrity-error handling -----------------------------------------
    # PostgreSQL raises psycopg2.IntegrityError; SQLite raises
    # sqlite3.IntegrityError.  We catch both via a helper tuple.

    _integrity_errors = (sqlite3.IntegrityError,)
    try:
        import psycopg2
        _integrity_errors = (sqlite3.IntegrityError, psycopg2.IntegrityError)
    except ImportError:
        pass

    # --- Routes -----------------------------------------------------------

    @app.before_request
    def protect_mutations():
        if request.method == 'POST':
            supplied = request.headers.get('X-CSRF-Token', '')
            expected = session.get('csrf_token', '')
            if not expected or not secrets.compare_digest(supplied, expected):
                return jsonify(success=False, error='Session expired. Refresh the page and try again.'), 403

    @app.after_request
    def response_headers(response):
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    @app.get('/')
    @app.get('/login')
    def index():
        return send_from_directory(BASE_DIR.parent / 'frontend', 'index.html')

    @app.get('/styles.css')
    def styles():
        return send_from_directory(BASE_DIR.parent / 'frontend', 'styles.css')

    @app.get('/app.js')
    def app_js():
        return send_from_directory(BASE_DIR.parent / 'frontend', 'app.js')

    @app.get('/favicon.ico')
    def favicon_ico():
        folder = BASE_DIR.parent / 'frontend' if (BASE_DIR.parent / 'frontend' / 'favicon.ico').is_file() else BASE_DIR.parent / 'frontend' / 'static'
        return send_from_directory(folder, 'favicon.ico', mimetype='image/x-icon')

    @app.get('/favicon.svg')
    def favicon_svg():
        folder = BASE_DIR.parent / 'frontend' if (BASE_DIR.parent / 'frontend' / 'favicon.svg').is_file() else BASE_DIR.parent / 'frontend' / 'static'
        return send_from_directory(folder, 'favicon.svg', mimetype='image/svg+xml')

    @app.get('/favicon.png')
    def favicon_png():
        folder = BASE_DIR.parent / 'frontend' if (BASE_DIR.parent / 'frontend' / 'favicon.png').is_file() else BASE_DIR.parent / 'frontend' / 'static'
        return send_from_directory(folder, 'favicon.png', mimetype='image/png')

    @app.get('/health')
    def health():
        return jsonify(status='ok')

    @app.get('/api/session')
    def session_info():
        user = current_user()
        return jsonify(success=True, username=user['username'] if user else None, csrf_token=csrf_token())

    @app.post('/api/register')
    @app.post('/api/login')
    def authenticate():
        # Bound authentication attempts for this local demo (10 attempts / IP / 15 minutes).
        address = _client_address()
        now = time.time()
        db().execute('DELETE FROM auth_attempts WHERE attempted < ?', (now - 900,))
        attempts = db().execute('SELECT COUNT(*) FROM auth_attempts WHERE address = ?', (address,)).fetchone()[0]
        if attempts >= 10:
            return jsonify(success=False, error='Too many attempts. Try again in 15 minutes.'), 429
        db().execute('INSERT INTO auth_attempts VALUES (?, ?)', (address, now))
        db().commit()
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(success=False, error='A JSON object is required.'), 400
        username, password = data.get('username'), data.get('password')
        if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_]{3,32}', username.strip()):
            return jsonify(success=False, error='Use 3–32 letters, numbers or underscores for your username.'), 400
        username = username.strip()
        if not isinstance(password, str) or not 8 <= len(password) <= 128:
            return jsonify(success=False, error='Use a password of 8–128 characters.'), 400
        if request.path == '/api/register':
            if data.get('confirm_password') != password:
                return jsonify(success=False, error='Passwords do not match.'), 400
            try:
                db().execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                             (username, generate_password_hash(password)))
                db().commit()
            except _integrity_errors:
                db().rollback()
                return jsonify(success=False, error='That username is already registered. Please sign in.'), 409
        user = db().execute('SELECT * FROM users WHERE LOWER(username) = LOWER(?)', (username,)).fetchone()
        if not user or not check_password_hash(user['password_hash'], password):
            return jsonify(success=False, error='Incorrect username or password.'), 401
        db().execute('DELETE FROM sessions WHERE token_hash = ? OR expires <= ?', (token_hash(), now))
        session.clear()
        session.permanent = True
        session['auth_token'] = secrets.token_urlsafe(32)
        db().execute('INSERT INTO sessions VALUES (?, ?, ?)',
                     (token_hash(), user['id'], now + app.permanent_session_lifetime.total_seconds()))
        db().execute('DELETE FROM auth_attempts WHERE address = ?', (address,))
        db().commit()
        return jsonify(success=True, username=user['username'], csrf_token=csrf_token())

    @app.post('/api/logout')
    def logout():
        if session.get('auth_token'):
            db().execute('DELETE FROM sessions WHERE token_hash = ?', (token_hash(),))
            db().commit()
        session.clear()
        return jsonify(success=True, csrf_token=csrf_token())

    @app.post('/predict')
    def predict():
        if not current_user():
            return jsonify(success=False, error='Please sign in before requesting a prediction.'), 401
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(success=False, error='A JSON object with all seven inputs is required.'), 400
        # Accept the original misspelling for compatibility, but use Phosphorus in the UI.
        if 'Phosphorus' not in data and 'Phosporus' in data:
            data['Phosphorus'] = data['Phosporus']
        values = []
        for name in FIELDS:
            raw = data.get(name)
            try:
                if raw is None or isinstance(raw, bool):
                    raise ValueError
                value = float(raw)
                if not math.isfinite(value):
                    raise ValueError
            except (ValueError, TypeError, OverflowError):
                return jsonify(success=False, error=f'{name} must be a finite number.'), 400
            if (name != 'Temperature' and value < 0) or (name == 'Temperature' and value < -273.15):
                return jsonify(success=False, error=f'{name} is outside its valid range.'), 400
            if (name == 'Humidity' and value > 100) or (name == 'Ph' and value > 14):
                return jsonify(success=False, error=f'{name} is outside its valid range.'), 400
            values.append(value)
        try:
            if 'models' not in app.extensions:
                # Only load trusted model artifacts distributed with this repository.
                objects = []
                for name in ['model.pkl', 'scaler.pkl', 'label_encoder.pkl']:
                    with (BASE_DIR / 'models' / name).open('rb') as stream:
                        objects.append(pickle.load(stream))
                app.extensions['models'] = objects
            model, scaler, encoder = app.extensions['models']
            features = pd.DataFrame([values], columns=FEATURES)
            crop = str(encoder.inverse_transform(model.predict(scaler.transform(features)))[0])
            image = IMAGE_MAP.get(crop.lower())
            if image and not (BASE_DIR.parent / 'frontend' / 'static' / image).is_file():
                image = None
            return jsonify(success=True, crop=crop, image=image)
        except Exception:
            app.logger.exception('Prediction failed')
            return jsonify(success=False, error='Prediction unavailable. Check the trained model files.'), 503

    return app


if __name__ == '__main__':
    create_app().run(debug=os.environ.get('FLASK_DEBUG') == '1')
