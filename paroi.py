#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paroi.py — смена пароля пользователя Strovo из консоли (без сайта).

Запуск из папки со server.py:

    python paroi.py
    python paroi.py list
    python paroi.py set <username> <new_password>
    python paroi.py set <username>          # спросит пароль скрыто

Пароли хранятся как SHA-256 в datag/users.json (как у server.py).
"""

import os
import sys
import json
import hashlib
import getpass
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, 'datag', 'users.json')


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def load_users():
    if not os.path.isfile(USERS_FILE):
        print(f'[!] Файл не найден: {USERS_FILE}')
        print('    Запусти из папки C:\\strovo (где лежит server.py).')
        sys.exit(1)
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f'[!] Не удалось прочитать users.json: {e}')
        sys.exit(1)
    if not isinstance(data, dict):
        print('[!] users.json имеет неверный формат.')
        sys.exit(1)
    return data


def save_users(users: dict):
    tmp = USERS_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    os.replace(tmp, USERS_FILE)


def find_username(users: dict, name: str):
    """Точное имя или без учёта регистра."""
    if name in users:
        return name
    lower = name.lower()
    for u in users:
        if u.lower() == lower:
            return u
    return None


def cmd_list(users: dict):
    print(f'Пользователи ({len(users)}) — {USERS_FILE}')
    print('-' * 40)
    if not users:
        print('(пусто)')
        return
    for name, u in sorted(users.items(), key=lambda x: x[0].lower()):
        banned = ' [BAN]' if u.get('is_banned') else ''
        admin = ' [ADMIN]' if u.get('is_admin') else ''
        coins = u.get('coins', 0)
        print(f'  {name}{admin}{banned}  coins={coins}')


def cmd_set(users, username, password=None):
    real = find_username(users, username)
    if not real:
        print(f'[!] Пользователь «{username}» не найден.')
        print('    Список: python paroi.py list')
        sys.exit(1)

    if not password:
        p1 = getpass.getpass(f'Новый пароль для {real}: ')
        p2 = getpass.getpass('Ещё раз: ')
        if p1 != p2:
            print('[!] Пароли не совпадают.')
            sys.exit(1)
        password = p1

    if len(password) < 6:
        print('[!] Пароль минимум 6 символов.')
        sys.exit(1)

    users[real]['password_hash'] = hash_password(password)
    users[real]['updated_at'] = datetime.now().isoformat()
    save_users(users)
    print(f'[OK] Пароль для «{real}» изменён.')
    print('     Можно сразу входить на сайте с новым паролем.')


def interactive(users: dict):
    print('=' * 45)
    print('  Strovo — смена пароля (paroi.py)')
    print(f'  Файл: {USERS_FILE}')
    print('=' * 45)
    cmd_list(users)
    print()
    name = input('Имя пользователя: ').strip()
    if not name:
        print('Отмена.')
        return
    cmd_set(users, name, None)


def main():
    args = sys.argv[1:]
    users = load_users()

    if not args:
        interactive(users)
        return

    cmd = args[0].lower()
    if cmd in ('list', 'ls', 'l'):
        cmd_list(users)
    elif cmd in ('set', 's', 'password', 'pass'):
        if len(args) < 2:
            print('Использование: python paroi.py set <username> [password]')
            sys.exit(1)
        username = args[1]
        password = args[2] if len(args) >= 3 else None
        cmd_set(users, username, password)
    elif cmd in ('help', '-h', '--help'):
        print(__doc__)
    else:
        # короткая форма: python paroi.py username [password]
        username = args[0]
        password = args[1] if len(args) >= 2 else None
        cmd_set(users, username, password)


if __name__ == '__main__':
    main()
