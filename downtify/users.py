"""User accounts: who signs in to Downtify, and what they may do.

Every web page and API call is made by a user, signed in with a username
and password (or through a phone paired to their account - see
:mod:`downtify.auth`). There are two roles:

* **admin** - everything: every setting, every user, the activity log.
* **user** - listen, search, download, like; in Settings only General,
  Apps and About, and only their own account, preferences and devices.

A new install starts with one admin, ``admin`` / ``downtify``
(:data:`DEFAULT_USERNAME`, :data:`DEFAULT_PASSWORD`), flagged as still
using the default password so the web app keeps suggesting a change. An
install upgraded from a version without accounts gets the same account -
or, when it had set the single sign-in password of the version before,
that password (so it keeps working) - and a one-time notice on the
sign-in page saying accounts exist now (:meth:`UserStore.notice`).

The last admin can't be deleted or made a normal user: somebody has to
be able to manage the server. ``python main.py auth-reset`` puts
``admin`` / ``downtify`` back (as an admin) for a forgotten password.

Stored in ``downtify_auth.db`` next to devices and sessions. Passwords
are scrypt hashes (:func:`hash_password`).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .sqlite_utils import connect_sqlite

#: Shortest password accepted.
MIN_PASSWORD_LENGTH = 8

# scrypt: N=2**15, r=8, p=1 (~32 MiB, ~50-100 ms) - the OWASP minimum.
_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_MAXMEM = 64 * 1024 * 1024

ROLE_ADMIN = 'admin'
ROLE_USER = 'user'
ROLES = (ROLE_ADMIN, ROLE_USER)

DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'downtify'

#: Usernames: 3-32 letters, digits, dots, dashes or underscores.
_USERNAME_RE = re.compile(r'^[A-Za-z0-9._-]{3,32}$')
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

#: Words used to randomly generate usernames on Google OAuth sign-in.
_RANDOM_WORDS: tuple[str, ...] = (
    'acoustic',
    'ambient',
    'audio',
    'bass',
    'beat',
    'chord',
    'classic',
    'cosmic',
    'disco',
    'drum',
    'echo',
    'fader',
    'funk',
    'groove',
    'harmony',
    'indie',
    'jazz',
    'listener',
    'lofi',
    'melody',
    'music',
    'note',
    'player',
    'pulse',
    'radio',
    'record',
    'retro',
    'rhythm',
    'riff',
    'rocker',
    'sonic',
    'sound',
    'stereo',
    'synth',
    'tempo',
    'track',
    'tune',
    'tuner',
    'vibes',
    'vinyl',
    'vocal',
    'wave',
)

#: The preferences a user keeps for themselves (Settings > General), with
#: their type. Anything else sent is ignored.
PREFERENCES: dict[str, type] = {
    'theme': str,
    'locale': str,
    'show_lyrics': bool,
    'translate_lyrics': bool,
    'search_albums': bool,
    'hide_public_playlists_by_default': bool,
    'sidebar_discovery': bool,
    'sidebar_monitor': bool,
    'sidebar_podcasts': bool,
    'sidebar_charts': bool,
    'sidebar_similar': bool,
}


def clean_email(value: Any) -> Optional[str]:
    text = str(value or '').strip()
    if not text:
        return None
    if not _EMAIL_RE.fullmatch(text):
        raise UserError('Please enter a valid email address')
    return text.lower()


def clean_display_name(value: Any) -> str:
    text = str(value or '').strip()
    return text[:100]


class UserError(ValueError):
    """A request about users that can't be done; the message says why."""


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def hash_password(password: str) -> str:
    """``scrypt$N$r$p$<salt>$<hash>`` for *password*."""

    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        maxmem=_SCRYPT_MAXMEM,
    )
    return (
        f'scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}$'
        f'{_b64(salt)}${_b64(digest)}'
    )


def verify_password(password: str, stored: str) -> bool:
    """Whether *password* matches a :func:`hash_password` value."""

    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split('$')
        if scheme != 'scrypt':
            return False
        salt = base64.urlsafe_b64decode(salt_b64 + '=' * (-len(salt_b64) % 4))
        expected = base64.urlsafe_b64decode(
            hash_b64 + '=' * (-len(hash_b64) % 4)
        )
        digest = hashlib.scrypt(
            password.encode(),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            maxmem=_SCRYPT_MAXMEM,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_username(value: Any) -> str:
    """*value* as a username, or :class:`UserError`."""

    name = str(value or '').strip()
    if not _USERNAME_RE.fullmatch(name):
        raise UserError(
            'Usernames are 3 to 32 letters, digits, dots, dashes or '
            'underscores'
        )
    return name


def check_password_rules(password: Any) -> str:
    text = str(password or '')
    if len(text) < MIN_PASSWORD_LENGTH:
        raise UserError(f'Use at least {MIN_PASSWORD_LENGTH} characters')
    if len(text) > 256:
        raise UserError('That password is too long')
    return text


def clean_preferences(values: Any) -> dict[str, Any]:
    """The known preferences in *values*, each of its type."""

    if not isinstance(values, dict):
        return {}
    clean: dict[str, Any] = {}
    for key, kind in PREFERENCES.items():
        if key not in values:
            continue
        value = values[key]
        if kind is bool:
            clean[key] = bool(value)
        elif value is None:
            clean[key] = ''
        else:
            clean[key] = str(value)[:32]
    return clean


def public_user(row: Any) -> dict[str, Any]:
    """A user as the API shows it - never the password hash."""

    cols = row.keys() if hasattr(row, 'keys') else []
    return {
        'id': int(row['id']),
        'username': row['username'],
        'role': row['role'],
        'default_password': bool(row['default_password']),
        'created_at': row['created_at'],
        'last_login_at': row['last_login_at'],
        'last_login_ip': row['last_login_ip'] or '',
        'email': (row['email'] or '') if 'email' in cols else '',
        'display_name': (row['display_name'] or '')
        if 'display_name' in cols
        else '',
        'google_id': (row['google_id'] or '') if 'google_id' in cols else '',
    }


class UserStore:  # noqa: PLR0904
    """The users table (and the one-time accounts notice)."""

    def __init__(self, db_path: Path) -> None:
        self._path = str(db_path)
        self._lock = threading.RLock()
        self._init_db()
        self._dummy: Optional[str] = None

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self._path, row_factory=True)

    @property
    def _dummy_hash(self) -> str:
        """A hash to check against when there's no user, so an unknown
        username takes as long as a wrong password."""

        if self._dummy is None:
            self._dummy = hash_password('not a real password')
        return self._dummy

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    default_password INTEGER NOT NULL DEFAULT 0,
                    prefs_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    last_login_at TEXT,
                    last_login_ip TEXT NOT NULL DEFAULT '',
                    email TEXT COLLATE NOCASE,
                    display_name TEXT NOT NULL DEFAULT '',
                    google_id TEXT
                )
            """)
            cols = {
                r['name']
                for r in conn.execute('PRAGMA table_info(users)').fetchall()
            }
            if 'email' not in cols:
                conn.execute(
                    'ALTER TABLE users ADD COLUMN email TEXT COLLATE NOCASE'
                )
            if 'display_name' not in cols:
                conn.execute(
                    "ALTER TABLE users ADD COLUMN display_name TEXT NOT NULL DEFAULT ''"
                )
            if 'google_id' not in cols:
                conn.execute('ALTER TABLE users ADD COLUMN google_id TEXT')
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email
                ON users(email)
                WHERE email IS NOT NULL AND email != ''
            """)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id
                ON users(google_id)
                WHERE google_id IS NOT NULL AND google_id != ''
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS auth_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

    @staticmethod
    def _config(conn: sqlite3.Connection, key: str) -> Optional[str]:
        row = conn.execute(
            'SELECT value FROM auth_config WHERE key = ?', (key,)
        ).fetchone()
        return row['value'] if row else None

    @staticmethod
    def _set_config(
        conn: sqlite3.Connection, key: str, value: Optional[str]
    ) -> None:
        if value is None:
            conn.execute('DELETE FROM auth_config WHERE key = ?', (key,))
        else:
            conn.execute(
                """INSERT INTO auth_config (key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (key, value),
            )

    def get_config(self, key: str) -> Optional[str]:
        with self._connect() as conn:
            return self._config(conn, key)

    def set_config(self, key: str, value: Optional[str]) -> None:
        with self._lock, self._connect() as conn:
            self._set_config(conn, key, value)

    def get_google_client_id(self) -> str:
        env_val = os.environ.get(
            'DOWNTIFY_GOOGLE_CLIENT_ID'
        ) or os.environ.get('GOOGLE_CLIENT_ID')
        if env_val and env_val.strip():
            return env_val.strip()
        val = self.get_config('google_client_id')
        return val.strip() if val else ''

    def get_google_client_secret(self) -> str:
        env_val = os.environ.get(
            'DOWNTIFY_GOOGLE_CLIENT_SECRET'
        ) or os.environ.get('GOOGLE_CLIENT_SECRET')
        if env_val and env_val.strip():
            return env_val.strip()
        val = self.get_config('google_client_secret')
        return val.strip() if val else ''

    # First run and upgrades

    def ensure_default_admin(self, *, existing_install: bool = False) -> bool:
        """Create the first admin when there are no users yet. Returns
        whether one was created.

        An *existing_install* (upgraded from a version without accounts)
        also gets the accounts notice. The single sign-in password of the
        version before, if one was set, becomes the admin's password, and
        the paired devices of that version are given to the admin.
        """

        with self._lock, self._connect() as conn:
            if conn.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                return False
            legacy = self._config(conn, 'password_hash')
            conn.execute(
                'INSERT INTO users (username, password_hash, role, '
                'default_password, created_at) VALUES (?, ?, ?, ?, ?)',
                (
                    DEFAULT_USERNAME,
                    legacy or hash_password(DEFAULT_PASSWORD),
                    ROLE_ADMIN,
                    0 if legacy else 1,
                    _now(),
                ),
            )
            admin_id = conn.execute(
                'SELECT id FROM users WHERE username = ?', (DEFAULT_USERNAME,)
            ).fetchone()['id']
            # Devices paired before accounts existed belong to the admin.
            columns = {
                r[1] for r in conn.execute('PRAGMA table_info(auth_devices)')
            }
            if 'user_id' in columns:
                conn.execute(
                    'UPDATE auth_devices SET user_id = ? WHERE user_id = 0',
                    (admin_id,),
                )
            if existing_install:
                self._set_config(
                    conn,
                    'accounts_notice',
                    'kept_password' if legacy else 'default_password',
                )
            self._set_config(conn, 'password_hash', None)
            self._set_config(conn, 'require_sign_in', None)
        return True

    def notice(self) -> Optional[dict[str, Any]]:
        """The one-time notice for an upgraded install, shown on the
        sign-in page until an admin has signed in with a password of
        their own: ``{username, password}`` - the password only when it
        is still the default (``None`` when the old one was kept)."""

        with self._connect() as conn:
            kind = self._config(conn, 'accounts_notice')
        if not kind:
            return None
        return {
            'username': DEFAULT_USERNAME,
            'password': DEFAULT_PASSWORD
            if kind == 'default_password'
            else None,
        }

    def clear_notice(self) -> None:
        with self._connect() as conn:
            self._set_config(conn, 'accounts_notice', None)

    def reset_admin(self) -> dict[str, Any]:
        """Recovery (``python main.py auth-reset``): an admin ``admin``
        with the default password, whether or not it existed."""

        with self._lock, self._connect() as conn:
            row = conn.execute(
                'SELECT id FROM users WHERE username = ?', (DEFAULT_USERNAME,)
            ).fetchone()
            if row is None:
                conn.execute(
                    'INSERT INTO users (username, password_hash, role, '
                    'default_password, created_at) VALUES (?, ?, ?, 1, ?)',
                    (
                        DEFAULT_USERNAME,
                        hash_password(DEFAULT_PASSWORD),
                        ROLE_ADMIN,
                        _now(),
                    ),
                )
            else:
                conn.execute(
                    'UPDATE users SET password_hash = ?, role = ?, '
                    'default_password = 1 WHERE id = ?',
                    (hash_password(DEFAULT_PASSWORD), ROLE_ADMIN, row['id']),
                )
        return self.by_username(DEFAULT_USERNAME) or {}

    # Signing in

    def authenticate(
        self, username: str, password: str
    ) -> Optional[dict[str, Any]]:
        """The user, when *username* and *password* match; else ``None``.
        Takes as long either way."""

        with self._connect() as conn:
            row = conn.execute(
                'SELECT * FROM users WHERE username = ?',
                (str(username or '').strip(),),
            ).fetchone()
        stored = row['password_hash'] if row else self._dummy_hash
        ok = verify_password(str(password or ''), stored)
        if row is None or not ok:
            return None
        return public_user(row)

    def record_login(self, user_id: int, ip: str) -> None:
        with self._connect() as conn:
            conn.execute(
                'UPDATE users SET last_login_at = ?, last_login_ip = ? '
                'WHERE id = ?',
                (_now(), ip[:64], user_id),
            )

    # Reading

    def get(self, user_id: int) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT * FROM users WHERE id = ?', (user_id,)
            ).fetchone()
        return public_user(row) if row else None

    def by_username(self, username: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT * FROM users WHERE username = ? COLLATE NOCASE',
                (username,),
            ).fetchone()
        return public_user(row) if row else None

    def by_email(self, email: str) -> Optional[dict[str, Any]]:
        clean = clean_email(email)
        if not clean:
            return None
        with self._connect() as conn:
            row = conn.execute(
                'SELECT * FROM users WHERE email = ? COLLATE NOCASE',
                (clean,),
            ).fetchone()
        return public_user(row) if row else None

    def by_google_id(self, google_id: str) -> Optional[dict[str, Any]]:
        gid = str(google_id or '').strip()
        if not gid:
            return None
        with self._connect() as conn:
            row = conn.execute(
                'SELECT * FROM users WHERE google_id = ?',
                (gid,),
            ).fetchone()
        return public_user(row) if row else None

    def list(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT * FROM users ORDER BY username COLLATE NOCASE'
            ).fetchall()
        return [public_user(r) for r in rows]

    def first_admin(self) -> Optional[dict[str, Any]]:
        """The oldest admin - who everyone is when sign-in is turned off
        (``DOWNTIFY_DISABLE_AUTH``)."""

        with self._connect() as conn:
            row = conn.execute(
                'SELECT * FROM users WHERE role = ? ORDER BY id LIMIT 1',
                (ROLE_ADMIN,),
            ).fetchone()
        return public_user(row) if row else None

    def admin_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT COUNT(*) AS n FROM users WHERE role = ?', (ROLE_ADMIN,)
            ).fetchone()
        return int(row['n'])

    # Changing

    @classmethod
    def _random_username(cls, conn: sqlite3.Connection) -> str:
        """Generate a random username consisting of a word with numbers."""
        for _ in range(100):
            word = secrets.choice(_RANDOM_WORDS)
            num = secrets.randbelow(9000) + 1000
            candidate = f'{word}{num}'
            row = conn.execute(
                'SELECT id FROM users WHERE username = ? COLLATE NOCASE',
                (candidate,),
            ).fetchone()
            if not row:
                return candidate
        return f'user{secrets.randbelow(900000) + 100000}'

    @staticmethod
    def _unique_username(
        conn: sqlite3.Connection,
        preferred: str,
        exclude_id: Optional[int] = None,
    ) -> str:
        base = re.sub(
            r'[^A-Za-z0-9._-]', '', str(preferred or '').strip().lower()
        )
        if len(base) < 3:
            base = 'user'
        base = base[:26]
        candidate = base
        count = 1
        while True:
            row = conn.execute(
                'SELECT id FROM users WHERE username = ? COLLATE NOCASE',
                (candidate,),
            ).fetchone()
            if not row or (exclude_id is not None and row['id'] == exclude_id):
                return candidate
            count += 1
            candidate = f'{base}_{count}'[:32]

    def sign_up(
        self,
        username: Optional[str] = None,
        password: Any = None,
        *,
        email: Optional[str] = None,
        display_name: str = '',
        role: str = ROLE_USER,
    ) -> dict[str, Any]:
        """Sign up a new user account (defaults to standard ROLE_USER).
        If an account with this email already exists:
        - If it had no custom password (e.g. created via Google), merges
          password and display name into that existing account.
        - If it already has a password, raises UserError.
        """
        secret = check_password_rules(password)
        clean_em = clean_email(email) if email else None
        disp_name = clean_display_name(display_name)
        if role not in ROLES:
            raise UserError('Unknown role')

        with self._lock:
            with self._connect() as conn:
                existing_merged = False
                if clean_em:
                    existing = conn.execute(
                        'SELECT * FROM users WHERE email = ? COLLATE NOCASE',
                        (clean_em,),
                    ).fetchone()
                    if existing:
                        if (
                            not existing['password_hash']
                            or existing['default_password']
                            or (
                                existing['google_id']
                                and not existing['password_hash']
                            )
                            or existing['default_password'] == 1
                        ):
                            conn.execute(
                                'UPDATE users SET password_hash = ?, default_password = 0, '
                                'display_name = CASE WHEN display_name = "" THEN ? ELSE display_name END '
                                'WHERE id = ?',
                                (
                                    hash_password(secret),
                                    disp_name,
                                    existing['id'],
                                ),
                            )
                            user_id = existing['id']
                            existing_merged = True
                        else:
                            raise UserError(
                                'An account with this email already exists'
                            )

                if not existing_merged:
                    uname = str(username or '').strip()
                    if not uname:
                        base = (
                            clean_em.split('@')[0]
                            if clean_em
                            else (disp_name or 'user')
                        )
                        uname = self._unique_username(conn, base)
                    else:
                        uname = clean_username(uname)
                        row = conn.execute(
                            'SELECT id FROM users WHERE username = ? COLLATE NOCASE',
                            (uname,),
                        ).fetchone()
                        if row:
                            raise UserError('That username is taken')

                    try:
                        conn.execute(
                            'INSERT INTO users (username, password_hash, role, created_at, '
                            'email, display_name) VALUES (?, ?, ?, ?, ?, ?)',
                            (
                                uname,
                                hash_password(secret),
                                role,
                                _now(),
                                clean_em,
                                disp_name,
                            ),
                        )
                    except sqlite3.IntegrityError as exc:
                        if 'email' in str(exc).lower():
                            raise UserError(
                                'An account with this email already exists'
                            ) from exc
                        raise UserError('That username is taken') from exc
                    user_id = conn.execute(
                        'SELECT id FROM users WHERE username = ?', (uname,)
                    ).fetchone()['id']
            return self.get(user_id) or {}

    def authenticate_google(
        self, google_id: str, email: str, display_name: str = ''
    ) -> dict[str, Any]:
        """Authenticate or register a user via Google OAuth.
        Automatically merges accounts sharing the same email address.
        """
        gid = str(google_id or '').strip()
        if not gid:
            raise UserError('Invalid Google account ID')
        clean_em = clean_email(email)
        if not clean_em:
            raise UserError('Google account missing valid email address')
        disp_name = clean_display_name(display_name)

        with self._lock:
            with self._connect() as conn:
                # 1. Existing by google_id
                row = conn.execute(
                    'SELECT * FROM users WHERE google_id = ?', (gid,)
                ).fetchone()
                if row:
                    updates = {}
                    if not row['email']:
                        updates['email'] = clean_em
                    if not row['display_name'] and disp_name:
                        updates['display_name'] = disp_name
                    if updates:
                        assignments = ', '.join(f'{k} = ?' for k in updates)
                        conn.execute(
                            f'UPDATE users SET {assignments} WHERE id = ?',
                            (*updates.values(), row['id']),
                        )
                    user_id = row['id']
                else:
                    # 2. Existing by email -> MERGE Google account into existing user!
                    row = conn.execute(
                        'SELECT * FROM users WHERE email = ? COLLATE NOCASE',
                        (clean_em,),
                    ).fetchone()
                    if row:
                        conn.execute(
                            'UPDATE users SET google_id = ?, '
                            'display_name = CASE WHEN display_name = "" THEN ? ELSE display_name END '
                            'WHERE id = ?',
                            (gid, disp_name, row['id']),
                        )
                        user_id = row['id']
                    else:
                        # 3. Create new user with randomly generated word+numbers username
                        uname = self._random_username(conn)
                        conn.execute(
                            'INSERT INTO users (username, password_hash, role, created_at, '
                            'email, display_name, google_id, default_password) VALUES (?, ?, ?, ?, ?, ?, ?, 0)',
                            (
                                uname,
                                '',
                                ROLE_USER,
                                _now(),
                                clean_em,
                                disp_name,
                                gid,
                            ),
                        )
                        new_row = conn.execute(
                            'SELECT id FROM users WHERE username = ?', (uname,)
                        ).fetchone()
                        user_id = new_row['id']
                if user_id:
                    conn.execute(
                        'UPDATE users SET default_password = 0 WHERE id = ? AND default_password = 1 AND google_id != ""',
                        (user_id,),
                    )
            return self.get(user_id) or {}

    def merge_users(self, target_id: int, source_id: int) -> dict[str, Any]:
        """Merge source_id into target_id: reassign devices and sessions,
        keep non-empty profile fields, and delete source_id."""
        if target_id == source_id:
            return self.get(target_id) or {}
        with self._lock:
            with self._connect() as conn:
                target = conn.execute(
                    'SELECT * FROM users WHERE id = ?', (target_id,)
                ).fetchone()
                source = conn.execute(
                    'SELECT * FROM users WHERE id = ?', (source_id,)
                ).fetchone()
                if not target or not source:
                    raise UserError('User not found')

                email = target['email'] or source['email']
                disp = target['display_name'] or source['display_name']
                gid = target['google_id'] or source['google_id']

                for table in ('auth_devices', 'auth_sessions'):
                    cols = {
                        r[1]
                        for r in conn.execute(f'PRAGMA table_info({table})')
                    }
                    if 'user_id' in cols:
                        conn.execute(
                            f'UPDATE {table} SET user_id = ? WHERE user_id = ?',
                            (target_id, source_id),
                        )

                conn.execute('DELETE FROM users WHERE id = ?', (source_id,))
                conn.execute(
                    'UPDATE users SET email = ?, display_name = ?, google_id = ? WHERE id = ?',
                    (email, disp, gid, target_id),
                )
            return self.get(target_id) or {}

    def create(
        self, username: Any, password: Any, role: str = ROLE_USER
    ) -> dict[str, Any]:
        name = clean_username(username)
        secret = check_password_rules(password)
        if role not in ROLES:
            raise UserError('Unknown role')
        try:
            with self._connect() as conn:
                conn.execute(
                    'INSERT INTO users (username, password_hash, role, '
                    'created_at) VALUES (?, ?, ?, ?)',
                    (name, hash_password(secret), role, _now()),
                )
        except sqlite3.IntegrityError as exc:
            raise UserError('That username is taken') from exc
        return self.by_username(name) or {}

    def update(
        self,
        user_id: int,
        *,
        username: Any = None,
        email: Any = None,
        display_name: Any = None,
        role: Optional[str] = None,
    ) -> dict[str, Any]:
        """Rename a user, change email/display_name and/or change their role."""
        with self._lock:
            current = self.get(user_id)
            if current is None:
                raise UserError('User not found')
            updates: dict[str, Any] = {}
            if username is not None:
                updates['username'] = clean_username(username)
            if display_name is not None:
                updates['display_name'] = clean_display_name(display_name)
            if email is not None:
                clean_em = clean_email(email)
                if clean_em:
                    with self._connect() as conn:
                        other = conn.execute(
                            'SELECT id FROM users WHERE email = ? COLLATE NOCASE AND id != ?',
                            (clean_em, user_id),
                        ).fetchone()
                        if other:
                            raise UserError(
                                'An account with this email already exists'
                            )
                updates['email'] = clean_em
            if role is not None:
                if role not in ROLES:
                    raise UserError('Unknown role')
                if (
                    current['role'] == ROLE_ADMIN
                    and role != ROLE_ADMIN
                    and self.admin_count() <= 1
                ):
                    raise UserError('The last admin must stay an admin')
                updates['role'] = role
            if updates:
                assignments = ', '.join(f'{key} = ?' for key in updates)
                try:
                    with self._connect() as conn:
                        conn.execute(
                            f'UPDATE users SET {assignments} WHERE id = ?',
                            (*updates.values(), user_id),
                        )
                except sqlite3.IntegrityError as exc:
                    if 'email' in str(exc).lower():
                        raise UserError(
                            'An account with this email already exists'
                        ) from exc
                    raise UserError('That username is taken') from exc
        return self.get(user_id) or {}

    def set_password(self, user_id: int, password: Any) -> None:
        secret = check_password_rules(password)
        with self._connect() as conn:
            cur = conn.execute(
                'UPDATE users SET password_hash = ?, default_password = 0 '
                'WHERE id = ?',
                (hash_password(secret), user_id),
            )
            if cur.rowcount == 0:
                raise UserError('User not found')

    def check_password(self, user_id: int, password: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT password_hash FROM users WHERE id = ?', (user_id,)
            ).fetchone()
        stored = row['password_hash'] if row else self._dummy_hash
        return bool(row) and verify_password(str(password or ''), stored)

    def delete(self, user_id: int) -> dict[str, Any]:
        with self._lock:
            current = self.get(user_id)
            if current is None:
                raise UserError('User not found')
            if current['role'] == ROLE_ADMIN and self.admin_count() <= 1:
                raise UserError('The last admin cannot be deleted')
            with self._connect() as conn:
                conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        return current

    # Preferences

    def preferences(self, user_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT prefs_json FROM users WHERE id = ?', (user_id,)
            ).fetchone()
        if row is None:
            return {}
        try:
            data = json.loads(row['prefs_json'])
        except ValueError:
            return {}
        return clean_preferences(data)

    def set_preferences(self, user_id: int, values: Any) -> dict[str, Any]:
        """Merge *values* into the user's preferences; the result."""

        merged = {**self.preferences(user_id), **clean_preferences(values)}
        with self._connect() as conn:
            conn.execute(
                'UPDATE users SET prefs_json = ? WHERE id = ?',
                (json.dumps(merged), user_id),
            )
        return merged
