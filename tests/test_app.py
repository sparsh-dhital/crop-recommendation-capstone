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
