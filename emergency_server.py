#!/usr/bin/env python3
"""
Strovo АВАРИЙНЫЙ СЕРВЕР
Минимальный запасной backend, если основной server.py не запускается.
Раздаёт сайт, логин/регистрацию, профиль, проекты (чтение), донат-коины.
Без тяжёлой логики: presence, WebRTC, studio save — по возможности упрощены.
"""

import json
import os
import sys
import hashlib
import uuid
import mimetypes
import socket
from datetime import datetime

try:
    from flask import Flask, request, jsonify, send_from_directory, send_file
    from flask_cors import CORS
except ImportError:
    print("Нужен Flask:  pip install flask flask-cors")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'datag')
GALO_DIR = os.path.join(BASE_DIR, 'galo')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(GALO_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, 'users.json')
SESSIONS_FILE = os.path.join(DATA_DIR, 'sessions.json')
PROJECTS_FILE = os.path.join(DATA_DIR, 'projects.json')
VERIFIED_FILE = os.path.join(GALO_DIR, 'verified.json')

DONATE_PACKAGES = {
    'donat-90-koin': {'id': 'donat-90-koin', 'title': '90 коинов', 'coins': 90, 'price_rub': 50},
    'donat-300-koin': {'id': 'donat-300-koin', 'title': '300 коинов', 'coins': 300, 'price_rub': 150},
}

app = Flask(__name__)
CORS(app)


def load_json(path, default=None):
    if default is None:
        default = {}
    try:
        if not os.path.exists(path):
            return default if not isinstance(default, dict) else dict(default)
        with open(path, 'r', encoding='utf-8') as f:
            raw = f.read().strip()
        if not raw:
            return default if not isinstance(default, dict) else dict(default)
        return json.loads(raw)
    except Exception as e:
        print(f'[EMERGENCY] JSON error {path}: {e}')
        return default if not isinstance(default, dict) else dict(default)


def save_json(path, data):
    try:
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception as e:
        print(f'[EMERGENCY] save failed {path}: {e}')
        return False


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def get_user_by_token(token):
    if not token:
        return None
    sessions = load_json(SESSIONS_FILE, {})
    s = sessions.get(token)
    if not s:
        return None
    users = load_json(USERS_FILE, {})
    return users.get(s.get('username'))


def port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('0.0.0.0', port))
        s.close()
        return True
    except OSError:
        return False


# ---------- STATUS ----------
@app.route('/api/status')
@app.route('/api/emergency')
def api_status():
    return jsonify({
        'success': True,
        'mode': 'emergency',
        'message': 'Аварийный сервер Strovo',
        'time': datetime.now().isoformat(),
    })


# ---------- AUTH ----------
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if len(username) < 3:
        return jsonify({'success': False, 'error': 'Ник минимум 3 символа'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Пароль минимум 6 символов'}), 400
    users = load_json(USERS_FILE, {})
    if any(u.lower() == username.lower() for u in users):
        return jsonify({'success': False, 'error': 'Ник занят'}), 409
    user_id = uuid.uuid4().hex
    users[username] = {
        'id': user_id,
        'username': username,
        'password_hash': hash_password(password),
        'coins': 500,
        'friends': [],
        'followers': 0,
        'created_at': datetime.now().isoformat(),
        'avatar_color': '#ff6b00',
        'avatar_parts': {},
        'inventory': [],
        'equipped': {},
    }
    save_json(USERS_FILE, users)
    token = uuid.uuid4().hex
    sessions = load_json(SESSIONS_FILE, {})
    sessions[token] = {'user_id': user_id, 'username': username, 'created_at': datetime.now().isoformat()}
    save_json(SESSIONS_FILE, sessions)
    return jsonify({'success': True, 'token': token, 'user': {'username': username, 'coins': 500}})


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    users = load_json(USERS_FILE, {})
    user = users.get(username)
    if not user or user.get('password_hash') != hash_password(password):
        return jsonify({'success': False, 'error': 'Неверный логин или пароль'}), 401
    token = uuid.uuid4().hex
    sessions = load_json(SESSIONS_FILE, {})
    sessions[token] = {
        'user_id': user.get('id'),
        'username': username,
        'created_at': datetime.now().isoformat(),
    }
    save_json(SESSIONS_FILE, sessions)
    return jsonify({
        'success': True,
        'token': token,
        'user': {'username': username, 'coins': user.get('coins', 0)},
    })


@app.route('/api/logout', methods=['POST'])
def api_logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    sessions = load_json(SESSIONS_FILE, {})
    if token in sessions:
        del sessions[token]
        save_json(SESSIONS_FILE, sessions)
    return jsonify({'success': True})


@app.route('/api/me', methods=['GET'])
def api_me():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    verified = load_json(VERIFIED_FILE, {})
    return jsonify({
        'success': True,
        'user': {
            'id': user.get('id'),
            'username': user.get('username'),
            'coins': user.get('coins', 0),
            'friends': user.get('friends', []),
            'followers': user.get('followers', 0),
            'avatar_color': user.get('avatar_color', '#ff6b00'),
            'avatar_parts': user.get('avatar_parts', {}),
            'inventory': user.get('inventory', []),
            'equipped': user.get('equipped', {}),
            'verified': verified.get(user.get('username'), False),
            'is_admin': user.get('is_admin', False),
            'created_at': user.get('created_at', ''),
            'emergency_mode': True,
        },
    })


# ---------- GAMES / PROJECTS (read-only + simple save) ----------
@app.route('/api/games', methods=['GET'])
def api_games():
    projects = load_json(PROJECTS_FILE, {})
    verified = load_json(VERIFIED_FILE, {})
    games = []
    for pid, p in projects.items():
        if not p.get('published'):
            continue
        games.append({
            'id': pid,
            'name': p.get('name', 'Без имени'),
            'owner': p.get('owner', ''),
            'plays': p.get('plays', 0),
            'likes': p.get('likes', 0),
            'owner_verified': verified.get(p.get('owner'), False),
        })
    return jsonify({'success': True, 'games': games})


@app.route('/api/games/<game_id>', methods=['GET'])
def api_game(game_id):
    projects = load_json(PROJECTS_FILE, {})
    p = projects.get(game_id)
    if not p:
        return jsonify({'success': False, 'error': 'Игра не найдена'}), 404
    verified = load_json(VERIFIED_FILE, {})
    return jsonify({
        'success': True,
        'game': {
            **p,
            'id': game_id,
            'owner_verified': verified.get(p.get('owner'), False),
        },
    })


@app.route('/api/projects', methods=['GET'])
def api_projects():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    projects = load_json(PROJECTS_FILE, {})
    mine = []
    for pid, p in projects.items():
        if p.get('owner') == user.get('username'):
            mine.append({**p, 'id': pid})
    return jsonify({'success': True, 'projects': mine})


@app.route('/api/projects', methods=['POST'])
@app.route('/api/projects/<project_id>', methods=['PUT'])
def api_save_project(project_id=None):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    data = request.get_json() or {}
    projects = load_json(PROJECTS_FILE, {})
    if not project_id:
        project_id = uuid.uuid4().hex[:12]
    existing = projects.get(project_id)
    if existing and existing.get('owner') != user.get('username'):
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403
    projects[project_id] = {
        'id': project_id,
        'name': data.get('name') or (existing or {}).get('name') or 'Новый проект',
        'owner': user.get('username'),
        'blocks': data.get('blocks', (existing or {}).get('blocks', [])),
        'lights': data.get('lights', (existing or {}).get('lights', [])),
        'world_settings': data.get('world_settings', (existing or {}).get('world_settings', {})),
        'published': data.get('published', (existing or {}).get('published', False)),
        'plays': (existing or {}).get('plays', 0),
        'likes': (existing or {}).get('likes', 0),
        'updated_at': datetime.now().isoformat(),
        'created_at': (existing or {}).get('created_at', datetime.now().isoformat()),
    }
    save_json(PROJECTS_FILE, projects)
    return jsonify({'success': True, 'project': projects[project_id]})


# ---------- DONATE ----------
@app.route('/api/donate/packages', methods=['GET'])
def api_donate_packages():
    return jsonify({'success': True, 'packages': list(DONATE_PACKAGES.values())})


@app.route('/api/donate/<package_id>', methods=['POST'])
def api_donate(package_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Войди в аккаунт'}), 401
    pkg = DONATE_PACKAGES.get(package_id)
    if not pkg:
        return jsonify({'success': False, 'error': 'Пакет не найден'}), 404
    users = load_json(USERS_FILE, {})
    u = users.get(user['username'])
    if not u:
        return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404
    u['coins'] = int(u.get('coins', 0)) + int(pkg['coins'])
    save_json(USERS_FILE, users)
    return jsonify({'success': True, 'coins': u['coins'], 'added': pkg['coins'], 'message': f"+{pkg['coins']} коинов"})


# ---------- SHOP (list only) ----------
@app.route('/api/shop', methods=['GET'])
def api_shop():
    return jsonify({'success': True, 'items': []})


# ---------- PRESENCE stubs (чтобы play не падал) ----------
@app.route('/api/games/<game_id>/presence', methods=['GET', 'POST'])
def api_presence(game_id):
    return jsonify({'success': True, 'players': []})


@app.route('/api/games/<game_id>/chat', methods=['GET', 'POST'])
def api_chat(game_id):
    if request.method == 'GET':
        return jsonify({'success': True, 'messages': []})
    return jsonify({'success': True})


@app.route('/api/games/<game_id>/rtc/signal', methods=['GET', 'POST'])
def api_rtc(game_id):
    return jsonify({'success': True, 'signals': []})


# ---------- STATIC ----------
@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/donat-90-koin')
@app.route('/donat-90-koin.html')
def donat90():
    return send_from_directory(BASE_DIR, 'donat-90-koin.html')


@app.route('/donat-300-koin')
@app.route('/donat-300-koin.html')
def donat300():
    return send_from_directory(BASE_DIR, 'donat-300-koin.html')


@app.route('/css/<path:path>')
def css_files(path):
    return send_from_directory(os.path.join(BASE_DIR, 'css'), path)


@app.route('/js/<path:path>')
def js_files(path):
    return send_from_directory(os.path.join(BASE_DIR, 'js'), path)


@app.route('/images/<path:path>')
def image_files(path):
    return send_from_directory(os.path.join(BASE_DIR, 'images'), path)


@app.route('/<path:path>')
def static_files(path):
    safe = os.path.normpath(path).lstrip('/\\')
    full = os.path.join(BASE_DIR, safe)
    if not os.path.abspath(full).startswith(os.path.abspath(BASE_DIR)):
        return send_from_directory(BASE_DIR, 'index.html')
    if os.path.isfile(full):
        mime, _ = mimetypes.guess_type(full)
        return send_file(full, mimetype=mime)
    return send_from_directory(BASE_DIR, 'index.html')


def main():
    port = 5000
    if not port_free(port):
        print(f'[!] Порт {port} занят — пробую 5001')
        port = 5001
        if not port_free(port):
            print('[!] Порт 5001 тоже занят. Останови основной сервер или укажи другой порт.')
            port = int(os.environ.get('PORT', '5002'))

    print('=' * 50)
    print('  STROVO — АВАРИЙНЫЙ СЕРВЕР')
    print('  Режим: emergency (урезанный API)')
    print(f'  Папка: {BASE_DIR}')
    print(f'  Открой: http://localhost:{port}')
    print('  Если основной server.py снова работает —')
    print('  останови этот (Ctrl+C) и запусти start.bat')
    print('=' * 50)
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
