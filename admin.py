#!/usr/bin/env python3
"""
Strovo Admin Panel — админка для управления пользователями и играми.

Работает НАПРЯМУЮ с теми же JSON-файлами, что и server.py (папки datag/ и galo/),
поэтому admin.py должен лежать в той же папке, что и server.py.

Запуск (рядом с server.py, ОТДЕЛЬНО от него, на другом порту):

    python3 admin.py

По умолчанию поднимается на http://localhost:5050/admin

Пароль берётся из переменной окружения STROVO_ADMIN_PASSWORD.
Если её не задать — используется пароль по умолчанию 'admin123'.
ОБЯЗАТЕЛЬНО смени его перед тем, как выкладывать сайт куда-либо публично:

    export STROVO_ADMIN_PASSWORD="твой-длинный-пароль"
    python3 admin.py
"""

import os
import json
import secrets
import hashlib
from datetime import datetime
from flask import Flask, request, redirect, url_for, session, render_template_string

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

DEFAULT_ADMIN_PASSWORD = os.environ.get('STROVO_ADMIN_PASSWORD', 'admin123')
SERVER_MODEL = os.environ.get('STROVO_SERVER_MODEL', 'zxer-pont-90880')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'datag')
GALO_DIR = os.path.join(BASE_DIR, 'galo')
GAMES_DIR = os.path.join(BASE_DIR, 'games')
COVERS_DIR = os.path.join(GAMES_DIR, 'covers')
PHOTOS_DIR = os.path.join(GAMES_DIR, 'photos')
ADMIN_LOG_FILE = os.path.join(DATA_DIR, 'admin_log.json')
ADMIN_AUTH_FILE = os.path.join(DATA_DIR, 'admin_auth.json')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(GALO_DIR, exist_ok=True)
os.makedirs(COVERS_DIR, exist_ok=True)
os.makedirs(PHOTOS_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, 'users.json')
SESSIONS_FILE = os.path.join(DATA_DIR, 'sessions.json')
PROJECTS_FILE = os.path.join(DATA_DIR, 'projects.json')
CHATS_FILE = os.path.join(DATA_DIR, 'chats.json')
VERIFIED_FILE = os.path.join(GALO_DIR, 'verified.json')


def load_json(path, default=None):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return default if default is not None else {}
                return json.loads(content)
        except (json.JSONDecodeError, OSError):
            return default if default is not None else {}
    return default if default is not None else {}


def save_json(path, data):
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def append_admin_log(action, detail=''):
    logs = load_json(ADMIN_LOG_FILE, [])
    if not isinstance(logs, list):
        logs = []
    logs.append({
        'ts': datetime.now().isoformat(timespec='seconds'),
        'action': str(action)[:80],
        'detail': str(detail)[:400],
    })
    if len(logs) > 500:
        logs = logs[-500:]
    save_json(ADMIN_LOG_FILE, logs)


def load_admin_auth():
    data = load_json(ADMIN_AUTH_FILE, {}) or {}
    if not isinstance(data, dict):
        return {}
    return data


def is_admin_setup_done():
    """Первый запуск = регистрации ещё не было."""
    data = load_admin_auth()
    return bool(data.get('setup_done') and data.get('password_hash'))


def get_server_model():
    data = load_admin_auth()
    return data.get('server_model') or SERVER_MODEL


def get_admin_password_hash():
    data = load_admin_auth()
    h = data.get('password_hash')
    if h:
        return h
    # Старые установки без setup_done — совместимость с admin123 / env
    return hash_password(DEFAULT_ADMIN_PASSWORD)


def check_admin_password(password):
    if not password:
        return False
    expected = get_admin_password_hash()
    try:
        return secrets.compare_digest(hash_password(password), expected)
    except Exception:
        return False


def complete_admin_setup(new_password, server_model=None):
    """Первая регистрация пароля админки."""
    save_json(ADMIN_AUTH_FILE, {
        'setup_done': True,
        'password_hash': hash_password(new_password),
        'server_model': (server_model or SERVER_MODEL).strip() or SERVER_MODEL,
        'updated_at': datetime.now().isoformat(timespec='seconds'),
    })


def set_admin_password(new_password):
    data = load_admin_auth()
    data['setup_done'] = True
    data['password_hash'] = hash_password(new_password)
    data['server_model'] = data.get('server_model') or SERVER_MODEL
    data['updated_at'] = datetime.now().isoformat(timespec='seconds')
    save_json(ADMIN_AUTH_FILE, data)


def is_logged_in():
    return session.get('admin_ok') is True


def kick_user_sessions(username):
    """Немедленно убивает все активные токены пользователя (для мгновенного бана)."""
    sessions = load_json(SESSIONS_FILE, {})
    sessions = {tok: s for tok, s in sessions.items() if s.get('username') != username}
    save_json(SESSIONS_FILE, sessions)


def delete_game_images(project):
    """Удаляет файлы обложки и фото игры с диска (games/covers, games/photos)."""
    for key in ('cover', 'photo'):
        url = project.get(key) or ''
        if isinstance(url, str) and url.startswith('/games/'):
            rel = url.lstrip('/')
            full = os.path.join(BASE_DIR, rel)
            if os.path.isfile(full):
                try:
                    os.remove(full)
                except OSError:
                    pass


def delete_user_account(username):
    """Полностью удаляет аккаунт пользователя с сервера."""
    # 1. Пользователь
    users = load_json(USERS_FILE, {})
    if username in users:
        del users[username]
        save_json(USERS_FILE, users)

    # 2. Сессии
    kick_user_sessions(username)

    # 3. Верификация
    verified = load_json(VERIFIED_FILE, {})
    if username in verified:
        del verified[username]
        save_json(VERIFIED_FILE, verified)

    # 4. Сообщения пользователя в чатах (оставляем комнаты, чистим только его сообщения)
    chats = load_json(CHATS_FILE, {})
    changed = False
    for gid, messages in list(chats.items()):
        new_msgs = [m for m in messages if m.get('username') != username]
        if len(new_msgs) != len(messages):
            chats[gid] = new_msgs
            changed = True
    if changed:
        save_json(CHATS_FILE, chats)

    # 5. Проекты пользователя (удаляем полностью + файлы обложек)
    projects = load_json(PROJECTS_FILE, {})
    to_del = [pid for pid, p in projects.items() if p.get('owner') == username]
    for pid in to_del:
        delete_game_images(projects[pid])
        del projects[pid]
    if to_del:
        save_json(PROJECTS_FILE, projects)


# ==================== ШАБЛОНЫ ====================

BASE_STYLE = """
<style>
    :root {
        --primary: #ff6b00; --primary-hover: #e66000; --secondary: #00b2ff;
        --bg: #0d0d0d; --bg-light: #16161a; --bg-card: #1e1e24; --bg-hover: #2a2a32;
        --text: #ffffff; --text-muted: #a0a0b0; --border: #2a2a35;
        --success: #00d26a; --warning: #ffc107; --danger: #ff4757;
        --radius: 12px; --radius-sm: 8px;
    }
    * { box-sizing: border-box; }
    body {
        margin: 0; background: var(--bg); color: var(--text);
        font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
    }
    .wrap { max-width: 1100px; margin: 0 auto; padding: 32px 20px; }
    h1 { font-size: 22px; display:flex; align-items:center; gap:10px; }
    h1 span.logo { color: var(--primary); }
    a { color: var(--secondary); }
    .card {
        background: var(--bg-card); border: 1px solid var(--border);
        border-radius: var(--radius); padding: 20px; margin-bottom: 20px;
    }
    input[type=text], input[type=password], input[type=number] {
        background: var(--bg-light); border: 1px solid var(--border); color: var(--text);
        padding: 9px 12px; border-radius: var(--radius-sm); font-size: 14px;
    }
    button, .btn {
        background: var(--bg-hover); border: 1px solid var(--border); color: var(--text);
        padding: 7px 12px; border-radius: var(--radius-sm); font-size: 13px; cursor: pointer;
        font-weight: 600; white-space: nowrap;
    }
    button:hover, .btn:hover { background: var(--border); }
    .btn-primary { background: var(--primary); border-color: var(--primary); color: #fff; }
    .btn-primary:hover { background: var(--primary-hover); }
    .btn-danger { background: var(--danger); border-color: var(--danger); color: #fff; }
    .btn-success { background: var(--success); border-color: var(--success); color: #062; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 10px 8px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: middle; }
    th { color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 11px; }
    tr:hover { background: var(--bg-hover); }
    .badge { padding: 2px 8px; border-radius: 100px; font-size: 11px; font-weight: 700; }
    .badge-verified {
        background: rgba(29,161,242,.15); color: #1da1f2;
        display: inline-flex; align-items: center; gap: 5px;
    }
    .badge-verified .v-icon {
        width: 14px; height: 14px; display: inline-block;
        background: #1da1f2;
        border-radius: 50%;
        position: relative;
        flex-shrink: 0;
    }
    .badge-verified .v-icon::after {
        content: '';
        position: absolute;
        left: 3px; top: 2px;
        width: 5px; height: 8px;
        border: solid #fff;
        border-width: 0 2px 2px 0;
        transform: rotate(45deg);
    }
    .badge-admin { background: rgba(255,107,0,.15); color: var(--primary); }
    .badge-banned { background: rgba(255,71,87,.15); color: var(--danger); }
    .badge-muted { background: rgba(255,193,7,.15); color: var(--warning); }
    .badge-ok { background: rgba(0,210,106,.15); color: var(--success); }
    .actions { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
    .actions form { display: inline-flex; gap: 4px; align-items: center; margin: 0; }
    .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
    .muted { color: var(--text-muted); font-size: 12px; }
    .login-box { max-width: 360px; margin: 90px auto; text-align: center; }
    .login-box input { width: 100%; margin: 10px 0; }
    .login-box button { width: 100%; padding: 11px; }
    .error { color: var(--danger); font-size: 13px; margin-top: 6px; }
    .search-form { display: flex; gap: 8px; margin-bottom: 16px; }
    .amount-input { width: 70px; }
    @media (max-width: 768px) {
        .wrap { padding: 16px 12px; }
        .top-bar { flex-direction: column; align-items: flex-start; gap: 8px; }
        table { font-size: 12px; display: block; overflow-x: auto; }
        th, td { padding: 8px 6px; }
        .actions { flex-direction: column; align-items: stretch; }
        .actions form { flex-wrap: wrap; }
        .search-form { flex-direction: column; }
        .search-form input[type=text] { width: 100%; }
    }
</style>
"""

LOGIN_PAGE = BASE_STYLE + """
<div class="wrap">
  <div class="login-box card">
    <h1 style="justify-content:center;"><span class="logo">Strovo</span> Admin</h1>
    <p class="muted" style="margin:0 0 12px;">Модель сервера: <code>{{ server_model }}</code></p>
    <form method="POST">
        <input type="password" name="password" placeholder="Пароль админки" autofocus required>
        <button class="btn-primary" type="submit">Войти</button>
    </form>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    {% if ok %}<div class="error" style="background:rgba(0,210,106,.12);color:#00d26a;border-color:rgba(0,210,106,.35);">{{ ok }}</div>{% endif %}
  </div>
</div>
"""

SETUP_PAGE = BASE_STYLE + """
<div class="wrap">
  <div class="login-box card" style="max-width:400px;">
    <h1 style="justify-content:center;"><span class="logo">Strovo</span> Регистрация</h1>
    <p class="muted" style="margin:0 0 8px;">Первый запуск админки — создай пароль.</p>
    <p class="muted" style="margin:0 0 14px;">Модель сервера: <code>{{ server_model }}</code></p>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="POST">
        <input type="password" name="new1" placeholder="Новый пароль (мин. 6)" required minlength="6" autofocus style="margin-bottom:10px;">
        <input type="password" name="new2" placeholder="Повтори пароль" required minlength="6" style="margin-bottom:12px;">
        <button class="btn-primary" type="submit">Зарегистрировать</button>
    </form>
  </div>
</div>
"""

DASHBOARD_PAGE = BASE_STYLE + """
<div class="wrap">
  <div class="top-bar">
    <h1><span class="logo">Strovo</span> Admin Panel</h1>
    <div>
        <span class="muted">Модель: <code>{{ server_model }}</code> · Пользователей: {{ total_users }}</span>
        &nbsp;·&nbsp; <a href="{{ url_for('admin_password') }}">Пароль</a>
        &nbsp;·&nbsp; <a href="{{ url_for('admin_files') }}">Файлы</a>
        &nbsp;·&nbsp; <a href="{{ url_for('admin_logs') }}">Логи</a>
        &nbsp;·&nbsp; <a href="{{ url_for('admin_logout') }}">Выйти</a>
    </div>
  </div>

  <div class="card">
    <form class="search-form" method="GET">
        <input type="text" name="q" value="{{ q }}" placeholder="Поиск по имени пользователя...">
        <button type="submit">Найти</button>
        {% if q %}<a class="btn" href="{{ url_for('admin_dashboard') }}">Сбросить</a>{% endif %}
    </form>

    <table>
        <thead>
        <tr>
            <th>Пользователь</th><th>Коины</th><th>Статусы</th><th>Действия</th>
        </tr>
        </thead>
        <tbody>
        {% for u in users %}
        <tr>
            <td>
                <strong>{{ u.username }}</strong>
                {% if u.is_banned %}<div class="muted">Причина бана: {{ u.ban_reason or '—' }}</div>{% endif %}
                {% if u.is_muted %}<div class="muted">Мут чата: {{ u.mute_reason or '—' }}</div>{% endif %}
            </td>
            <td>{{ u.coins }} 🪙</td>
            <td>
                {% if u.is_verified %}<span class="badge badge-verified"><span class="v-icon"></span> Верифицирован</span>{% endif %}
                {% if u.is_admin %}<span class="badge badge-admin">🛡️ Админ</span>{% endif %}
                {% if u.is_banned %}<span class="badge badge-banned">🚫 Бан</span>{% elif u.is_muted %}<span class="badge badge-muted">🔇 Мут</span>{% else %}<span class="badge badge-ok">Активен</span>{% endif %}
            </td>
            <td>
                <div class="actions">
                    <form method="POST" action="{{ url_for('admin_user_action') }}">
                        <input type="hidden" name="username" value="{{ u.username }}">
                        <input type="hidden" name="q" value="{{ q }}">
                        <input type="hidden" name="action" value="toggle_verified">
                        <button title="Выдать/снять галочку верификации">{{ 'Снять галочку' if u.is_verified else 'Выдать галочку' }}</button>
                    </form>

                    <form method="POST" action="{{ url_for('admin_user_action') }}">
                        <input type="hidden" name="username" value="{{ u.username }}">
                        <input type="hidden" name="q" value="{{ q }}">
                        <input type="hidden" name="action" value="toggle_admin">
                        <button title="Выдать/снять права администратора">{{ '🛡️ Снять админку' if u.is_admin else '🛡️ Выдать админку' }}</button>
                    </form>

                    <form method="POST" action="{{ url_for('admin_user_action') }}">
                        <input type="hidden" name="username" value="{{ u.username }}">
                        <input type="hidden" name="q" value="{{ q }}">
                        <input type="hidden" name="action" value="add_coins">
                        <input class="amount-input" type="number" name="amount" placeholder="±100" required>
                        <button title="Выдать (или списать, если минус) коины">🪙 Выдать</button>
                    </form>

                    <form method="POST" action="{{ url_for('admin_user_action') }}">
                        <input type="hidden" name="username" value="{{ u.username }}">
                        <input type="hidden" name="q" value="{{ q }}">
                        <input type="hidden" name="action" value="toggle_mute">
                        {% if not u.is_muted %}
                            <input type="text" name="reason" placeholder="причина мута">
                        {% endif %}
                        <button class="{{ 'btn-success' if u.is_muted else '' }}" title="Мут в чате (нельзя писать)">
                            {{ '🔊 Снять мут' if u.is_muted else '🔇 Мут чата' }}
                        </button>
                    </form>

                    <form method="POST" action="{{ url_for('admin_user_action') }}">
                        <input type="hidden" name="username" value="{{ u.username }}">
                        <input type="hidden" name="q" value="{{ q }}">
                        <input type="hidden" name="action" value="toggle_ban">
                        {% if not u.is_banned %}
                            <input type="text" name="reason" placeholder="причина бана">
                        {% endif %}
                        <button class="{{ 'btn-success' if u.is_banned else 'btn-danger' }}">
                            {{ 'Разбанить' if u.is_banned else 'Забанить' }}
                        </button>
                    </form>

                    <form method="POST" action="{{ url_for('admin_user_action') }}" onsubmit="return confirm('УДАЛИТЬ аккаунт {{ u.username }} НАВСЕГДА с сервера? Все его игры, сообщения и данные будут стёрты.');">
                        <input type="hidden" name="username" value="{{ u.username }}">
                        <input type="hidden" name="q" value="{{ q }}">
                        <input type="hidden" name="action" value="delete_account">
                        <button class="btn-danger" title="Полностью удалить аккаунт с сервера">🗑️ Удалить аккаунт</button>
                    </form>
                </div>
            </td>
        </tr>
        {% else %}
        <tr><td colspan="4" class="muted">Никого не найдено.</td></tr>
        {% endfor %}
        </tbody>
    </table>
  </div>

  <div class="card">
    <h1 style="font-size:16px;">💬 Все сообщения чата</h1>
    <p class="muted" style="margin-bottom:12px;">Показаны последние сообщения из всех игровых комнат. Всего комнат: {{ chat_rooms_count }}, сообщений: {{ chat_total }}</p>
    <div style="max-height:420px; overflow-y:auto; border:1px solid var(--border); border-radius:var(--radius-sm);">
      <table>
        <thead>
          <tr>
            <th>Время</th>
            <th>Игра / комната</th>
            <th>Пользователь</th>
            <th>Сообщение</th>
          </tr>
        </thead>
        <tbody>
        {% for m in chat_messages %}
        <tr>
          <td class="muted" style="white-space:nowrap;">{{ m.ts_short }}</td>
          <td><code style="font-size:11px;">{{ m.game_id_short }}</code></td>
          <td>
            <strong>{{ m.username }}</strong>
            {% if m.verified %}<span class="badge badge-verified" style="margin-left:4px;"><span class="v-icon"></span></span>{% endif %}
            {% if m.is_admin %}<span class="badge badge-admin" style="margin-left:2px;">🛡️</span>{% endif %}
          </td>
          <td style="word-break:break-word; max-width:360px;">{{ m.text }}</td>
        </tr>
        {% else %}
        <tr><td colspan="4" class="muted">Сообщений в чате пока нет.</td></tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <h1 style="font-size:16px;">🎮 Опубликованные игры</h1>
    <table>
        <thead><tr><th>Название</th><th>Автор</th><th>Игр</th><th>Лайков</th><th>Действия</th></tr></thead>
        <tbody>
        {% for g in games %}
        <tr>
            <td>{{ g.name }}</td>
            <td>{{ g.owner }}</td>
            <td>{{ g.plays }}</td>
            <td>{{ g.likes }}</td>
            <td class="actions">
                <form method="POST" action="{{ url_for('admin_game_action') }}">
                    <input type="hidden" name="game_id" value="{{ g.id }}">
                    <input type="hidden" name="action" value="unpublish">
                    <button>Снять с публикации</button>
                </form>
                <form method="POST" action="{{ url_for('admin_game_action') }}" onsubmit="return confirm('Удалить игру навсегда?');">
                    <input type="hidden" name="game_id" value="{{ g.id }}">
                    <input type="hidden" name="action" value="delete">
                    <button class="btn-danger">Удалить</button>
                </form>
            </td>
        </tr>
        {% else %}
        <tr><td colspan="5" class="muted">Опубликованных игр пока нет.</td></tr>
        {% endfor %}
        </tbody>
    </table>
  </div>
</div>
"""


# ==================== РОУТЫ ====================

@app.route('/')
@app.route('/admin')
def admin_root():
    if not is_admin_setup_done():
        return redirect(url_for('admin_setup'))
    if not is_logged_in():
        return redirect(url_for('admin_login'))
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/setup', methods=['GET', 'POST'])
def admin_setup():
    """Первый запуск — регистрация пароля админки."""
    if is_admin_setup_done():
        return redirect(url_for('admin_login'))
    error = None
    if request.method == 'POST':
        new1 = request.form.get('new1', '')
        new2 = request.form.get('new2', '')
        if len(new1) < 6:
            error = 'Пароль минимум 6 символов'
        elif new1 != new2:
            error = 'Пароли не совпадают'
        else:
            complete_admin_setup(new1, SERVER_MODEL)
            append_admin_log('setup', f'Регистрация админки, модель {SERVER_MODEL}')
            return redirect(url_for('admin_login') + '?setup=1')
    return render_template_string(SETUP_PAGE, error=error, server_model=SERVER_MODEL)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    # Пока нет регистрации — только setup
    if not is_admin_setup_done():
        return redirect(url_for('admin_setup'))

    error = None
    ok = None
    if request.args.get('changed') == '1':
        ok = 'Пароль изменён. Войди с новым паролем.'
    elif request.args.get('setup') == '1':
        ok = 'Регистрация готова. Войди со своим паролем.'

    if request.method == 'POST':
        password = request.form.get('password', '')
        if check_admin_password(password):
            session['admin_ok'] = True
            append_admin_log('login', 'Успешный вход в админку')
            return redirect(url_for('admin_dashboard'))
        error = 'Неверный пароль'
        ok = None
        append_admin_log('login_fail', 'Неверный пароль')
    return render_template_string(
        LOGIN_PAGE,
        error=error,
        ok=ok,
        server_model=get_server_model(),
    )


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_ok', None)
    return redirect(url_for('admin_login'))


@app.route('/admin/dashboard')
def admin_dashboard():
    if not is_logged_in():
        return redirect(url_for('admin_login'))

    q = request.args.get('q', '').strip().lower()
    users_data = load_json(USERS_FILE, {})
    verified = load_json(VERIFIED_FILE, {})
    projects = load_json(PROJECTS_FILE, {})

    rows = []
    for username, u in users_data.items():
        if q and q not in username.lower():
            continue
        rows.append({
            'username': username,
            'coins': u.get('coins', 0),
            'is_verified': verified.get(username, False),
            'is_admin': u.get('is_admin', False),
            'is_banned': u.get('is_banned', False),
            'ban_reason': u.get('ban_reason', ''),
            'is_muted': u.get('is_muted', False),
            'mute_reason': u.get('mute_reason', ''),
        })
    rows.sort(key=lambda r: r['username'].lower())

    games = []
    for pid, p in projects.items():
        if p.get('published'):
            games.append({
                'id': pid, 'name': p.get('name', '—'), 'owner': p.get('owner', '—'),
                'plays': p.get('plays', 0), 'likes': p.get('likes', 0)
            })
    games.sort(key=lambda g: -g['plays'])

    # Все сообщения чата (последние 200, свежие сверху)
    chats = load_json(CHATS_FILE, {})
    chat_messages = []
    for gid, messages in chats.items():
        for m in messages:
            ts = m.get('ts', '')
            ts_short = ts[11:19] if len(ts) >= 19 else ts  # HH:MM:SS
            chat_messages.append({
                'ts': ts,
                'ts_short': ts_short,
                'game_id': gid,
                'game_id_short': (gid[:8] + '…') if len(gid) > 10 else gid,
                'username': m.get('username', '?'),
                'text': m.get('text', ''),
                'verified': m.get('verified', False),
                'is_admin': m.get('is_admin', False),
            })
    chat_messages.sort(key=lambda x: x['ts'], reverse=True)
    chat_messages = chat_messages[:200]
    chat_total = sum(len(msgs) for msgs in chats.values())

    return render_template_string(
        DASHBOARD_PAGE,
        users=rows,
        games=games,
        q=q,
        total_users=len(users_data),
        chat_messages=chat_messages,
        chat_rooms_count=len(chats),
        chat_total=chat_total,
        server_model=get_server_model(),
    )


@app.route('/admin/action/user', methods=['POST'])
def admin_user_action():
    if not is_logged_in():
        return redirect(url_for('admin_login'))

    username = request.form.get('username', '')
    action = request.form.get('action', '')
    q = request.form.get('q', '')

    users_data = load_json(USERS_FILE, {})
    user = users_data.get(username)
    if not user:
        return redirect(url_for('admin_dashboard', q=q))

    if action == 'toggle_verified':
        verified = load_json(VERIFIED_FILE, {})
        verified[username] = not verified.get(username, False)
        save_json(VERIFIED_FILE, verified)
        append_admin_log('toggle_verified', f'{username} → {verified.get(username)}')

    elif action == 'toggle_admin':
        user['is_admin'] = not user.get('is_admin', False)
        save_json(USERS_FILE, users_data)
        append_admin_log('toggle_admin', f'{username} → {user.get("is_admin")}')

    elif action == 'add_coins':
        try:
            amount = int(request.form.get('amount', '0'))
        except ValueError:
            amount = 0
        user['coins'] = max(0, user.get('coins', 0) + amount)
        save_json(USERS_FILE, users_data)
        append_admin_log('add_coins', f'{username} +{amount} → {user.get("coins")}')

    elif action == 'toggle_ban':
        user['is_banned'] = not user.get('is_banned', False)
        user['ban_reason'] = request.form.get('reason', '').strip() if user['is_banned'] else ''
        save_json(USERS_FILE, users_data)
        if user['is_banned']:
            kick_user_sessions(username)
        append_admin_log('toggle_ban', f'{username} banned={user.get("is_banned")} reason={user.get("ban_reason","")}')

    elif action == 'toggle_mute':
        user['is_muted'] = not user.get('is_muted', False)
        user['mute_reason'] = request.form.get('reason', '').strip() if user['is_muted'] else ''
        save_json(USERS_FILE, users_data)
        append_admin_log('toggle_mute', f'{username} muted={user.get("is_muted")}')

    elif action == 'delete_account':
        delete_user_account(username)
        append_admin_log('delete_account', f'Удалён аккаунт {username}')
        return redirect(url_for('admin_dashboard', q=q))

    return redirect(url_for('admin_dashboard', q=q))


@app.route('/admin/action/game', methods=['POST'])
def admin_game_action():
    if not is_logged_in():
        return redirect(url_for('admin_login'))

    game_id = request.form.get('game_id', '')
    action = request.form.get('action', '')

    projects = load_json(PROJECTS_FILE, {})
    project = projects.get(game_id)
    if project:
        if action == 'unpublish':
            project['published'] = False
            project['updated_at'] = datetime.now().isoformat()
            save_json(PROJECTS_FILE, projects)
            append_admin_log('unpublish_game', f'{game_id} ({project.get("name","")})')
        elif action == 'delete':
            name = project.get('name', '')
            delete_game_images(project)
            del projects[game_id]
            save_json(PROJECTS_FILE, projects)
            append_admin_log('delete_game', f'{game_id} ({name})')

    return redirect(url_for('admin_dashboard'))


LOGS_PAGE = BASE_STYLE + """
<div class="wrap">
  <div class="top-bar">
    <h1><span class="logo">Strovo</span> Логи админки</h1>
    <div>
        <a href="{{ url_for('admin_dashboard') }}">← Назад</a>
        &nbsp;·&nbsp;
        <a href="{{ url_for('admin_logout') }}">Выйти</a>
    </div>
  </div>

  <div class="card">
    <p class="muted" style="margin:0 0 12px;">Файл: datag/admin_log.json · последние {{ logs|length }} записей</p>
    {% if not logs %}
      <p class="muted">Пока пусто. Действия в админке (бан, удаление, выдача коинов) появятся здесь.</p>
    {% else %}
    <table>
      <thead>
        <tr><th style="width:180px;">Время</th><th>Действие</th><th>Детали</th></tr>
      </thead>
      <tbody>
      {% for row in logs|reverse %}
        <tr>
          <td class="muted">{{ row.ts }}</td>
          <td><strong>{{ row.action }}</strong></td>
          <td>{{ row.detail }}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
    {% endif %}
  </div>
</div>
"""


@app.route('/admin/logs')
def admin_logs():
    if not is_logged_in():
        return redirect(url_for('admin_login'))
    logs = load_json(ADMIN_LOG_FILE, [])
    if not isinstance(logs, list):
        logs = []
    return render_template_string(LOGS_PAGE, logs=logs)


PASSWORD_PAGE = BASE_STYLE + """
<div class="wrap">
  <div class="top-bar">
    <h1><span class="logo">Strovo</span> Пароль админки</h1>
    <div>
        <a href="{{ url_for('admin_dashboard') }}">← Назад</a>
        &nbsp;·&nbsp;
        <a href="{{ url_for('admin_logout') }}">Выйти</a>
    </div>
  </div>

  <div class="card" style="max-width:440px;">
    <p class="muted" style="margin:0 0 14px;">
      Пароль хранится в <code>datag/admin_auth.json</code> (хэш SHA-256).
      После смены войди заново.
    </p>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    {% if ok %}<div class="error" style="background:rgba(0,210,106,.12);color:#00d26a;border-color:rgba(0,210,106,.35);">{{ ok }}</div>{% endif %}
    <form method="POST">
      <label class="muted" style="display:block;margin-bottom:4px;">Текущий пароль</label>
      <input type="password" name="current" required autocomplete="current-password" style="width:100%;margin-bottom:12px;">
      <label class="muted" style="display:block;margin-bottom:4px;">Новый пароль (мин. 6 символов)</label>
      <input type="password" name="new1" required minlength="6" autocomplete="new-password" style="width:100%;margin-bottom:12px;">
      <label class="muted" style="display:block;margin-bottom:4px;">Повтори новый пароль</label>
      <input type="password" name="new2" required minlength="6" autocomplete="new-password" style="width:100%;margin-bottom:16px;">
      <button class="btn-primary" type="submit" style="width:100%;">Сменить пароль</button>
    </form>
  </div>
</div>
"""


@app.route('/admin/password', methods=['GET', 'POST'])
def admin_password():
    if not is_logged_in():
        return redirect(url_for('admin_login'))

    error = None
    ok = None
    if request.method == 'POST':
        current = request.form.get('current', '')
        new1 = request.form.get('new1', '')
        new2 = request.form.get('new2', '')
        if not check_admin_password(current):
            error = 'Текущий пароль неверный'
            append_admin_log('password_change_fail', 'Неверный текущий пароль')
        elif len(new1) < 6:
            error = 'Новый пароль минимум 6 символов'
        elif new1 != new2:
            error = 'Новые пароли не совпадают'
        elif new1 == current:
            error = 'Новый пароль совпадает со старым'
        else:
            set_admin_password(new1)
            append_admin_log('password_change', 'Пароль админки изменён')
            session.pop('admin_ok', None)
            return redirect(url_for('admin_login') + '?changed=1')

    return render_template_string(PASSWORD_PAGE, error=error, ok=ok)


# ---------- Просмотр файлов проекта ----------
TEXT_PREVIEW_EXTS = {
    '.txt', '.json', '.py', '.html', '.htm', '.css', '.js', '.md', '.bat',
    '.cfg', '.ini', '.log', '.csv', '.xml', '.yml', '.yaml', '.svg',
}
SKIP_DIR_NAMES = {'__pycache__', '.git', 'node_modules'}
MAX_PREVIEW_BYTES = 200_000


def _safe_rel_path(rel):
    """Только пути внутри BASE_DIR, без .."""
    rel = (rel or '').replace('\\', '/').lstrip('/')
    parts = [p for p in rel.split('/') if p and p != '.']
    if any(p == '..' for p in parts):
        return None
    full = os.path.normpath(os.path.join(BASE_DIR, *parts))
    base = os.path.normpath(BASE_DIR)
    if full != base and not full.startswith(base + os.sep):
        return None
    return full, '/'.join(parts)


def _fmt_size(n):
    try:
        n = int(n)
    except Exception:
        return '—'
    if n < 1024:
        return f'{n} B'
    if n < 1024 * 1024:
        return f'{n / 1024:.1f} KB'
    return f'{n / (1024 * 1024):.1f} MB'


FILES_PAGE = BASE_STYLE + """
<div class="wrap">
  <div class="top-bar">
    <h1><span class="logo">Strovo</span> Файлы</h1>
    <div>
        <a href="{{ url_for('admin_dashboard') }}">← Назад</a>
        &nbsp;·&nbsp;
        <a href="{{ url_for('admin_logs') }}">Логи</a>
        &nbsp;·&nbsp;
        <a href="{{ url_for('admin_logout') }}">Выйти</a>
    </div>
  </div>

  <div class="card">
    <p class="muted" style="margin:0 0 10px;">
      Корень: <code>{{ base_dir }}</code><br>
      Путь:
      <a href="{{ url_for('admin_files') }}">/</a>
      {% for crumb in crumbs %}
        / <a href="{{ url_for('admin_files', path=crumb.path) }}">{{ crumb.name }}</a>
      {% endfor %}
    </p>

    <table>
      <thead>
        <tr>
          <th>Имя</th>
          <th style="width:100px;">Тип</th>
          <th style="width:100px;">Размер</th>
        </tr>
      </thead>
      <tbody>
      {% if parent_path is not none %}
        <tr>
          <td colspan="3"><a href="{{ url_for('admin_files', path=parent_path) }}">.. (наверх)</a></td>
        </tr>
      {% endif %}
      {% for d in dirs %}
        <tr>
          <td>📁 <a href="{{ url_for('admin_files', path=d.rel) }}"><strong>{{ d.name }}</strong></a></td>
          <td class="muted">папка</td>
          <td class="muted">—</td>
        </tr>
      {% endfor %}
      {% for f in files %}
        <tr>
          <td>📄 <a href="{{ url_for('admin_files', path=f.rel) }}">{{ f.name }}</a></td>
          <td class="muted">{{ f.ext or 'файл' }}</td>
          <td class="muted">{{ f.size }}</td>
        </tr>
      {% endfor %}
      {% if not dirs and not files %}
        <tr><td colspan="3" class="muted">Пусто</td></tr>
      {% endif %}
      </tbody>
    </table>
  </div>

  {% if preview is not none %}
  <div class="card" style="margin-top:16px;">
    <h2 style="margin:0 0 10px;font-size:16px;">Просмотр: {{ preview_name }}</h2>
    {% if preview_error %}
      <p class="muted">{{ preview_error }}</p>
    {% else %}
      <pre style="margin:0;max-height:60vh;overflow:auto;background:#0a0a0f;padding:12px;border-radius:8px;font-size:12px;white-space:pre-wrap;word-break:break-word;">{{ preview }}</pre>
    {% endif %}
  </div>
  {% endif %}
</div>
"""


@app.route('/admin/files')
def admin_files():
    if not is_logged_in():
        return redirect(url_for('admin_login'))

    req_path = request.args.get('path', '') or ''
    resolved = _safe_rel_path(req_path)
    if not resolved:
        return redirect(url_for('admin_files'))
    full, rel = resolved

    # Хлебные крошки
    crumbs = []
    if rel:
        acc = []
        for part in rel.split('/'):
            acc.append(part)
            crumbs.append({'name': part, 'path': '/'.join(acc)})

    parent_path = None
    if rel:
        parent_path = '/'.join(rel.split('/')[:-1])

    preview = None
    preview_name = ''
    preview_error = None

    if os.path.isfile(full):
        preview_name = os.path.basename(full)
        ext = os.path.splitext(full)[1].lower()
        size = os.path.getsize(full)
        if ext not in TEXT_PREVIEW_EXTS:
            preview_error = f'Бинарный файл ({ext or "без расширения"}), просмотр текста недоступен. Размер: {_fmt_size(size)}'
            preview = ''
        elif size > MAX_PREVIEW_BYTES:
            preview_error = f'Файл слишком большой для превью ({_fmt_size(size)}). Макс. {_fmt_size(MAX_PREVIEW_BYTES)}'
            preview = ''
        else:
            try:
                with open(full, 'r', encoding='utf-8', errors='replace') as f:
                    preview = f.read()
            except Exception as e:
                preview_error = f'Не удалось прочитать: {e}'
                preview = ''
        # список = родительская папка
        list_dir = os.path.dirname(full)
        list_rel = '/'.join(rel.split('/')[:-1])
    elif os.path.isdir(full):
        list_dir = full
        list_rel = rel
    else:
        return redirect(url_for('admin_files'))

    dirs = []
    files = []
    try:
        names = sorted(os.listdir(list_dir), key=lambda n: (not os.path.isdir(os.path.join(list_dir, n)), n.lower()))
    except OSError:
        names = []
    for name in names:
        if name in SKIP_DIR_NAMES:
            continue
        fp = os.path.join(list_dir, name)
        item_rel = f'{list_rel}/{name}'.lstrip('/') if list_rel else name
        if os.path.isdir(fp):
            dirs.append({'name': name, 'rel': item_rel})
        else:
            try:
                sz = os.path.getsize(fp)
            except OSError:
                sz = 0
            files.append({
                'name': name,
                'rel': item_rel,
                'size': _fmt_size(sz),
                'ext': os.path.splitext(name)[1].lower() or '',
            })

    return render_template_string(
        FILES_PAGE,
        base_dir=BASE_DIR,
        crumbs=crumbs,
        parent_path=parent_path if rel else None,
        dirs=dirs,
        files=files,
        preview=preview,
        preview_name=preview_name,
        preview_error=preview_error,
    )


if __name__ == '__main__':
    print("=" * 55)
    print("  STROVO ADMIN PANEL")
    print(f"  Модель сервера: {SERVER_MODEL}")
    if is_admin_setup_done():
        print("  Статус: пароль уже задан (datag/admin_auth.json)")
        print("  Вход:   http://localhost:5050/admin/login")
    else:
        print("  Статус: ПЕРВЫЙ ЗАПУСК — нужна регистрация")
        print("  Открой: http://localhost:5050/admin/setup")
    print("  Пароль:  http://localhost:5050/admin/password")
    print("  Файлы:   http://localhost:5050/admin/files")
    print("  Логи:    http://localhost:5050/admin/logs")
    print("  Запускать ОТДЕЛЬНО и ОДНОВРЕМЕННО с server.py")
    print("=" * 55)
    app.run(host='0.0.0.0', port=5050, debug=True)