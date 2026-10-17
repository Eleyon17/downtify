"""Never-expiring public share links for songs and playlists.

A shared song or playlist can be accessed without login, granting only
the ability to listen, skip, play/pause, and manage the queue for that
shared content.
"""

from __future__ import annotations

import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .sqlite_utils import connect_sqlite


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


import mimetypes

_AUDIO_TYPES = {
    '.mp3': 'audio/mpeg',
    '.flac': 'audio/flac',
    '.m4a': 'audio/mp4',
    '.mp4': 'audio/mp4',
    '.ogg': 'audio/ogg',
    '.opus': 'audio/ogg',
    '.wav': 'audio/wav',
}


def audio_media_type(path: Path) -> str:
    return (
        _AUDIO_TYPES.get(path.suffix.lower())
        or mimetypes.guess_type(path.name)[0]
        or 'application/octet-stream'
    )


def new_share_id() -> str:
    """A URL-safe 22-character random token."""
    return secrets.token_urlsafe(16)


class ShareStore:
    """Storage for share links in SQLite."""

    def __init__(self, db_path: Path) -> None:
        self._path = str(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self):
        return connect_sqlite(self._path, row_factory=True)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS shares (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    target TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    user_id INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_shares_user ON shares(user_id)
            """)

    def create_share(
        self,
        kind: str,
        target: str,
        title: str = '',
        user_id: int = 0,
    ) -> dict[str, Any]:
        """Create and store a new share link."""
        kind_norm = 'playlist' if str(kind or '').strip().lower() == 'playlist' else 'track'
        target_norm = str(target or '').strip()
        title_norm = str(title or '').strip()
        share_id = new_share_id()
        now = _now_iso()

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO shares (id, kind, target, title, user_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (share_id, kind_norm, target_norm, title_norm, int(user_id), now),
            )
        return {
            'id': share_id,
            'kind': kind_norm,
            'target': target_norm,
            'title': title_norm,
            'user_id': int(user_id),
            'created_at': now,
        }

    def get_share(self, share_id: str) -> Optional[dict[str, Any]]:
        """Fetch a share by ID."""
        clean_id = str(share_id or '').strip()
        if not clean_id:
            return None
        with self._connect() as conn:
            row = conn.execute(
                'SELECT id, kind, target, title, user_id, created_at FROM shares WHERE id = ?',
                (clean_id,),
            ).fetchone()
            if row is None:
                return None
            return {
                'id': row['id'],
                'kind': row['kind'],
                'target': row['target'],
                'title': row['title'],
                'user_id': int(row['user_id']),
                'created_at': row['created_at'],
            }

    def list_shares(self, user_id: Optional[int] = None) -> list[dict[str, Any]]:
        """List shares, optionally filtered by creator user_id."""
        with self._connect() as conn:
            if user_id is not None:
                cur = conn.execute(
                    """
                    SELECT id, kind, target, title, user_id, created_at
                    FROM shares
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    """,
                    (int(user_id),),
                )
            else:
                cur = conn.execute(
                    """
                    SELECT id, kind, target, title, user_id, created_at
                    FROM shares
                    ORDER BY created_at DESC
                    """
                )
            rows = cur.fetchall()
            return [
                {
                    'id': row['id'],
                    'kind': row['kind'],
                    'target': row['target'],
                    'title': row['title'],
                    'user_id': int(row['user_id']),
                    'created_at': row['created_at'],
                }
                for row in rows
            ]

    def delete_share(self, share_id: str, user_id: Optional[int] = None) -> bool:
        """Delete a share by ID. If user_id is given, requires ownership."""
        clean_id = str(share_id or '').strip()
        if not clean_id:
            return False
        with self._lock, self._connect() as conn:
            if user_id is not None:
                cur = conn.execute(
                    'DELETE FROM shares WHERE id = ? AND user_id = ?',
                    (clean_id, int(user_id)),
                )
            else:
                cur = conn.execute('DELETE FROM shares WHERE id = ?', (clean_id,))
            return cur.rowcount > 0
