"""What users do on the server: the activity log and who's playing what.

Admins see both in Settings > Activity (``GET /api/activity``,
``GET /api/activity/now``), much like a Jellyfin dashboard:

* :class:`ActivityLog` - a history kept in ``<data>/downtify_activity.db``:
  sign-ins (and failed ones), sign-outs, songs started, downloads asked
  for, likes, deleted files, tracks whose audio was replaced, apps paired and unpaired, accounts created,
  changed and deleted, settings saved. Entries older than
  :data:`RETENTION_DAYS` are dropped.
* :class:`NowPlaying` - kept in memory: what each browser tab and app is
  playing right now, from the reports players send to
  ``POST /api/activity/playback`` while they play. A player that stops
  reporting drops off after :data:`NOW_PLAYING_TIMEOUT` seconds.
"""

from __future__ import annotations

import collections
import json
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from .sqlite_utils import connect_sqlite

#: How long entries are kept.
RETENTION_DAYS = 90
#: A player that hasn't reported for this long isn't playing any more.
NOW_PLAYING_TIMEOUT = 90
#: Longest page of entries one request gets.
MAX_PAGE = 200

#: What entries record (``kind``).
KINDS = (
    'login',
    'login_failed',
    'logout',
    'playback',
    'download',
    'like',
    'unlike',
    'delete',
    'audio_replaced',
    'device_paired',
    'device_unpaired',
    'user_created',
    'user_updated',
    'user_deleted',
    'password_changed',
    'settings_changed',
)

_PRUNE_EVERY = 500


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clip(value: Any, length: int) -> str:
    return str(value or '')[:length]


def describe_user_agent(user_agent: str) -> str:
    """``Firefox on Linux``-style label for a browser, or ``''``."""

    ua = user_agent or ''
    browser = ''
    for name, pattern in (
        ('Edge', r'Edg/'),
        ('Opera', r'OPR/'),
        ('Firefox', r'Firefox/'),
        ('Chrome', r'Chrome/'),
        ('Safari', r'Safari/'),
    ):
        if re.search(pattern, ua):
            browser = name
            break
    system = ''
    for name, pattern in (
        ('Android', r'Android'),
        ('iOS', r'iPhone|iPad'),
        ('Windows', r'Windows'),
        ('macOS', r'Mac OS X'),
        ('Linux', r'Linux'),
    ):
        if re.search(pattern, ua):
            system = name
            break
    if browser and system:
        return f'{browser} on {system}'
    return browser or system


def track_label(track: dict[str, Any]) -> str:
    """``Artist - Title`` (or whichever of the two is known)."""

    title = str(track.get('title') or '').strip()
    artist = str(track.get('artist') or '').strip()
    if title and artist:
        return f'{artist} - {title}'
    return title or artist or str(track.get('file') or '').strip()


class ActivityLog:
    """The history of what users did, newest first."""

    def __init__(self, db_path: Path) -> None:
        self._path = str(db_path)
        self._lock = threading.Lock()
        self._since_prune = 0
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at TEXT NOT NULL,
                    user_id INTEGER NOT NULL DEFAULT 0,
                    username TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    detail_json TEXT NOT NULL DEFAULT '{}',
                    client TEXT NOT NULL DEFAULT '',
                    ip TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute(
                'CREATE INDEX IF NOT EXISTS activity_user '
                'ON activity (user_id, id)'
            )
        self.prune()

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self._path, row_factory=True)

    def record(
        self,
        kind: str,
        *,
        user_id: int = 0,
        username: str = '',
        summary: str = '',
        detail: Optional[dict[str, Any]] = None,
        client: str = '',
        ip: str = '',
    ) -> None:
        """Add an entry. *summary* is the one line shown for it (a song,
        a file, a username); *detail* anything else worth keeping."""

        with self._connect() as conn:
            conn.execute(
                'INSERT INTO activity (at, user_id, username, kind, '
                'summary, detail_json, client, ip) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    _now().isoformat(),
                    int(user_id or 0),
                    _clip(username, 64),
                    _clip(kind, 32),
                    _clip(summary, 300),
                    json.dumps(detail or {})[:4000],
                    _clip(client, 100),
                    _clip(ip, 64),
                ),
            )
        with self._lock:
            self._since_prune += 1
            due = self._since_prune >= _PRUNE_EVERY
            if due:
                self._since_prune = 0
        if due:
            self.prune()

    def entries(
        self,
        *,
        limit: int = 100,
        before: int = 0,
        user_id: int = 0,
        kinds: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """A page of entries, newest first: ``{entries, next}`` - pass
        ``next`` as *before* for the page after (``0`` at the end)."""

        limit = max(1, min(int(limit), MAX_PAGE))
        where = ['1 = 1']
        args: list[Any] = []
        if before:
            where.append('id < ?')
            args.append(int(before))
        if user_id:
            where.append('user_id = ?')
            args.append(int(user_id))
        if kinds:
            where.append(f'kind IN ({", ".join("?" for _ in kinds)})')
            args.extend(kinds)
        with self._connect() as conn:
            rows = conn.execute(
                f'SELECT * FROM activity WHERE {" AND ".join(where)} '
                'ORDER BY id DESC LIMIT ?',
                (*args, limit + 1),
            ).fetchall()
        entries = [self._entry(row) for row in rows[:limit]]
        more = len(rows) > limit
        return {
            'entries': entries,
            'next': entries[-1]['id'] if more and entries else 0,
        }

    @staticmethod
    def _entry(row: Any) -> dict[str, Any]:
        try:
            detail = json.loads(row['detail_json'])
        except ValueError:
            detail = {}
        return {
            'id': int(row['id']),
            'at': row['at'],
            'user_id': int(row['user_id']),
            'username': row['username'],
            'kind': row['kind'],
            'summary': row['summary'],
            'detail': detail,
            'client': row['client'],
            'ip': row['ip'],
        }

    def prune(self, days: int = RETENTION_DAYS) -> int:
        cutoff = (_now() - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            return conn.execute(
                'DELETE FROM activity WHERE at < ?', (cutoff,)
            ).rowcount

    def stats(
        self,
        *,
        user_id: int = 0,
        days: int = 90,
        genre_map: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Aggregate listening statistics from playback activity:
        by genre, artist, day, weekday, hour, and top tracks."""
        where = ["kind = 'playback'"]
        args: list[Any] = []
        if user_id:
            where.append('user_id = ?')
            args.append(int(user_id))
        if days > 0:
            cutoff = (_now() - timedelta(days=days)).isoformat()
            where.append('at >= ?')
            args.append(cutoff)

        with self._connect() as conn:
            rows = conn.execute(
                f'SELECT at, summary, detail_json FROM activity WHERE {" AND ".join(where)} '
                'ORDER BY at ASC',
                args,
            ).fetchall()

        genre_map = genre_map or {}
        artist_counts: dict[str, int] = collections.defaultdict(int)
        artist_durations: dict[str, float] = collections.defaultdict(float)
        genre_counts: dict[str, int] = collections.defaultdict(int)
        track_counts: dict[str, int] = collections.defaultdict(int)
        day_counts: dict[str, int] = collections.defaultdict(int)
        weekday_counts: dict[int, int] = collections.defaultdict(int)
        hour_counts: dict[int, int] = collections.defaultdict(int)

        total_plays = 0
        total_duration = 0.0

        for row in rows:
            total_plays += 1
            dt_str = str(row['at'])
            day_str = dt_str[:10]
            day_counts[day_str] += 1
            try:
                dt = datetime.fromisoformat(dt_str)
                weekday_counts[dt.weekday()] += 1
                hour_counts[dt.hour] += 1
            except Exception:
                pass

            try:
                detail = json.loads(row['detail_json'])
            except Exception:
                detail = {}
            track = detail.get('track') or {}
            artist = str(track.get('artist') or '').strip()
            title = str(track.get('title') or '').strip()
            summary = str(row['summary'] or '').strip()
            if not artist and ' - ' in summary:
                artist = summary.split(' - ')[0].strip()
            if not title and ' - ' in summary:
                title = summary.split(' - ', 1)[1].strip()
            elif not title:
                title = summary

            if artist:
                artist_counts[artist] += 1
            if title:
                t_lbl = f'{artist} - {title}' if artist else title
                track_counts[t_lbl] += 1

            dur = float(track.get('duration') or 0.0)
            if dur > 0:
                total_duration += dur
                if artist:
                    artist_durations[artist] += dur

            file_path = str(track.get('file') or '').strip()
            genre = (
                str(track.get('genre') or '').strip()
                or genre_map.get(file_path, '')
            )
            if genre:
                for g in [
                    p.strip() for p in re.split(r'[/,;&]', genre) if p.strip()
                ]:
                    genre_counts[g.capitalize()] += 1
            else:
                genre_counts['Unknown'] += 1

        top_artists = [
            {
                'artist': a,
                'plays': c,
                'duration': round(artist_durations.get(a, 0.0), 1),
            }
            for a, c in sorted(
                artist_counts.items(), key=lambda x: x[1], reverse=True
            )[:20]
        ]
        top_genres = [
            {
                'genre': g,
                'plays': c,
                'percentage': round((c / total_plays) * 100, 1)
                if total_plays
                else 0,
            }
            for g, c in sorted(
                genre_counts.items(), key=lambda x: x[1], reverse=True
            )[:15]
        ]
        top_tracks_list = [
            {'track': t, 'plays': c}
            for t, c in sorted(
                track_counts.items(), key=lambda x: x[1], reverse=True
            )[:20]
        ]
        by_day_list = [
            {'day': d, 'plays': c} for d, c in sorted(day_counts.items())
        ]
        weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        by_weekday_list = [
            {'weekday': weekdays[i], 'index': i, 'plays': weekday_counts[i]}
            for i in range(7)
        ]
        by_hour_list = [
            {'hour': h, 'plays': hour_counts[h]} for h in range(24)
        ]

        return {
            'total_plays': total_plays,
            'total_duration': round(total_duration, 1),
            'top_artists': top_artists,
            'top_genres': top_genres,
            'top_tracks': top_tracks_list,
            'by_day': by_day_list,
            'by_weekday': by_weekday_list,
            'by_hour': by_hour_list,
            'days': days,
        }


class NowPlaying:
    """What each player is playing, from its reports. In memory only."""

    def __init__(self, timeout: float = NOW_PLAYING_TIMEOUT) -> None:
        self._timeout = timeout
        self._lock = threading.Lock()
        # (user_id, player key) -> entry
        self._players: dict[tuple[int, str], dict[str, Any]] = {}

    def report(
        self,
        *,
        user_id: int,
        username: str,
        player: str,
        client: str,
        state: str,
        track: dict[str, Any],
        position: float = 0.0,
        ip: str = '',
    ) -> bool:
        """Note a player's report; whether it started a new song (the
        caller logs that). *state* ``stopped`` removes the player."""

        key = (int(user_id), player)
        now = time.monotonic()
        with self._lock:
            self._drop_stale(now)
            if state == 'stopped':
                self._players.pop(key, None)
                return False
            previous = self._players.get(key)
            song = str(track.get('track_id') or track.get('file') or '')
            started = previous is None or previous['song'] != song
            self._players[key] = {
                'user_id': int(user_id),
                'username': username,
                'client': client,
                'ip': ip,
                'song': song,
                'track': track,
                'paused': state == 'paused',
                'position': max(0.0, float(position or 0)),
                'seen': now,
                'started_at': (
                    _now().isoformat() if started else previous['started_at']
                ),
            }
        return started and state == 'playing'

    def _drop_stale(self, now: float) -> None:
        for key, entry in list(self._players.items()):
            if now - entry['seen'] > self._timeout:
                del self._players[key]

    def forget_user(self, user_id: int) -> None:
        with self._lock:
            for key in [k for k in self._players if k[0] == user_id]:
                del self._players[key]

    def active(self) -> list[dict[str, Any]]:
        """Players heard from lately, playing ones first."""

        now = time.monotonic()
        with self._lock:
            self._drop_stale(now)
            entries = [
                {
                    'user_id': e['user_id'],
                    'username': e['username'],
                    'client': e['client'],
                    'ip': e['ip'],
                    'track': e['track'],
                    'paused': e['paused'],
                    'position': e['position'],
                    'started_at': e['started_at'],
                    'seconds_ago': int(now - e['seen']),
                }
                for e in self._players.values()
            ]
        return sorted(
            entries, key=lambda e: (e['paused'], e['username'].lower())
        )


def clean_track(value: Any) -> dict[str, Any]:
    """The track a player reports, reduced to what's shown."""

    if not isinstance(value, dict):
        return {}
    track: dict[str, Any] = {
        key: _clip(value.get(key), 300)
        for key in (
            'title',
            'artist',
            'album',
            'file',
            'track_id',
            'cover',
            'genre',
        )
        if value.get(key)
    }
    try:
        duration = float(value.get('duration') or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration > 0:
        track['duration'] = round(duration, 1)
    return track
