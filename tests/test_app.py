import os
import sqlite3
import time
import pytest
from app import create_app

INPUT = dict(Nitrogen=90, Phosphorus=42, Potassium=43, Temperature=20.5, Humidity=82, Ph=6.5, Rainfall=200)
PASSWORD = 'test password 123'

@pytest.fixture
def app(tmp_path):
    return create_app({'TESTING': True, 'SECRET_KEY': 'test-only-key', 'DATABASE': str(tmp_path / 'users.sqlite3')})

@pytest.fixture
def client(app):
    return app.test_client()

def post(client, path, payload):
    token = client.get('/api/session').json['csrf_token']
    return client.post(path, json=payload, headers={'X-CSRF-Token': token})

def register(client, username='student'):
    return post(client, '/api/register', dict(username=username, password=PASSWORD, confirm_password=PASSWORD))

def test_pages_and_unknown_user(client, app):
    assert client.get('/').status_code == 200
    assert client.get('/login').status_code == 200
    assert post(client, '/api/login', dict(username='unknown', password=PASSWORD)).status_code == 401
    with sqlite3.connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0

def test_registration_login_persistence_and_password_hash(client, app):
    assert register(client).json['username'] == 'student'
    with sqlite3.connect(app.config['DATABASE']) as db:
        stored = db.execute('SELECT password_hash FROM users').fetchone()[0]
        assert stored != PASSWORD and stored.startswith('scrypt:')
    assert post(client, '/api/logout', {}).status_code == 200
    fresh_app = create_app(dict(app.config))
    other = fresh_app.test_client()
    assert post(other, '/api/login', dict(username='STUDENT', password=PASSWORD)).status_code == 200
    assert other.get('/api/session').json['username'] == 'student'
    assert post(other, '/api/login', dict(username='student', password='wrong password')).status_code == 401
    assert register(other, 'STUDENT').status_code == 409

def test_csrf_and_revoked_cookie(client, app):
    assert client.post('/api/register', json={}).status_code == 403
    assert post(client, '/predict', INPUT).status_code == 401
    assert register(client).status_code == 200
    old_cookie = client.get_cookie('session').value
    assert post(client, '/predict', INPUT).json['crop'] == 'rice'
    assert post(client, '/api/logout', {}).status_code == 200
    replay = app.test_client()
    replay.set_cookie('session', old_cookie)
    assert replay.get('/api/session').json['username'] is None
    assert post(replay, '/predict', INPUT).status_code == 401
    assert post(client, '/predict', INPUT).status_code == 401

def test_session_expiry(client, app):
    register(client)
    with sqlite3.connect(app.config['DATABASE']) as db:
        db.execute('UPDATE sessions SET expires = ?', (time.time() - 1,))
    assert post(client, '/predict', INPUT).status_code == 401

@pytest.mark.parametrize('field,value', [('Humidity',101),('Ph',15),('Rainfall',-1),('Nitrogen','NaN'),('Temperature','Infinity'),('Potassium',True),('Temperature',-274),('Nitrogen',None)])
def test_invalid_prediction(client, field, value):
    register(client)
    payload = INPUT | {field:value}
    assert post(client, '/predict', payload).status_code == 400

def test_missing_field_and_wrong_json(client):
    register(client)
    payload = dict(INPUT)
    payload.pop('Rainfall')
    assert post(client, '/predict', payload).status_code == 400
    assert post(client, '/predict', []).status_code == 400

def test_old_phosphorus_field_and_cookie_flags(client):
    response = register(client)
    cookie = response.headers['Set-Cookie']
    assert 'HttpOnly' in cookie and 'SameSite=Lax' in cookie
    payload = dict(INPUT)
    payload['Phosporus'] = payload.pop('Phosphorus')
    result = post(client, '/predict', payload)
    assert result.status_code == 200 and result.json['crop'] == 'rice'
    assert client.get('/static/' + result.json['image']).status_code == 200

@pytest.mark.parametrize('payload', [dict(username='<script>',password=PASSWORD), dict(username='ok_name',password='short'), dict(username='student',password=PASSWORD,confirm_password='different')])
def test_invalid_registration(client,payload):
    assert post(client,'/api/register',payload).status_code == 400

def test_password_spaces_preserved(client):
    password = '  exact password  '
    assert post(client,'/api/register',dict(username='spaces',password=password,confirm_password=password)).status_code == 200
    post(client,'/api/logout',{})
    assert post(client,'/api/login',dict(username='spaces',password=password.strip())).status_code == 401
    assert post(client,'/api/login',dict(username='spaces',password=password)).status_code == 200

def test_rate_limit(client):
    for _ in range(10):
        assert post(client, '/api/login',dict(username='unknown',password=PASSWORD)).status_code == 401
    assert post(client, '/api/login',dict(username='unknown',password=PASSWORD)).status_code == 429

# --- Proxy-aware rate-limit tests ----------------------------------------

def test_rate_limit_ignores_xff_without_trusted_proxy(tmp_path):
    """Without TRUSTED_PROXY, X-Forwarded-For must be ignored and
    rate-limiting must key on request.remote_addr."""
    # Ensure TRUSTED_PROXY is NOT set for this test.
    env_backup = os.environ.pop('TRUSTED_PROXY', None)
    try:
        app = create_app({
            'TESTING': True, 'SECRET_KEY': 'test-only-key',
            'DATABASE': str(tmp_path / 'xff_ignore.sqlite3'),
        })
        client = app.test_client()
        # Send 10 attempts claiming a different IP via X-Forwarded-For.
        for _ in range(10):
            tok = client.get('/api/session').json['csrf_token']
            resp = client.post(
                '/api/login', json=dict(username='unknown', password=PASSWORD),
                headers={'X-CSRF-Token': tok, 'X-Forwarded-For': '1.2.3.4'},
            )
            assert resp.status_code == 401
        # The 11th attempt should still be rate-limited because the app
        # must be using remote_addr (127.0.0.1), not the spoofed XFF.
        tok = client.get('/api/session').json['csrf_token']
        resp = client.post(
            '/api/login', json=dict(username='unknown', password=PASSWORD),
            headers={'X-CSRF-Token': tok, 'X-Forwarded-For': '1.2.3.4'},
        )
        assert resp.status_code == 429
    finally:
        if env_backup is not None:
            os.environ['TRUSTED_PROXY'] = env_backup


def test_rate_limit_uses_xff_with_trusted_proxy(tmp_path):
    """With TRUSTED_PROXY=1, rate limiting must key on the leftmost
    X-Forwarded-For address instead of remote_addr."""
    os.environ['TRUSTED_PROXY'] = '1'
    try:
        app = create_app({
            'TESTING': True, 'SECRET_KEY': 'test-only-key',
            'DATABASE': str(tmp_path / 'xff_trusted.sqlite3'),
        })
        client = app.test_client()

        # Exhaust rate limit for a spoofed IP.
        for _ in range(10):
            tok = client.get('/api/session').json['csrf_token']
            resp = client.post(
                '/api/login', json=dict(username='unknown', password=PASSWORD),
                headers={'X-CSRF-Token': tok, 'X-Forwarded-For': '10.0.0.1'},
            )
            assert resp.status_code == 401

        # 11th attempt from the *same* forwarded IP should be blocked.
        tok = client.get('/api/session').json['csrf_token']
        resp = client.post(
            '/api/login', json=dict(username='unknown', password=PASSWORD),
            headers={'X-CSRF-Token': tok, 'X-Forwarded-For': '10.0.0.1'},
        )
        assert resp.status_code == 429

        # A *different* forwarded IP should still be allowed.
        tok = client.get('/api/session').json['csrf_token']
        resp = client.post(
            '/api/login', json=dict(username='unknown', password=PASSWORD),
            headers={'X-CSRF-Token': tok, 'X-Forwarded-For': '10.0.0.2'},
        )
        assert resp.status_code == 401  # wrong creds, but not rate-limited
    finally:
        del os.environ['TRUSTED_PROXY']


def test_static_asset_routes(client):
    """Verify frontend static assets are routed correctly by Flask."""
    css = client.get('/styles.css')
    assert css.status_code == 200
    assert 'text/css' in css.headers['Content-Type']
    assert b'.bg-slideshow' in css.data

    js = client.get('/app.js')
    assert js.status_code == 200
    assert 'javascript' in js.headers['Content-Type']
    assert b'initializeSession' in js.data

    fav_ico = client.get('/favicon.ico')
    assert fav_ico.status_code == 200

    fav_svg = client.get('/favicon.svg')
    assert fav_svg.status_code == 200
    assert 'image/svg+xml' in fav_svg.headers['Content-Type']

    fav_png = client.get('/favicon.png')
    assert fav_png.status_code == 200
    assert 'image/png' in fav_png.headers['Content-Type']


def test_health_and_security_headers(client):
    """Verify health endpoint and security headers on responses."""
    health = client.get('/health')
    assert health.status_code == 200
    assert health.json == {'status': 'ok'}
    assert health.headers['X-Content-Type-Options'] == 'nosniff'
    assert health.headers['X-Frame-Options'] == 'DENY'
    assert 'no-store' in health.headers['Cache-Control']


def test_unauthenticated_prediction_fails_cleanly(client):
    """Verify predict returns 401 with informative error for unauthenticated requests."""
    res = post(client, '/predict', INPUT)
    assert res.status_code == 401
    assert res.json['success'] is False
    assert 'sign in' in res.json['error'].lower()

