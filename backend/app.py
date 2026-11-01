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


def create_app(test_config=None):
    app = Flask(__name__, static_folder=str(BASE_DIR.parent / 'frontend' / 'static'))
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY'),
        DATABASE=os.environ.get('DATABASE_PATH', str(BASE_DIR.parent / 'instance' / 'users.sqlite3')),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE') == '1',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=16384,
    )
    if test_config:
        app.config.update(test_config)
    Path(app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
    if not app.config['SECRET_KEY']:
        # Persist the local development key across restarts; never commit it.
        key_path = Path(app.config['DATABASE']).parent / 'secret.key'
        key_path.parent.mkdir(exist_ok=True)
        try:
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, 'w') as stream:
                stream.write(secrets.token_hex(32))
        app.config['SECRET_KEY'] = key_path.read_text().strip()

    def db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE'])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        connection = g.pop('db', None)
        if connection is not None:
            connection.close()

    with app.app_context():
        db().executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS auth_attempts (
                address TEXT NOT NULL, attempted REAL NOT NULL);
        ''')
        db().commit()

    def csrf_token():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_urlsafe(32)
        return session['csrf_token']

    def token_hash():
        return hashlib.sha256(session.get('auth_token', '').encode()).hexdigest()

    def current_user():
        return db().execute(
            'SELECT users.id, users.username FROM sessions JOIN users ON users.id = sessions.user_id '
            'WHERE token_hash = ? AND expires > ?', (token_hash(), time.time())
        ).fetchone()

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
        address = request.remote_addr or 'unknown'
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
            except sqlite3.IntegrityError:
                db().rollback()
                return jsonify(success=False, error='That username is already registered. Please sign in.'), 409
        user = db().execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
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
