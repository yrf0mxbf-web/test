#!/usr/bin/env python3
"""
Strovo Server v0.0.2.V — Python backend
"""

import json
import os
import hashlib
import uuid
import base64
import re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, send_file, redirect
from flask_cors import CORS
import mimetypes

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Data folders
DATA_DIR = os.path.join(BASE_DIR, 'datag')
GALO_DIR = os.path.join(BASE_DIR, 'galo')
# Папка где хранятся игры и обложки
GAMES_DIR = os.path.join(BASE_DIR, 'games')
COVERS_DIR = os.path.join(GAMES_DIR, 'covers')   # обложки игр
PHOTOS_DIR = os.path.join(GAMES_DIR, 'photos')   # фото игр
# Клиент Windows (Strovo.exe) для скачивания с сайта
DOWNLOADS_DIR = os.path.join(BASE_DIR, 'downloads')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(GALO_DIR, exist_ok=True)
os.makedirs(COVERS_DIR, exist_ok=True)
os.makedirs(PHOTOS_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, 'users.json')
SESSIONS_FILE = os.path.join(DATA_DIR, 'sessions.json')
PROJECTS_FILE = os.path.join(DATA_DIR, 'projects.json')
VERIFIED_FILE = os.path.join(GALO_DIR, 'verified.json')

# Shop items (static catalog)
SHOP_ITEMS = {
    "hat_crown": {"id": "hat_crown", "name": "Золотая корона", "type": "hat", "price": 500, "color": "#FFD700"},
    "hat_cap": {"id": "hat_cap", "name": "Кепка", "type": "hat", "price": 100, "color": "#ff4757"},
    "shirt_ninja": {"id": "shirt_ninja", "name": "Куртка ниндзя", "type": "shirt", "price": 300, "color": "#2f3542"},
    "shirt_hoodie": {"id": "shirt_hoodie", "name": "Худи", "type": "shirt", "price": 200, "color": "#00d26a"},
    "pants_jeans": {"id": "pants_jeans", "name": "Джинсы", "type": "pants", "price": 150, "color": "#3742fa"},
    "pants_shorts": {"id": "pants_shorts", "name": "Шорты", "type": "pants", "price": 80, "color": "#ffa502"},
    "shoes_sneakers": {"id": "shoes_sneakers", "name": "Кроссовки", "type": "shoes", "price": 120, "color": "#ffffff"},
    "shoes_boots": {"id": "shoes_boots", "name": "Ботинки", "type": "shoes", "price": 180, "color": "#8B4513"},
    "face_glasses": {"id": "face_glasses", "name": "Очки", "type": "face", "price": 90, "color": "#333333"},
    "face_mask": {"id": "face_mask", "name": "Маска", "type": "face", "price": 250, "color": "#2ed573"},
    "back_wings": {"id": "back_wings", "name": "Крылья", "type": "back", "price": 1000, "color": "#a55eea"},
    "back_pack": {"id": "back_pack", "name": "Рюкзак", "type": "back", "price": 220, "color": "#ff6b00"},
}

# Донат-пакеты коинов (цена в рублях)
DONATE_PACKAGES = {
    "donat-90-koin": {
        "id": "donat-90-koin",
        "title": "90 коинов",
        "coins": 90,
        "price_rub": 50,
        "badge": "Старт",
        "description": "Небольшой пакет для старта",
    },
    "donat-300-koin": {
        "id": "donat-300-koin",
        "title": "300 коинов",
        "coins": 300,
        "price_rub": 150,
        "badge": "Выгодно",
        "description": "Больше коинов — выгоднее",
    },
}


def load_json(path, default=None):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return default if default is not None else {}
                return json.loads(content)
        except (json.JSONDecodeError, OSError):
            # Файл пустой/битый (например, сохранение прервалось) — не роняем сервер,
            # а откатываемся на пустое значение по умолчанию.
            return default if default is not None else {}
    return default if default is not None else {}


def save_json(path, data):
    # Пишем во временный файл и атомарно переименовываем, чтобы сбой/обрыв
    # записи посреди процесса никогда не оставлял битый/пустой JSON-файл.
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _ext_from_data_url(data_url):
    """Определяет расширение файла из data:image/...;base64,..."""
    m = re.match(r'^data:image/([\w+.-]+);base64,', str(data_url or ''), re.I)
    if not m:
        return 'jpg'
    fmt = m.group(1).lower()
    if fmt in ('jpeg', 'jpg'):
        return 'jpg'
    if fmt in ('png', 'gif', 'webp', 'bmp'):
        return fmt
    return 'jpg'


def save_game_image(data_url, folder, project_id, kind):
    """
    Сохраняет base64-картинку на диск в games/covers или games/photos.
    Возвращает публичный URL вида /games/covers/{id}_cover.jpg
    Если передан уже путь (/games/...), возвращает его как есть.
    """
    if not data_url:
        return ''
    s = str(data_url)
    # Уже сохранённый файл — не трогаем
    if s.startswith('/games/'):
        return s
    if not s.startswith('data:image'):
        return s  # неизвестный формат — оставляем как есть

    try:
        header, b64data = s.split(',', 1)
    except ValueError:
        return ''

    try:
        raw = base64.b64decode(b64data)
    except Exception:
        return ''

    if len(raw) > 1_500_000:  # ~1.5 МБ
        return ''

    ext = _ext_from_data_url(s)
    filename = f"{project_id}_{kind}.{ext}"
    path = os.path.join(folder, filename)
    with open(path, 'wb') as f:
        f.write(raw)

    sub = 'covers' if folder == COVERS_DIR else 'photos'
    return f"/games/{sub}/{filename}"


def delete_game_images(project):
    """Удаляет файлы обложки и фото игры с диска."""
    for key in ('cover', 'photo'):
        url = project.get(key) or ''
        if isinstance(url, str) and url.startswith('/games/'):
            # /games/covers/xxx.jpg -> games/covers/xxx.jpg
            rel = url.lstrip('/')
            full = os.path.join(BASE_DIR, rel)
            if os.path.isfile(full):
                try:
                    os.remove(full)
                except OSError:
                    pass


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token():
    return uuid.uuid4().hex


def get_user_by_token(token):
    if not token:
        return None
    sessions = load_json(SESSIONS_FILE, {})
    session = sessions.get(token)
    if not session:
        return None
    users = load_json(USERS_FILE, {})
    user = users.get(session.get('username'))
    if not user or user.get('is_banned'):
        return None
    return user


@app.route('/api/ping', methods=['GET'])
def api_ping():
    """Проверка, что сервер жив (клиент показывает ошибку 272, если нет ответа)."""
    return jsonify({'success': True, 'ok': True, 'ts': datetime.now().isoformat()})


# ==================== AUTH API ====================

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    birth_date = data.get('birth_date', '')
    gender = data.get('gender', '')

    if not username or not password:
        return jsonify({'success': False, 'error': 'Заполни все поля'}), 400
    if len(username) < 3:
        return jsonify({'success': False, 'error': 'Имя пользователя минимум 3 символа'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Пароль минимум 6 символов'}), 400

    users = load_json(USERS_FILE, {})
    if username.lower() in {u.lower() for u in users}:
        return jsonify({'success': False, 'error': 'Это имя уже занято'}), 409

    user_id = str(uuid.uuid4())
    users[username] = {
        'id': user_id,
        'username': username,
        'password_hash': hash_password(password),
        'birth_date': birth_date,
        'gender': gender,
        'created_at': datetime.now().isoformat(),
        'coins': 0,  # Стартовые коины
        'friends': [],
        'friend_requests': [],  # входящие заявки (список username)
        'profile_public': True,  # публичный профиль по умолчанию
        'followers': 0,
        'games_played': 0,
        'avatar_color': '#ff6b00',
        'avatar_parts': {
            'head': '#ffdbac',
            'torso': '#ff6b00',
            'left_arm': '#ffdbac',
            'right_arm': '#ffdbac',
            'left_leg': '#3742fa',
            'right_leg': '#3742fa'
        },
        'inventory': [],
        'equipped': {},
        'is_admin': False,
        'is_banned': False,
        'ban_reason': '',
        'is_muted': False,
        'mute_reason': ''
    }
    save_json(USERS_FILE, users)

    token = generate_token()
    sessions = load_json(SESSIONS_FILE, {})
    sessions[token] = {'user_id': user_id, 'username': username, 'created_at': datetime.now().isoformat()}
    save_json(SESSIONS_FILE, sessions)

    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': user_id,
            'username': username,
            'coins': 500
        }
    })


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'success': False, 'error': 'Заполни все поля'}), 400

    users = load_json(USERS_FILE, {})
    user = users.get(username)

    if not user or user['password_hash'] != hash_password(password):
        return jsonify({'success': False, 'error': 'Неверное имя пользователя или пароль'}), 401

    if user.get('is_banned'):
        reason = user.get('ban_reason') or 'нарушение правил Strovo'
        return jsonify({'success': False, 'error': f'Аккаунт заблокирован администрацией. Причина: {reason}', 'banned': True}), 403

    token = generate_token()
    sessions = load_json(SESSIONS_FILE, {})
    sessions[token] = {'user_id': user['id'], 'username': username, 'created_at': datetime.now().isoformat()}
    save_json(SESSIONS_FILE, sessions)

    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'coins': user.get('coins', 0)
        }
    })


@app.route('/api/me', methods=['GET'])
def api_me():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    verified = load_json(VERIFIED_FILE, {})
    is_verified = verified.get(user['username'], False)

    return jsonify({
        'success': True,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'coins': user.get('coins', 0),
            'friends': user.get('friends', []),
            'friend_requests': user.get('friend_requests', []),
            'profile_public': user.get('profile_public', True),
            'followers': user.get('followers', 0),
            'games_played': user.get('games_played', 0),
            'created_at': user.get('created_at', ''),
            'avatar_color': user.get('avatar_color', '#ff6b00'),
            'avatar_parts': user.get('avatar_parts', {}),
            'inventory': user.get('inventory', []),
            'equipped': user.get('equipped', {}),
            'owned_gamepasses': user.get('owned_gamepasses', {}),
            'verified': is_verified,
            'is_admin': user.get('is_admin', False),
            'is_muted': user.get('is_muted', False),
            'mute_reason': user.get('mute_reason', '')
        }
    })


@app.route('/api/logout', methods=['POST'])
def api_logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    sessions = load_json(SESSIONS_FILE, {})
    if token in sessions:
        del sessions[token]
        save_json(SESSIONS_FILE, sessions)
    return jsonify({'success': True})


# ==================== FRIENDS & PROFILE PRIVACY ====================

def _public_user_card(username, u, verified_map):
    return {
        'username': username,
        'avatar_color': u.get('avatar_color', '#ff6b00'),
        'verified': verified_map.get(username, False),
        'profile_public': u.get('profile_public', True),
        'friends_count': len(u.get('friends') or []),
        'created_at': u.get('created_at', ''),
    }


@app.route('/api/users/<username>', methods=['GET'])
def api_get_user_profile(username):
    """Публичный профиль. Приватный видят только владелец и друзья."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    me = get_user_by_token(token)
    users = load_json(USERS_FILE, {})
    # case-insensitive lookup
    target_name = None
    for uname in users:
        if uname.lower() == username.lower():
            target_name = uname
            break
    if not target_name:
        return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404

    u = users[target_name]
    verified = load_json(VERIFIED_FILE, {})
    is_owner = me and me.get('username') == target_name
    is_friend = bool(me and target_name in (me.get('friends') or []))
    is_public = u.get('profile_public', True)

    if not is_public and not is_owner and not is_friend:
        return jsonify({
            'success': True,
            'private': True,
            'user': {
                'username': target_name,
                'avatar_color': u.get('avatar_color', '#ff6b00'),
                'verified': verified.get(target_name, False),
                'profile_public': False,
            },
            'message': 'Этот профиль приватный'
        })

    # relation for current viewer
    relation = 'self' if is_owner else ('friend' if is_friend else 'none')
    if me and not is_owner and not is_friend:
        if me.get('username') in (u.get('friend_requests') or []):
            relation = 'outgoing'  # я уже отправил заявку ему
        elif target_name in (me.get('friend_requests') or []):
            relation = 'incoming'  # он отправил мне

    payload = {
        'username': target_name,
        'avatar_color': u.get('avatar_color', '#ff6b00'),
        'avatar_parts': u.get('avatar_parts', {}),
        'verified': verified.get(target_name, False),
        'profile_public': is_public,
        'friends': u.get('friends', []) if (is_owner or is_public or is_friend) else [],
        'friends_count': len(u.get('friends') or []),
        'followers': u.get('followers', 0),
        'created_at': u.get('created_at', ''),
        'games_played': u.get('games_played', 0),
    }
    if is_owner:
        payload['coins'] = u.get('coins', 0)
        payload['friend_requests'] = u.get('friend_requests', [])
        payload['inventory'] = u.get('inventory', [])
        payload['equipped'] = u.get('equipped', {})

    return jsonify({
        'success': True,
        'private': False,
        'relation': relation,
        'user': payload,
    })


@app.route('/api/friends', methods=['GET'])
def api_friends_list():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    me = get_user_by_token(token)
    if not me:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    users = load_json(USERS_FILE, {})
    verified = load_json(VERIFIED_FILE, {})
    me_full = users.get(me['username'], me)

    friends = []
    for fname in me_full.get('friends') or []:
        fu = users.get(fname)
        if fu:
            friends.append(_public_user_card(fname, fu, verified))
        else:
            friends.append({'username': fname, 'avatar_color': '#ff6b00', 'verified': False})

    incoming = []
    for rname in me_full.get('friend_requests') or []:
        ru = users.get(rname)
        if ru:
            incoming.append(_public_user_card(rname, ru, verified))
        else:
            incoming.append({'username': rname, 'avatar_color': '#ff6b00', 'verified': False})

    return jsonify({
        'success': True,
        'friends': friends,
        'incoming': incoming,
        'profile_public': me_full.get('profile_public', True),
    })


@app.route('/api/friends/request', methods=['POST'])
def api_friend_request():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    me = get_user_by_token(token)
    if not me:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    data = request.get_json() or {}
    target = (data.get('username') or '').strip()
    if not target:
        return jsonify({'success': False, 'error': 'Укажи ник'}), 400

    users = load_json(USERS_FILE, {})
    my_name = me['username']
    # resolve case
    target_name = None
    for uname in users:
        if uname.lower() == target.lower():
            target_name = uname
            break
    if not target_name:
        return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404
    if target_name == my_name:
        return jsonify({'success': False, 'error': 'Нельзя добавить себя'}), 400

    me_u = users[my_name]
    them = users[target_name]
    me_u.setdefault('friends', [])
    me_u.setdefault('friend_requests', [])
    them.setdefault('friends', [])
    them.setdefault('friend_requests', [])

    if target_name in me_u['friends']:
        return jsonify({'success': False, 'error': 'Уже в друзьях'}), 409
    if my_name in them['friend_requests']:
        return jsonify({'success': False, 'error': 'Заявка уже отправлена'}), 409

    # Если у меня уже есть входящая от него — сразу принимаем
    if target_name in me_u['friend_requests']:
        me_u['friend_requests'] = [x for x in me_u['friend_requests'] if x != target_name]
        if target_name not in me_u['friends']:
            me_u['friends'].append(target_name)
        if my_name not in them['friends']:
            them['friends'].append(my_name)
        save_json(USERS_FILE, users)
        return jsonify({'success': True, 'message': 'Теперь вы друзья', 'status': 'accepted'})

    them['friend_requests'].append(my_name)
    save_json(USERS_FILE, users)
    return jsonify({'success': True, 'message': 'Заявка отправлена', 'status': 'pending'})


@app.route('/api/friends/accept', methods=['POST'])
def api_friend_accept():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    me = get_user_by_token(token)
    if not me:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    data = request.get_json() or {}
    target = (data.get('username') or '').strip()
    users = load_json(USERS_FILE, {})
    my_name = me['username']
    me_u = users.get(my_name)
    them = users.get(target)
    if not me_u or not them:
        return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404

    me_u.setdefault('friends', [])
    me_u.setdefault('friend_requests', [])
    them.setdefault('friends', [])
    them.setdefault('friend_requests', [])

    if target not in me_u['friend_requests']:
        return jsonify({'success': False, 'error': 'Нет такой заявки'}), 404

    me_u['friend_requests'] = [x for x in me_u['friend_requests'] if x != target]
    if target not in me_u['friends']:
        me_u['friends'].append(target)
    if my_name not in them['friends']:
        them['friends'].append(my_name)
    # убрать встречную заявку если была
    them['friend_requests'] = [x for x in them.get('friend_requests', []) if x != my_name]
    save_json(USERS_FILE, users)
    return jsonify({'success': True, 'message': f'Вы теперь друзья с {target}'})


@app.route('/api/friends/decline', methods=['POST'])
def api_friend_decline():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    me = get_user_by_token(token)
    if not me:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    data = request.get_json() or {}
    target = (data.get('username') or '').strip()
    users = load_json(USERS_FILE, {})
    me_u = users.get(me['username'])
    if not me_u:
        return jsonify({'success': False, 'error': 'Ошибка'}), 400
    me_u['friend_requests'] = [x for x in me_u.get('friend_requests', []) if x != target]
    save_json(USERS_FILE, users)
    return jsonify({'success': True, 'message': 'Заявка отклонена'})


@app.route('/api/friends/remove', methods=['POST'])
def api_friend_remove():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    me = get_user_by_token(token)
    if not me:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    data = request.get_json() or {}
    target = (data.get('username') or '').strip()
    users = load_json(USERS_FILE, {})
    my_name = me['username']
    me_u = users.get(my_name)
    them = users.get(target)
    if me_u:
        me_u['friends'] = [x for x in me_u.get('friends', []) if x != target]
    if them:
        them['friends'] = [x for x in them.get('friends', []) if x != my_name]
    save_json(USERS_FILE, users)
    return jsonify({'success': True, 'message': 'Удалён из друзей'})


@app.route('/api/settings/privacy', methods=['POST'])
def api_settings_privacy():
    """profile_public: true = публичный, false = приватный"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    me = get_user_by_token(token)
    if not me:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    data = request.get_json() or {}
    if 'profile_public' not in data:
        return jsonify({'success': False, 'error': 'Укажи profile_public'}), 400

    users = load_json(USERS_FILE, {})
    u = users.get(me['username'])
    if not u:
        return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404

    u['profile_public'] = bool(data['profile_public'])
    save_json(USERS_FILE, users)
    return jsonify({
        'success': True,
        'profile_public': u['profile_public'],
        'message': 'Профиль публичный' if u['profile_public'] else 'Профиль приватный'
    })


@app.route('/api/users/search', methods=['GET'])
def api_users_search():
    q = (request.args.get('q') or '').strip().lower()
    if len(q) < 2:
        return jsonify({'success': True, 'users': []})
    users = load_json(USERS_FILE, {})
    verified = load_json(VERIFIED_FILE, {})
    results = []
    for uname, u in users.items():
        if q in uname.lower():
            results.append(_public_user_card(uname, u, verified))
            if len(results) >= 20:
                break
    return jsonify({'success': True, 'users': results})


# ==================== SETTINGS API ====================

USERNAME_CHANGE_COST = 1_000_000


@app.route('/api/settings/username', methods=['POST'])
def api_change_username():
    """Смена ника за 1 000 000 коинов."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    data = request.get_json() or {}
    new_name = (data.get('username') or '').strip()
    old_name = user['username']

    if not new_name:
        return jsonify({'success': False, 'error': 'Введи новый ник'}), 400
    if len(new_name) < 3:
        return jsonify({'success': False, 'error': 'Ник минимум 3 символа'}), 400
    if len(new_name) > 20:
        return jsonify({'success': False, 'error': 'Ник максимум 20 символов'}), 400
    if not all(c.isalnum() or c in '_-' for c in new_name):
        return jsonify({'success': False, 'error': 'Только буквы, цифры, _ и -'}), 400
    if new_name.lower() == old_name.lower():
        return jsonify({'success': False, 'error': 'Это уже твой ник'}), 400

    users = load_json(USERS_FILE, {})
    if new_name in users or any(u.lower() == new_name.lower() for u in users):
        return jsonify({'success': False, 'error': 'Этот ник уже занят'}), 409

    u = users.get(old_name)
    if not u:
        return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404

    if u.get('coins', 0) < USERNAME_CHANGE_COST:
        return jsonify({
            'success': False,
            'error': f'Недостаточно коинов. Нужно {USERNAME_CHANGE_COST:,}'.replace(',', ' ')
        }), 400

    # Переносим пользователя на новый ключ
    u['coins'] = u.get('coins', 0) - USERNAME_CHANGE_COST
    u['username'] = new_name
    users[new_name] = u
    del users[old_name]
    save_json(USERS_FILE, users)

    # Обновляем сессии
    sessions = load_json(SESSIONS_FILE, {})
    for tok, s in sessions.items():
        if s.get('username') == old_name:
            s['username'] = new_name
    save_json(SESSIONS_FILE, sessions)

    # Верификация
    verified = load_json(VERIFIED_FILE, {})
    if old_name in verified:
        verified[new_name] = verified.pop(old_name)
        save_json(VERIFIED_FILE, verified)

    # Владелец проектов
    projects = load_json(PROJECTS_FILE, {})
    changed = False
    for p in projects.values():
        if p.get('owner') == old_name:
            p['owner'] = new_name
            changed = True
    if changed:
        save_json(PROJECTS_FILE, projects)

    # Друзья у других пользователей
    for other in users.values():
        friends = other.get('friends') or []
        if old_name in friends:
            other['friends'] = [new_name if f == old_name else f for f in friends]
    save_json(USERS_FILE, users)

    return jsonify({
        'success': True,
        'username': new_name,
        'coins': u['coins'],
        'message': f'Ник изменён на {new_name}'
    })


@app.route('/api/settings/password', methods=['POST'])
def api_change_password():
    """Смена пароля бесплатно (нужен текущий пароль)."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    data = request.get_json() or {}
    current = data.get('current_password') or ''
    new_pass = data.get('new_password') or ''
    confirm = data.get('confirm_password') or ''

    if not current or not new_pass:
        return jsonify({'success': False, 'error': 'Заполни все поля'}), 400
    if len(new_pass) < 6:
        return jsonify({'success': False, 'error': 'Новый пароль минимум 6 символов'}), 400
    if new_pass != confirm:
        return jsonify({'success': False, 'error': 'Пароли не совпадают'}), 400

    users = load_json(USERS_FILE, {})
    u = users.get(user['username'])
    if not u:
        return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404

    if u.get('password_hash') != hash_password(current):
        return jsonify({'success': False, 'error': 'Неверный текущий пароль'}), 403

    if hash_password(new_pass) == u.get('password_hash'):
        return jsonify({'success': False, 'error': 'Новый пароль совпадает со старым'}), 400

    u['password_hash'] = hash_password(new_pass)
    save_json(USERS_FILE, users)

    return jsonify({'success': True, 'message': 'Пароль успешно изменён'})


# ==================== AVATAR API ====================

@app.route('/api/avatar', methods=['PUT'])
def api_update_avatar():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    data = request.get_json() or {}
    users = load_json(USERS_FILE, {})
    u = users.get(user['username'])

    if 'avatar_parts' in data:
        u['avatar_parts'] = {**u.get('avatar_parts', {}), **data['avatar_parts']}
    if 'equipped' in data:
        u['equipped'] = data['equipped']

    save_json(USERS_FILE, users)
    return jsonify({'success': True})


# ==================== SHOP API ====================

@app.route('/api/shop', methods=['GET'])
def api_shop():
    return jsonify({'success': True, 'items': list(SHOP_ITEMS.values())})


@app.route('/api/donate/packages', methods=['GET'])
def api_donate_packages():
    return jsonify({'success': True, 'packages': list(DONATE_PACKAGES.values())})


@app.route('/api/donate/<package_id>', methods=['POST'])
def api_donate_claim(package_id):
    """Зачисление коинов по донат-пакету (демо-оплата на localhost)."""
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

    return jsonify({
        'success': True,
        'coins': u['coins'],
        'added': pkg['coins'],
        'package': pkg['id'],
        'message': f"+{pkg['coins']} коинов зачислено"
    })


@app.route('/donat-90-koin')
@app.route('/donat-90-koin.html')
def page_donat_90():
    return send_from_directory(BASE_DIR, 'donat-90-koin.html')


@app.route('/donat-300-koin')
@app.route('/donat-300-koin.html')
def page_donat_300():
    return send_from_directory(BASE_DIR, 'donat-300-koin.html')


@app.route('/api/shop/buy', methods=['POST'])
def api_buy_item():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    data = request.get_json() or {}
    item_id = data.get('item_id')
    item = SHOP_ITEMS.get(item_id)
    if not item:
        return jsonify({'success': False, 'error': 'Предмет не найден'}), 404

    users = load_json(USERS_FILE, {})
    u = users.get(user['username'])

    if item_id in u.get('inventory', []):
        return jsonify({'success': False, 'error': 'Уже куплено'}), 409

    if u.get('coins', 0) < item['price']:
        return jsonify({'success': False, 'error': 'Недостаточно коинов'}), 400

    u['coins'] = u.get('coins', 0) - item['price']
    u['inventory'] = u.get('inventory', []) + [item_id]
    save_json(USERS_FILE, users)

    return jsonify({'success': True, 'coins': u['coins'], 'inventory': u['inventory']})


# ==================== VERIFIED (GALO) API ====================

@app.route('/api/verified', methods=['GET'])
def api_get_verified():
    username = request.args.get('username', '')
    if not username:
        return jsonify({'success': False, 'error': 'Укажи username'}), 400
    verified = load_json(VERIFIED_FILE, {})
    return jsonify({'success': True, 'verified': verified.get(username, False)})


@app.route('/api/verified', methods=['POST'])
def api_set_verified():
    # Для админов — в реальном приложении нужна проверка прав
    data = request.get_json() or {}
    username = data.get('username', '')
    status = data.get('status', False)
    if not username:
        return jsonify({'success': False, 'error': 'Укажи username'}), 400
    verified = load_json(VERIFIED_FILE, {})
    verified[username] = status
    save_json(VERIFIED_FILE, verified)
    return jsonify({'success': True, 'verified': status})


# ==================== STROVO STUDIO API ====================

@app.route('/api/projects', methods=['GET'])
def api_list_projects():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    projects = load_json(PROJECTS_FILE, {})
    dirty = False
    user_projects = []
    for pid, p in projects.items():
        if p.get('owner') != user['username']:
            continue
        if p.get('published') and ensure_play_url(p, pid, projects):
            dirty = True
        item = {**p, 'id': pid}
        if p.get('published'):
            item['url'] = game_public_url(p, pid)
        user_projects.append(item)
    if dirty:
        save_json(PROJECTS_FILE, projects)
    return jsonify({'success': True, 'projects': user_projects})


@app.route('/api/projects', methods=['POST'])
def api_create_project():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    data = request.get_json() or {}
    name = (data.get('name') or 'Новый проект').strip() or 'Новый проект'
    blocks = data.get('blocks', [])
    if not isinstance(blocks, list):
        blocks = []

    project_id = str(uuid.uuid4())
    projects = load_json(PROJECTS_FILE, {})
    projects[project_id] = {
        'name': name,
        'owner': user['username'],
        'blocks': blocks,
        'world_settings': data.get('world_settings', {'time': 'day', 'sky': 'blue'}),
        'published': False,
        'plays': 0,
        'likes': 0,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    save_json(PROJECTS_FILE, projects)

    return jsonify({'success': True, 'project': {'id': project_id, 'name': name}})


@app.route('/api/projects/<project_id>', methods=['GET'])
def api_get_project(project_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    projects = load_json(PROJECTS_FILE, {})
    project = projects.get(project_id)
    if not project:
        return jsonify({'success': False, 'error': 'Проект не найден'}), 404
    if project.get('owner') != user['username']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403

    return jsonify({'success': True, 'project': {**project, 'id': project_id}})


@app.route('/api/projects/<project_id>', methods=['PUT'])
def api_update_project(project_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    projects = load_json(PROJECTS_FILE, {})
    project = projects.get(project_id)
    if not project:
        return jsonify({'success': False, 'error': 'Проект не найден'}), 404
    if project.get('owner') != user['username']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403

    data = request.get_json() or {}
    project['name'] = data.get('name', project['name'])
    project['blocks'] = data.get('blocks', project.get('blocks', []))
    if 'world_settings' in data:
        project['world_settings'] = data['world_settings']
    project['updated_at'] = datetime.now().isoformat()
    save_json(PROJECTS_FILE, projects)

    return jsonify({'success': True, 'project': {'id': project_id, 'name': project['name']}})


@app.route('/api/projects/<project_id>', methods=['DELETE'])
def api_delete_project(project_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    projects = load_json(PROJECTS_FILE, {})
    project = projects.get(project_id)
    if not project:
        return jsonify({'success': False, 'error': 'Проект не найден'}), 404
    if project.get('owner') != user['username']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403

    delete_game_images(project)
    del projects[project_id]
    save_json(PROJECTS_FILE, projects)
    return jsonify({'success': True})


@app.route('/api/projects/<project_id>/publish', methods=['POST'])
def api_publish_project(project_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    projects = load_json(PROJECTS_FILE, {})
    project = projects.get(project_id)
    if not project:
        return jsonify({'success': False, 'error': 'Проект не найден'}), 404
    if project.get('owner') != user['username']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403

    data = request.get_json(silent=True) or {}
    description = (data.get('description') or project.get('description') or '').strip()
    cover = data.get('cover') or project.get('cover') or ''
    photo = data.get('photo') or project.get('photo') or ''

    if len(description) < 10:
        return jsonify({'success': False, 'error': 'Описание минимум 10 символов'}), 400
    if len(description) > 1000:
        return jsonify({'success': False, 'error': 'Описание максимум 1000 символов'}), 400

    # Принимаем либо data:image base64, либо уже сохранённый путь /games/...
    def _is_valid_image(val):
        s = str(val or '')
        return s.startswith('data:image') or s.startswith('/games/')

    if not _is_valid_image(cover):
        return jsonify({'success': False, 'error': 'Нужна обложка (картинка)'}), 400
    if not _is_valid_image(photo):
        return jsonify({'success': False, 'error': 'Нужно фото игры (картинка)'}), 400
    if str(cover).startswith('data:image') and len(str(cover)) > 1_500_000:
        return jsonify({'success': False, 'error': 'Обложка слишком большая (макс ~1 МБ)'}), 400
    if str(photo).startswith('data:image') and len(str(photo)) > 1_500_000:
        return jsonify({'success': False, 'error': 'Фото слишком большое (макс ~1 МБ)'}), 400

    # Сохраняем картинки в папку games/covers и games/photos
    cover_url = save_game_image(cover, COVERS_DIR, project_id, 'cover')
    photo_url = save_game_image(photo, PHOTOS_DIR, project_id, 'photo')
    if not cover_url:
        return jsonify({'success': False, 'error': 'Не удалось сохранить обложку'}), 400
    if not photo_url:
        return jsonify({'success': False, 'error': 'Не удалось сохранить фото'}), 400

    project['description'] = description
    project['cover'] = cover_url
    project['photo'] = photo_url
    project['published'] = True
    project['updated_at'] = datetime.now().isoformat()
    ensure_play_url(project, project_id, projects)
    save_json(PROJECTS_FILE, projects)
    return jsonify({
        'success': True,
        'published': True,
        'url': game_public_url(project, project_id),
        'play_code': project.get('play_code'),
        'play_slug': project.get('play_slug'),
        'description': description,
        'cover': cover_url,
        'photo': photo_url,
    })


@app.route('/api/projects/<project_id>/unpublish', methods=['POST'])
def api_unpublish_project(project_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    projects = load_json(PROJECTS_FILE, {})
    project = projects.get(project_id)
    if not project:
        return jsonify({'success': False, 'error': 'Проект не найден'}), 404
    if project.get('owner') != user['username']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403

    project['published'] = False
    project['updated_at'] = datetime.now().isoformat()
    save_json(PROJECTS_FILE, projects)
    return jsonify({'success': True, 'published': False})


# ==================== GAMES API ====================

import re as _re
import random as _random


def slugify_name(text):
    """Имя для URL: только латиница/цифры/дефис, нижний регистр."""
    text = (text or '').strip().lower()
    # транслит простых русских букв
    tr = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    out = []
    for ch in text:
        if ch in tr:
            out.append(tr[ch])
        elif ch.isascii() and (ch.isalnum() or ch in '-_'):
            out.append(ch)
        elif ch.isspace() or ch in '._/\\':
            out.append('-')
        else:
            out.append('')
    slug = _re.sub(r'-+', '-', ''.join(out)).strip('-')
    return slug or 'game'


def game_public_url(project, project_id=None):
    """Публичная ссылка на карточку/запуск (браузер → клиент)."""
    pid = project_id or project.get('id', '')
    return f"/game.html?id={pid}"


def game_launch_url(project, project_id=None):
    """Страница запуска клиента strovo://"""
    pid = project_id or project.get('id', '')
    code = str(project.get('play_code') or '')
    if pid:
        return f"/launch.html?id={pid}"
    if code:
        return f"/launch.html?code={code}"
    return "/download.html"


def ensure_play_url(project, project_id, projects):
    """Выдать случайный код и slug имени-ник, если ещё нет."""
    changed = False
    if not project.get('play_code'):
        # уникальный 6–8 значный код
        existing = {str(p.get('play_code')) for p in projects.values() if p.get('play_code')}
        for _ in range(50):
            code = str(_random.randint(100000, 99999999))
            if code not in existing:
                project['play_code'] = code
                changed = True
                break
        if not project.get('play_code'):
            project['play_code'] = str(uuid.uuid4().int)[:8]
            changed = True
    name_slug = slugify_name(project.get('name', 'game'))
    owner_slug = slugify_name(project.get('owner', 'player'))
    new_slug = f"{name_slug}-{owner_slug}"
    if project.get('play_slug') != new_slug:
        project['play_slug'] = new_slug
        changed = True
    return changed


@app.route('/api/games', methods=['GET'])
def api_list_games():
    projects = load_json(PROJECTS_FILE, {})
    users = load_json(USERS_FILE, {})
    verified = load_json(VERIFIED_FILE, {})
    published = []
    dirty = False
    for pid, p in projects.items():
        if p.get('published'):
            if ensure_play_url(p, pid, projects):
                dirty = True
            owner = users.get(p.get('owner'), {})
            published.append({
                'id': pid,
                'name': p['name'],
                'owner': p['owner'],
                'owner_avatar': owner.get('avatar_color', '#ff6b00'),
                'owner_verified': verified.get(p.get('owner'), False),
                'blocks_count': len(p.get('blocks', [])),
                'plays': p.get('plays', 0),
                'likes': p.get('likes', 0),
                'world_settings': p.get('world_settings', {}),
                'created_at': p.get('created_at', ''),
                'updated_at': p.get('updated_at', ''),
                'play_code': p.get('play_code'),
                'play_slug': p.get('play_slug'),
                'url': game_public_url(p, pid),
                'description': p.get('description', ''),
                'cover': p.get('cover', ''),
                'photo': p.get('photo', ''),
                'gamepasses': p.get('gamepasses', []),
            })
    if dirty:
        save_json(PROJECTS_FILE, projects)
    published.sort(key=lambda x: x['plays'], reverse=True)
    return jsonify({'success': True, 'games': published})


def _find_project_by_code(projects, code):
    code = str(code)
    for pid, p in projects.items():
        if str(p.get('play_code')) == code:
            return pid, p
    return None, None


@app.route('/api/games/by-code/<code>', methods=['GET'])
def api_get_game_by_code(code):
    projects = load_json(PROJECTS_FILE, {})
    pid, project = _find_project_by_code(projects, code)
    if not project or not project.get('published'):
        return jsonify({'success': False, 'error': 'Игра не найдена'}), 404
    ensure_play_url(project, pid, projects)
    project['plays'] = project.get('plays', 0) + 1
    save_json(PROJECTS_FILE, projects)
    users = load_json(USERS_FILE, {})
    verified = load_json(VERIFIED_FILE, {})
    owner = users.get(project.get('owner'), {})
    return jsonify({
        'success': True,
        'game': {
            **project,
            'id': pid,
            'owner_avatar': owner.get('avatar_color', '#ff6b00'),
            'owner_verified': verified.get(project.get('owner'), False),
            'url': game_public_url(project, pid),
        }
    })


def _request_is_strovo_client():
    """Клиент: ?client=1, cookie, или User-Agent."""
    if request.args.get('client') == '1':
        return True
    if request.cookies.get('strovo_client') == '1':
        return True
    ua = request.headers.get('User-Agent') or ''
    if 'StrovoClient' in ua or 'Electron' in ua:
        return True
    return False


@app.route('/games/<code>')
@app.route('/games/<code>/')
@app.route('/games/<code>/<slug>')
def page_play_pretty(code, slug=None):
    """Красивый URL: браузер → launch (клиент), клиент → play.html"""
    # Обложки/фото — отдаём файл, НЕ редирект (иначе 302-цикл)
    if code in ('covers', 'photos'):
        rel = code + ('/' + slug if slug else '')
        safe = os.path.normpath(rel).replace('\\', '/').lstrip('/')
        if safe.startswith('..') or '/../' in '/' + safe:
            return jsonify({'error': 'Forbidden'}), 403
        full = os.path.join(GAMES_DIR, safe)
        if os.path.isfile(full):
            mime, _ = mimetypes.guess_type(full)
            return send_file(full, mimetype=mime or 'application/octet-stream')
        return jsonify({'error': 'Not found'}), 404

    projects = load_json(PROJECTS_FILE, {})
    pid, project = _find_project_by_code(projects, code)
    if not project or not project.get('published'):
        return redirect('/games.html')

    ensure_play_url(project, pid, projects)
    save_json(PROJECTS_FILE, projects)

    if _request_is_strovo_client():
        # Клиент играет в webview
        return redirect(f'/play.html?id={pid}&client=1')

    # Браузер — только запуск клиента
    return redirect(game_launch_url(project, pid))


@app.route('/play.html')
def page_play_redirect():
    """Браузер → launch.html; клиент (?client=1) → сама игра."""
    game_id = request.args.get('id') or ''
    if _request_is_strovo_client():
        return send_from_directory(BASE_DIR, 'play.html')
    if game_id:
        return redirect(f'/launch.html?id={game_id}')
    return redirect('/download.html')


@app.route('/api/games/<game_id>', methods=['GET'])
def api_get_game(game_id):
    projects = load_json(PROJECTS_FILE, {})
    project = projects.get(game_id)
    if not project or not project.get('published'):
        return jsonify({'success': False, 'error': 'Игра не найдена'}), 404

    ensure_play_url(project, game_id, projects)
    project['plays'] = project.get('plays', 0) + 1
    save_json(PROJECTS_FILE, projects)

    users = load_json(USERS_FILE, {})
    verified = load_json(VERIFIED_FILE, {})
    owner = users.get(project.get('owner'), {})

    return jsonify({
        'success': True,
        'game': {
            'id': game_id,
            'name': project['name'],
            'owner': project['owner'],
            'owner_avatar': owner.get('avatar_color', '#ff6b00'),
            'owner_verified': verified.get(project.get('owner'), False),
            'blocks': project.get('blocks', []),
            'world_settings': project.get('world_settings', {}),
            'plays': project['plays'],
            'likes': project.get('likes', 0),
            'created_at': project.get('created_at', ''),
            'updated_at': project.get('updated_at', ''),
            'play_code': project.get('play_code'),
            'play_slug': project.get('play_slug'),
            'url': game_public_url(project, game_id),
            'description': project.get('description', ''),
            'cover': project.get('cover', ''),
            'photo': project.get('photo', ''),
            'gamepasses': project.get('gamepasses', []),
        }
    })


# ==================== GAME PASSES (геймпасы) ====================

@app.route('/api/projects/<project_id>/gamepasses', methods=['GET'])
def api_list_gamepasses(project_id):
    projects = load_json(PROJECTS_FILE, {})
    project = projects.get(project_id)
    if not project:
        return jsonify({'success': False, 'error': 'Проект не найден'}), 404
    return jsonify({'success': True, 'gamepasses': project.get('gamepasses', [])})


@app.route('/api/projects/<project_id>/gamepasses', methods=['POST'])
def api_create_gamepass(project_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    projects = load_json(PROJECTS_FILE, {})
    project = projects.get(project_id)
    if not project:
        return jsonify({'success': False, 'error': 'Проект не найден'}), 404
    if project.get('owner') != user['username']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403

    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip()
    try:
        price = int(data.get('price', 0))
    except (TypeError, ValueError):
        price = 0

    if len(name) < 2:
        return jsonify({'success': False, 'error': 'Название минимум 2 символа'}), 400
    if len(name) > 60:
        return jsonify({'success': False, 'error': 'Название максимум 60 символов'}), 400
    if len(description) > 300:
        return jsonify({'success': False, 'error': 'Описание максимум 300 символов'}), 400
    if price < 0 or price > 1_000_000:
        return jsonify({'success': False, 'error': 'Цена от 0 до 1 000 000'}), 400

    passes = project.setdefault('gamepasses', [])
    if len(passes) >= 50:
        return jsonify({'success': False, 'error': 'Максимум 50 геймпасов на игру'}), 400

    gp = {
        'id': uuid.uuid4().hex[:12],
        'name': name,
        'description': description,
        'price': price,
        'created_at': datetime.now().isoformat(),
    }
    passes.append(gp)
    project['updated_at'] = datetime.now().isoformat()
    save_json(PROJECTS_FILE, projects)
    return jsonify({'success': True, 'gamepass': gp, 'gamepasses': passes})


@app.route('/api/projects/<project_id>/gamepasses/<pass_id>', methods=['PUT'])
def api_update_gamepass(project_id, pass_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    projects = load_json(PROJECTS_FILE, {})
    project = projects.get(project_id)
    if not project:
        return jsonify({'success': False, 'error': 'Проект не найден'}), 404
    if project.get('owner') != user['username']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403

    passes = project.get('gamepasses', [])
    gp = next((p for p in passes if p.get('id') == pass_id), None)
    if not gp:
        return jsonify({'success': False, 'error': 'Геймпас не найден'}), 404

    data = request.get_json(silent=True) or {}
    if 'name' in data:
        name = (data.get('name') or '').strip()
        if len(name) < 2 or len(name) > 60:
            return jsonify({'success': False, 'error': 'Название 2–60 символов'}), 400
        gp['name'] = name
    if 'description' in data:
        description = (data.get('description') or '').strip()
        if len(description) > 300:
            return jsonify({'success': False, 'error': 'Описание максимум 300 символов'}), 400
        gp['description'] = description
    if 'price' in data:
        try:
            price = int(data.get('price', 0))
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'Некорректная цена'}), 400
        if price < 0 or price > 1_000_000:
            return jsonify({'success': False, 'error': 'Цена от 0 до 1 000 000'}), 400
        gp['price'] = price

    project['updated_at'] = datetime.now().isoformat()
    save_json(PROJECTS_FILE, projects)
    return jsonify({'success': True, 'gamepass': gp, 'gamepasses': passes})


@app.route('/api/projects/<project_id>/gamepasses/<pass_id>', methods=['DELETE'])
def api_delete_gamepass(project_id, pass_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    projects = load_json(PROJECTS_FILE, {})
    project = projects.get(project_id)
    if not project:
        return jsonify({'success': False, 'error': 'Проект не найден'}), 404
    if project.get('owner') != user['username']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403

    passes = project.get('gamepasses', [])
    new_passes = [p for p in passes if p.get('id') != pass_id]
    if len(new_passes) == len(passes):
        return jsonify({'success': False, 'error': 'Геймпас не найден'}), 404
    project['gamepasses'] = new_passes
    project['updated_at'] = datetime.now().isoformat()
    save_json(PROJECTS_FILE, projects)
    return jsonify({'success': True, 'gamepasses': new_passes})


@app.route('/api/games/<game_id>/gamepasses/buy', methods=['POST'])
def api_buy_gamepass(game_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    data = request.get_json(silent=True) or {}
    pass_id = (data.get('pass_id') or '').strip()
    if not pass_id:
        return jsonify({'success': False, 'error': 'Укажи pass_id'}), 400

    projects = load_json(PROJECTS_FILE, {})
    project = projects.get(game_id)
    if not project or not project.get('published'):
        return jsonify({'success': False, 'error': 'Игра не найдена'}), 404

    gp = next((p for p in project.get('gamepasses', []) if p.get('id') == pass_id), None)
    if not gp:
        return jsonify({'success': False, 'error': 'Геймпас не найден'}), 404

    users = load_json(USERS_FILE, {})
    u = users.get(user['username'])
    if not u:
        return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404

    owned = u.setdefault('owned_gamepasses', {})
    game_owned = owned.setdefault(game_id, [])
    if pass_id in game_owned:
        return jsonify({'success': False, 'error': 'Уже куплено', 'owned': True}), 400

    price = int(gp.get('price', 0))
    if u.get('coins', 0) < price:
        return jsonify({'success': False, 'error': 'Недостаточно коинов'}), 400

    u['coins'] = int(u.get('coins', 0)) - price
    game_owned.append(pass_id)
    save_json(USERS_FILE, users)

    # Автору игры — 90% от цены (остальное «комиссия платформы»)
    owner_name = project.get('owner')
    if owner_name and owner_name != user['username'] and price > 0:
        owner = users.get(owner_name)
        if owner:
            payout = max(0, int(price * 0.9))
            owner['coins'] = int(owner.get('coins', 0)) + payout
            save_json(USERS_FILE, users)

    return jsonify({
        'success': True,
        'coins': u['coins'],
        'pass_id': pass_id,
        'owned_gamepasses': game_owned,
    })


@app.route('/api/games/<game_id>/like', methods=['POST'])
def api_like_game(game_id):
    projects = load_json(PROJECTS_FILE, {})
    project = projects.get(game_id)
    if not project or not project.get('published'):
        return jsonify({'success': False, 'error': 'Игра не найдена'}), 404

    project['likes'] = project.get('likes', 0) + 1
    save_json(PROJECTS_FILE, projects)
    return jsonify({'success': True, 'likes': project['likes']})


# ==================== IN-GAME PRESENCE (online players) ====================
# In-memory: game_id -> { username: { last_seen, x, y, z, rot, avatar_parts, verified, is_admin, voice } }
PRESENCE = {}
PRESENCE_TTL_SEC = 20

# WebRTC signaling for voice chat
RTC_SIGNALS = {}  # game_id -> [ { id, from, to, type, payload, ts } ]
RTC_SIGNAL_TTL_SEC = 30
MAX_RTC_SIGNALS_PER_ROOM = 200


def _presence_cleanup(game_id):
    now = datetime.now().timestamp()
    room = PRESENCE.get(game_id, {})
    dead = [u for u, p in room.items() if now - p.get('last_seen', 0) > PRESENCE_TTL_SEC]
    for u in dead:
        del room[u]
    if not room and game_id in PRESENCE:
        del PRESENCE[game_id]


def _rtc_cleanup(game_id):
    now = datetime.now().timestamp()
    signals = RTC_SIGNALS.get(game_id, [])
    signals = [s for s in signals if now - s.get('ts', 0) <= RTC_SIGNAL_TTL_SEC]
    if signals:
        RTC_SIGNALS[game_id] = signals[-MAX_RTC_SIGNALS_PER_ROOM:]
    elif game_id in RTC_SIGNALS:
        del RTC_SIGNALS[game_id]


@app.route('/api/games/<game_id>/presence', methods=['POST'])
def api_post_presence(game_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    data = request.get_json() or {}
    verified = load_json(VERIFIED_FILE, {})
    # Имя устройства: Strovo-PCNAME (латиница)
    device = (data.get('device') or data.get('device_name') or '').strip()
    if device and not device.startswith('Strovo-'):
        device = 'Strovo-' + device
    if len(device) > 64:
        device = device[:64]
    room = PRESENCE.setdefault(game_id, {})
    room[user['username']] = {
        'last_seen': datetime.now().timestamp(),
        'x': float(data.get('x', 0)),
        'y': float(data.get('y', 0)),
        'z': float(data.get('z', 0)),
        'rot': float(data.get('rot', 0)),
        'avatar_parts': data.get('avatar_parts') or user.get('avatar_parts') or {},
        'verified': verified.get(user['username'], False),
        'is_admin': user.get('is_admin', False),
        'voice': bool(data.get('voice', False)),
        'device': device or None,
    }
    _presence_cleanup(game_id)
    return jsonify({'success': True, 'device': device or None})


@app.route('/api/games/<game_id>/presence', methods=['GET'])
def api_get_presence(game_id):
    _presence_cleanup(game_id)
    room = PRESENCE.get(game_id, {})
    players = []
    for username, p in room.items():
        players.append({
            'username': username,
            'x': p.get('x', 0),
            'y': p.get('y', 0),
            'z': p.get('z', 0),
            'rot': p.get('rot', 0),
            'avatar_parts': p.get('avatar_parts') or {},
            'verified': p.get('verified', False),
            'is_admin': p.get('is_admin', False),
            'voice': p.get('voice', False),
            'device': p.get('device'),
        })
    players.sort(key=lambda p: p['username'].lower())
    return jsonify({'success': True, 'players': players, 'count': len(players)})


@app.route('/api/games/<game_id>/presence/leave', methods=['POST'])
def api_leave_presence(game_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        data = request.get_json(silent=True) or {}
        token = data.get('token') or request.args.get('token') or ''
    user = get_user_by_token(token)
    if user:
        room = PRESENCE.get(game_id, {})
        if user['username'] in room:
            del room[user['username']]
        # очистить сигналы от/к этому пользователю
        signals = RTC_SIGNALS.get(game_id, [])
        RTC_SIGNALS[game_id] = [
            s for s in signals
            if s.get('from') != user['username'] and s.get('to') != user['username']
        ]
    return jsonify({'success': True})


# ==================== VOICE CHAT (WebRTC signaling) ====================

@app.route('/api/games/<game_id>/rtc', methods=['POST'])
def api_rtc_signal(game_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    data = request.get_json() or {}
    sig_type = (data.get('type') or '').strip()
    to_user = (data.get('to') or '').strip()
    payload = data.get('payload')
    if sig_type not in ('offer', 'answer', 'ice', 'hangup'):
        return jsonify({'success': False, 'error': 'Неверный тип сигнала'}), 400
    if not to_user:
        return jsonify({'success': False, 'error': 'Не указан получатель'}), 400
    if to_user == user['username']:
        return jsonify({'success': False, 'error': 'Нельзя слать себе'}), 400

    signal = {
        'id': uuid.uuid4().hex,
        'from': user['username'],
        'to': to_user,
        'type': sig_type,
        'payload': payload,
        'ts': datetime.now().timestamp(),
    }
    room = RTC_SIGNALS.setdefault(game_id, [])
    room.append(signal)
    _rtc_cleanup(game_id)
    return jsonify({'success': True, 'id': signal['id']})


@app.route('/api/games/<game_id>/rtc', methods=['GET'])
def api_rtc_poll(game_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    _rtc_cleanup(game_id)
    after_id = request.args.get('after_id') or ''
    room = RTC_SIGNALS.get(game_id, [])

    # Только сообщения адресованные текущему пользователю
    mine = [s for s in room if s.get('to') == user['username']]
    if after_id:
        idx = next((i for i, s in enumerate(mine) if s['id'] == after_id), None)
        if idx is not None:
            mine = mine[idx + 1:]
        else:
            # after_id не найден — отдаём только свежие (последние 20)
            mine = mine[-20:]

    return jsonify({'success': True, 'signals': mine})


# ==================== IN-GAME CHAT API ====================

CHATS_FILE = os.path.join(DATA_DIR, 'chats.json')
MAX_CHAT_MESSAGES = 100


@app.route('/api/games/<game_id>/chat', methods=['GET'])
def api_get_chat(game_id):
    chats = load_json(CHATS_FILE, {})
    messages = chats.get(game_id, [])

    after_id = request.args.get('after_id')
    if after_id:
        idx = next((i for i, m in enumerate(messages) if m['id'] == after_id), None)
        messages = messages[idx + 1:] if idx is not None else messages[-30:]
    else:
        messages = messages[-30:]

    return jsonify({'success': True, 'messages': messages})


@app.route('/api/games/<game_id>/chat', methods=['POST'])
def api_post_chat(game_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401

    if user.get('is_muted'):
        reason = user.get('mute_reason') or 'нарушение правил чата'
        return jsonify({'success': False, 'error': f'Вы в муте и не можете писать в чат. Причина: {reason}'}), 403

    data = request.get_json() or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'success': False, 'error': 'Пустое сообщение'}), 400
    text = text[:300]  # защита от гигантских сообщений

    verified = load_json(VERIFIED_FILE, {})
    message = {
        'id': uuid.uuid4().hex,
        'username': user['username'],
        'text': text,
        'ts': datetime.now().isoformat(),
        'verified': verified.get(user['username'], False),
        'is_admin': user.get('is_admin', False)
    }

    chats = load_json(CHATS_FILE, {})
    room = chats.setdefault(game_id, [])
    room.append(message)
    chats[game_id] = room[-MAX_CHAT_MESSAGES:]
    save_json(CHATS_FILE, chats)

    return jsonify({'success': True, 'message': message})


# ==================== STATIC FILES ====================

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/css/<path:path>')
def css_files(path):
    return send_file(os.path.join(BASE_DIR, 'css', path), mimetype='text/css')


@app.route('/js/<path:path>')
def js_files(path):
    return send_file(os.path.join(BASE_DIR, 'js', path), mimetype='application/javascript')


@app.route('/images/<path:path>')
def image_files(path):
    mime, _ = mimetypes.guess_type(path)
    return send_file(os.path.join(BASE_DIR, 'images', path), mimetype=mime or 'image/png')


@app.route('/games/<path:path>')
def game_files(path):
    """Раздача обложек и фото игр из папки games/"""
    # path вида covers/xxx.jpg или photos/xxx.jpg
    safe = os.path.normpath(path).replace('\\', '/').lstrip('/')
    if safe.startswith('..') or '/../' in '/' + safe:
        return jsonify({'error': 'Forbidden'}), 403
    full = os.path.join(GAMES_DIR, safe)
    if not full.startswith(GAMES_DIR) or not os.path.isfile(full):
        return jsonify({'error': 'Not found'}), 404
    mime, _ = mimetypes.guess_type(full)
    return send_file(full, mimetype=mime or 'application/octet-stream')


@app.route('/downloads/<path:path>')
def download_files(path):
    """Раздача клиента Strovo.exe и связанных файлов."""
    safe = os.path.normpath(path).replace('\\', '/').lstrip('/')
    if safe.startswith('..') or '/../' in '/' + safe:
        return jsonify({'error': 'Forbidden'}), 403
    full = os.path.join(DOWNLOADS_DIR, safe)
    if not full.startswith(DOWNLOADS_DIR) or not os.path.isfile(full):
        return jsonify({'error': 'Not found'}), 404
    mime, _ = mimetypes.guess_type(full)
    # force download for exe/zip
    return send_file(
        full,
        mimetype=mime or 'application/octet-stream',
        as_attachment=True,
        download_name=os.path.basename(full),
    )


@app.route('/api/client/download-info', methods=['GET'])
def api_client_download_info():
    """Какие файлы клиента доступны для скачивания."""
    candidates_exe = [
        'Strovo-Setup.exe', 'Strovo.exe', 'strovo-setup.exe', 'strovo.exe',
    ]
    candidates_zip = [
        'Strovo-Client.zip', 'Strovo.exe.zip', 'strovo-exe.zip', 'strovo-client.zip',
    ]
    exe_name = next((n for n in candidates_exe if os.path.isfile(os.path.join(DOWNLOADS_DIR, n))), None)
    zip_name = next((n for n in candidates_zip if os.path.isfile(os.path.join(DOWNLOADS_DIR, n))), None)
    # любой .exe / .zip в downloads/
    if not exe_name:
        for f in os.listdir(DOWNLOADS_DIR) if os.path.isdir(DOWNLOADS_DIR) else []:
            if f.lower().endswith('.exe'):
                exe_name = f
                break
    if not zip_name:
        for f in os.listdir(DOWNLOADS_DIR) if os.path.isdir(DOWNLOADS_DIR) else []:
            if f.lower().endswith('.zip'):
                zip_name = f
                break
    return jsonify({
        'success': True,
        'has_exe': bool(exe_name),
        'has_zip': bool(zip_name),
        'exe_url': f'/downloads/{exe_name}' if exe_name else None,
        'zip_url': f'/downloads/{zip_name}' if zip_name else None,
        'log_path': r'C:\strovo-log',
    })


@app.route('/<path:path>')
def static_files(path):
    safe_path = os.path.normpath(path).lstrip('/')
    full_path = os.path.join(BASE_DIR, safe_path)
    if not full_path.startswith(BASE_DIR):
        return send_from_directory(BASE_DIR, 'index.html')
    if os.path.exists(full_path) and os.path.isfile(full_path):
        mime, _ = mimetypes.guess_type(full_path)
        return send_file(full_path, mimetype=mime)
    return send_from_directory(BASE_DIR, 'index.html')


if __name__ == '__main__':
    print("=" * 50)
    print("  STROVO SERVER v0.0.2.V")
    print(f"  Папка: {BASE_DIR}")
    print("  Открой: http://localhost:5000 ")
    print("  Открой админ панель: http://localhost:5050")
    print(" Старая версия сайта")
    print("==================================================")
    app.run(host='0.0.0.0', port=5000, debug=True)
