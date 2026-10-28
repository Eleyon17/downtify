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
                "DELETE FROM activity WHERE at < ? AND kind != 'playback'",
                (cutoff,),
            ).rowcount

    def stats(
        self,
        *,
        user_id: int = 0,
        days: int = 90,
        genre_map: Optional[dict[str, str]] = None,
        artist_genre_map: Optional[dict[str, str]] = None,
        track_meta_map: Optional[dict[str, dict[str, Any]]] = None,
        artist_meta_map: Optional[dict[str, dict[str, Any]]] = None,
        discover_listens: Optional[list[dict[str, Any]]] = None,
        library_totals: Optional[dict[str, int]] = None,
        include_legacy_unowned: bool = False,
    ) -> dict[str, Any]:
        """Aggregate listening statistics from playback activity:
        by genre, artist, album, day, weekday, hour, top tracks, streaks, and recent plays.
        When *days* <= 0, computes Lifetime (all-time) statistics; otherwise computes
        Rolling statistics over the last *days* days."""
        where = ["kind = 'playback'"]
        args: list[Any] = []
        if user_id:
            if include_legacy_unowned:
                where.append('user_id IN (?, 0)')
                args.append(int(user_id))
            else:
                where.append('user_id = ?')
                args.append(int(user_id))
        now_dt = _now()
        if days > 0:
            cutoff = (now_dt - timedelta(days=days)).isoformat()
            where.append('at >= ?')
            args.append(cutoff)

        with self._connect() as conn:
            rows = conn.execute(
                f'SELECT at, summary, detail_json FROM activity WHERE {" AND ".join(where)} '
                'ORDER BY at ASC',
                args,
            ).fetchall()

        genre_map = genre_map or {}
        artist_genre_map = artist_genre_map or {}
        track_meta_map = track_meta_map or {}
        artist_meta_map = artist_meta_map or {}
        library_totals = library_totals or {}

        artist_counts: dict[str, int] = collections.defaultdict(int)
        artist_durations: dict[str, float] = collections.defaultdict(float)
        artist_tracks_set: dict[str, set[str]] = collections.defaultdict(set)
        genre_counts: dict[str, int] = collections.defaultdict(int)
        genre_durations: dict[str, float] = collections.defaultdict(float)
        track_counts: dict[str, int] = collections.defaultdict(int)
        track_durations: dict[str, float] = collections.defaultdict(float)
        track_info: dict[str, dict[str, Any]] = {}
        album_counts: dict[str, int] = collections.defaultdict(int)
        album_durations: dict[str, float] = collections.defaultdict(float)
        album_info: dict[str, dict[str, Any]] = {}
        day_counts: dict[str, int] = collections.defaultdict(int)
        day_durations: dict[str, float] = collections.defaultdict(float)
        weekday_counts: dict[int, int] = collections.defaultdict(int)
        weekday_durations: dict[int, float] = collections.defaultdict(float)
        hour_counts: dict[int, int] = collections.defaultdict(int)
        hour_durations: dict[int, float] = collections.defaultdict(float)

        total_plays = 0
        total_duration = 0.0
        first_play_at = ''
        last_play_at = ''
        recent_plays: list[dict[str, Any]] = []

        def _strip_ext(p: str) -> str:
            return re.sub(r'\.[^./\\]+$', '', p)

        for row in rows:
            dt_str = str(row['at'] or '')
            if not first_play_at and dt_str:
                first_play_at = dt_str
            if dt_str:
                last_play_at = dt_str

            try:
                detail = json.loads(row['detail_json'])
            except Exception:
                detail = {}
            track = detail.get('track') or {}
            artist = str(track.get('artist') or '').strip()
            title = str(track.get('title') or '').strip()
            album = str(track.get('album') or '').strip()
            file_path = str(track.get('file') or '').strip()
            norm_file = file_path.replace('\\', '/')
            stem_file = _strip_ext(norm_file).lower() if norm_file else ''
            base_stem = Path(norm_file).stem.lower() if norm_file else ''

            summary = str(row['summary'] or '').strip()
            if not artist and ' - ' in summary:
                artist = summary.split(' - ')[0].strip()
            if not title and ' - ' in summary:
                title = summary.split(' - ', 1)[1].strip()
            elif not title:
                title = summary

            # Enrich missing fields from library metadata
            meta = (
                track_meta_map.get(file_path)
                or track_meta_map.get(norm_file)
                or (track_meta_map.get(f'stem:{stem_file}') if stem_file else None)
                or (track_meta_map.get(f'base:{base_stem}') if base_stem else None)
                or (
                    track_meta_map.get(f'song:{artist.lower()}|{title.lower()}')
                    if artist and title
                    else None
                )
                or {}
            )
            if not artist and meta.get('artist'):
                artist = str(meta['artist']).strip()
            if not title and meta.get('title'):
                title = str(meta['title']).strip()
            if not album and meta.get('album'):
                album = str(meta['album']).strip()
            if not norm_file and meta.get('file'):
                norm_file = str(meta['file']).replace('\\', '/')
                file_path = norm_file

            art_meta = artist_meta_map.get(artist.lower(), {}) if artist else {}
            if artist and art_meta.get('display_name'):
                artist = str(art_meta['display_name'])

            dur = float(track.get('duration') or meta.get('duration') or 0.0)
            if dur <= 0 and (artist or title):
                dur = float(art_meta.get('avg_duration') or 210.0)

            genre = (
                str(track.get('genre') or '').strip()
                or str(meta.get('genre') or '').strip()
                or genre_map.get(file_path, '')
                or genre_map.get(norm_file, '')
                or (genre_map.get(f'stem:{stem_file}', '') if stem_file else '')
                or (genre_map.get(f'base:{base_stem}', '') if base_stem else '')
                or artist_genre_map.get(artist.lower(), '')
            )
            if not genre and artist:
                for sub_art in [p.strip() for p in re.split(r'[,;&/]|feat\.|ft\.', artist, flags=re.I) if p.strip()]:
                    g_cand = artist_genre_map.get(sub_art.lower(), '')
                    if g_cand:
                        genre = g_cand
                        break

            total_plays += 1
            day_str = dt_str[:10]
            if day_str:
                day_counts[day_str] += 1
                day_durations[day_str] += dur
            try:
                dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                weekday_counts[dt.weekday()] += 1
                weekday_durations[dt.weekday()] += dur
                hour_counts[dt.hour] += 1
                hour_durations[dt.hour] += dur
            except Exception:
                pass

            if artist:
                artist_counts[artist] += 1
            if title:
                t_lbl = f'{artist} - {title}' if artist else title
                track_counts[t_lbl] += 1
                track_durations[t_lbl] += dur
                if artist:
                    artist_tracks_set[artist].add(t_lbl)
                if t_lbl not in track_info or (norm_file and not track_info[t_lbl].get('file')):
                    track_info[t_lbl] = {
                        'track': t_lbl,
                        'title': title,
                        'artist': artist,
                        'album': album,
                        'file': norm_file,
                        'duration_single': round(dur, 1),
                    }
            if album and album.lower() not in {'unknown', 'unknown album', 'single'}:
                alb_key = f'{artist} — {album}' if artist else album
                album_counts[alb_key] += 1
                album_durations[alb_key] += dur
                if alb_key not in album_info:
                    album_info[alb_key] = {
                        'album': album,
                        'artist': artist,
                        'file': norm_file,
                    }

            if dur > 0:
                total_duration += dur
                if artist:
                    artist_durations[artist] += dur

            primary_genre = ''
            if genre and genre.lower() != 'unknown':
                for g in [
                    p.strip() for p in re.split(r'[/,;&]', genre) if p.strip()
                ]:
                    if g and g.lower() != 'unknown':
                        g_cap = g[:1].upper() + g[1:] if len(g) > 1 else g.upper()
                        if not primary_genre:
                            primary_genre = g_cap
                        genre_counts[g_cap] += 1
                        genre_durations[g_cap] += dur

            recent_plays.append({
                'at': dt_str,
                'title': title or summary or 'Unknown Track',
                'artist': artist,
                'album': album,
                'genre': primary_genre,
                'duration': round(dur, 1),
                'file': norm_file,
            })

        # For Lifetime stats (days <= 0) or when discover_listens has historical plays
        # that predate the activity log, reconcile artist play counts so lifetime stats are complete.
        if discover_listens:
            existing_by_lower = {a.lower(): a for a in artist_counts}
            cutoff_iso = (now_dt - timedelta(days=days)).isoformat() if days > 0 else ''
            for d_row in discover_listens:
                d_name = str(d_row.get('name') or '').strip()
                d_plays = int(d_row.get('plays') or 0)
                d_last = str(d_row.get('last_played') or '').strip()
                if not d_name or d_plays <= 0:
                    continue
                if days > 0 and d_last and d_last < cutoff_iso:
                    continue
                art_lower = d_name.lower()
                art_meta = artist_meta_map.get(art_lower, {})
                canonical = existing_by_lower.get(art_lower) or str(art_meta.get('display_name') or d_name)
                current_c = artist_counts.get(canonical, 0)
                # For lifetime (days <= 0), any excess plays in discover_listens are historical plays.
                # For rolling (days > 0), only backfill if activity had 0 plays for an artist played in window.
                extra = (d_plays - current_c) if days <= 0 else (1 if current_c == 0 and d_last >= cutoff_iso else 0)
                if extra > 0:
                    avg_dur = float(art_meta.get('avg_duration') or 210.0)
                    extra_dur = extra * avg_dur
                    artist_counts[canonical] += extra
                    artist_durations[canonical] += extra_dur
                    total_plays += extra
                    total_duration += extra_dur
                    existing_by_lower[art_lower] = canonical
                    g_str = artist_genre_map.get(art_lower, '')
                    if g_str and g_str.lower() != 'unknown':
                        for g in [p.strip() for p in re.split(r'[/,;&]', g_str) if p.strip()]:
                            if g and g.lower() != 'unknown':
                                g_cap = g[:1].upper() + g[1:] if len(g) > 1 else g.upper()
                                genre_counts[g_cap] += extra
                                genre_durations[g_cap] += extra_dur
                    if d_last and len(d_last) >= 10:
                        d_day = d_last[:10]
                        if d_day not in day_counts:
                            day_counts[d_day] += extra
                            day_durations[d_day] += extra_dur

        top_artists = [
            {
                'artist': a,
                'plays': c,
                'duration': round(artist_durations.get(a, 0.0), 1),
                'unique_tracks': len(artist_tracks_set.get(a, set())),
                'percentage': round((c / total_plays) * 100, 1) if total_plays else 0,
            }
            for a, c in sorted(
                artist_counts.items(),
                key=lambda x: (x[1], artist_durations.get(x[0], 0.0)),
                reverse=True,
            )[:20]
        ]
        known_genre_total = sum(genre_counts.values())
        top_genres = [
            {
                'genre': g,
                'plays': c,
                'duration': round(genre_durations.get(g, 0.0), 1),
                'percentage': round((c / known_genre_total) * 100, 1)
                if known_genre_total
                else 0,
            }
            for g, c in sorted(
                genre_counts.items(),
                key=lambda x: (x[1], genre_durations.get(x[0], 0.0)),
                reverse=True,
            )[:15]
            if g.lower() != 'unknown'
        ]
        top_tracks_list = [
            {
                **(track_info.get(t) or {'track': t, 'title': t, 'artist': '', 'album': '', 'file': ''}),
                'track': t,
                'plays': c,
                'duration': round(track_durations.get(t, 0.0), 1),
            }
            for t, c in sorted(
                track_counts.items(),
                key=lambda x: (x[1], track_durations.get(x[0], 0.0)),
                reverse=True,
            )[:20]
        ]
        top_albums_list = [
            {
                'album': (album_info.get(alb) or {}).get('album') or alb,
                'artist': (album_info.get(alb) or {}).get('artist') or '',
                'file': (album_info.get(alb) or {}).get('file') or '',
                'plays': c,
                'duration': round(album_durations.get(alb, 0.0), 1),
            }
            for alb, c in sorted(
                album_counts.items(),
                key=lambda x: (x[1], album_durations.get(x[0], 0.0)),
                reverse=True,
            )[:15]
        ]
        by_day_list = [
            {
                'day': d,
                'plays': c,
                'duration': round(day_durations.get(d, 0.0), 1),
            }
            for d, c in sorted(day_counts.items())
        ]
        # Build a continuous daily series for rolling windows (e.g. 30 days)
        # so the timeline accurately reflects every calendar day in the window.
        by_day_series: list[dict[str, Any]] = []
        if 0 < days <= 90:
            today_date = now_dt.date()
            for offset in range(days - 1, -1, -1):
                d_iso = (today_date - timedelta(days=offset)).isoformat()
                by_day_series.append({
                    'day': d_iso,
                    'plays': day_counts.get(d_iso, 0),
                    'duration': round(day_durations.get(d_iso, 0.0), 1),
                })
        else:
            by_day_series = list(by_day_list)

        weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        by_weekday_list = [
            {
                'weekday': weekdays[i],
                'index': i,
                'plays': weekday_counts[i],
                'duration': round(weekday_durations.get(i, 0.0), 1),
            }
            for i in range(7)
        ]

        def _hour_label(h: int) -> str:
            if h == 0:
                return '12 AM'
            if h < 12:
                return f'{h} AM'
            if h == 12:
                return '12 PM'
            return f'{h - 12} PM'

        by_hour_list = [
            {
                'hour': h,
                'label': _hour_label(h),
                'plays': hour_counts[h],
                'duration': round(hour_durations.get(h, 0.0), 1),
            }
            for h in range(24)
        ]

        # Streaks & active days
        active_dates = sorted(
            datetime.fromisoformat(d).date()
            for d, c in day_counts.items()
            if c > 0 and len(d) == 10
        )
        active_days = len(active_dates)
        longest_streak = 0
        current_streak = 0
        if active_dates:
            run = 1
            longest_streak = 1
            for idx in range(1, len(active_dates)):
                if (active_dates[idx] - active_dates[idx - 1]).days == 1:
                    run += 1
                    if run > longest_streak:
                        longest_streak = run
                elif active_dates[idx] != active_dates[idx - 1]:
                    run = 1
            today_d = now_dt.date()
            if (today_d - active_dates[-1]).days <= 1:
                current_streak = 1
                for idx in range(len(active_dates) - 1, 0, -1):
                    if (active_dates[idx] - active_dates[idx - 1]).days == 1:
                        current_streak += 1
                    else:
                        break

        peak_day_obj = None
        if by_day_list:
            best_d = max(by_day_list, key=lambda x: (x['plays'], x['duration']))
            peak_day_obj = best_d

        peak_hour_obj = None
        if any(h['plays'] > 0 for h in by_hour_list):
            best_h = max(by_hour_list, key=lambda x: (x['plays'], x['duration']))
            hr = best_h['hour']
            if 5 <= hr < 12:
                persona = 'Morning Listener'
            elif 12 <= hr < 17:
                persona = 'Afternoon Listener'
            elif 17 <= hr < 22:
                persona = 'Evening Listener'
            else:
                persona = 'Night Owl'
            peak_hour_obj = {**best_h, 'persona': persona}

        window_days = days if days > 0 else max(active_days, 1)
        avg_daily_plays = round(total_plays / max(active_days, 1), 1) if total_plays else 0.0
        avg_daily_duration = round(total_duration / max(active_days, 1), 1) if total_duration else 0.0
        rolling_daily_plays = round(total_plays / max(window_days, 1), 1) if total_plays else 0.0
        rolling_daily_duration = round(total_duration / max(window_days, 1), 1) if total_duration else 0.0

        unique_artists_count = len(artist_counts)
        unique_tracks_count = len(track_counts)
        unique_albums_count = len(album_counts)
        lib_tracks = int(library_totals.get('total_tracks') or 0)
        lib_artists = int(library_totals.get('total_artists') or 0)
        lib_albums = int(library_totals.get('total_albums') or 0)

        return {
            'mode': 'rolling' if days > 0 else 'lifetime',
            'days': days,
            'total_plays': total_plays,
            'total_duration': round(total_duration, 1),
            'unique_artists': unique_artists_count,
            'unique_tracks': unique_tracks_count,
            'unique_albums': unique_albums_count,
            'active_days': active_days,
            'current_streak': current_streak,
            'longest_streak': longest_streak,
            'avg_daily_plays': avg_daily_plays,
            'avg_daily_duration': avg_daily_duration,
            'rolling_daily_plays': rolling_daily_plays,
            'rolling_daily_duration': rolling_daily_duration,
            'peak_day': peak_day_obj,
            'peak_hour': peak_hour_obj,
            'first_play_at': first_play_at,
            'last_play_at': last_play_at,
            'top_artists': top_artists,
            'top_genres': top_genres,
            'top_tracks': top_tracks_list,
            'top_albums': top_albums_list,
            'by_day': by_day_list,
            'by_day_series': by_day_series,
            'by_weekday': by_weekday_list,
            'by_hour': by_hour_list,
            'recent_plays': list(reversed(recent_plays[-15:])),
            'library_coverage': {
                'tracks_played': unique_tracks_count,
                'total_tracks': lib_tracks,
                'tracks_pct': round(min(100.0, (unique_tracks_count / lib_tracks) * 100), 1)
                if lib_tracks
                else 0.0,
                'artists_played': unique_artists_count,
                'total_artists': lib_artists,
                'artists_pct': round(min(100.0, (unique_artists_count / lib_artists) * 100), 1)
                if lib_artists
                else 0.0,
                'albums_played': unique_albums_count,
                'total_albums': lib_albums,
                'albums_pct': round(min(100.0, (unique_albums_count / lib_albums) * 100), 1)
                if lib_albums
                else 0.0,
            },
        }


class NowPlaying:
    """What each player is playing, from its reports. In memory only."""

    def __init__(self, timeout: float = NOW_PLAYING_TIMEOUT) -> None:
        self._timeout = timeout
        self._lock = threading.Lock()
        # (user_id, player key) -> entry
        self._players: dict[tuple[int, str], dict[str, Any]] = {}
        # Remember the last song per player across pause timeouts so resuming
        # a paused song after >90s does not log a duplicate play.
        self._last_session: dict[tuple[int, str], dict[str, Any]] = {}

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
        pos = max(0.0, float(position or 0))
        with self._lock:
            self._drop_stale(now)
            if state == 'stopped':
                self._players.pop(key, None)
                self._last_session.pop(key, None)
                return False
            previous = self._players.get(key) or self._last_session.get(key)
            song = str(track.get('track_id') or track.get('file') or '')
            prev_max = float((previous or {}).get('max_position') or 0.0)
            replayed_same = (
                previous is not None
                and previous['song'] == song
                and state == 'playing'
                and prev_max >= 30.0
                and pos < 5.0
            )
            started = previous is None or previous['song'] != song or replayed_same
            max_pos = pos if started else max(prev_max, pos)
            entry = {
                'user_id': int(user_id),
                'username': username,
                'client': client,
                'ip': ip,
                'song': song,
                'track': track,
                'paused': state == 'paused',
                'position': pos,
                'max_position': max_pos,
                'seen': now,
                'started_at': (
                    _now().isoformat() if started else previous['started_at']
                ),
            }
            self._players[key] = entry
            self._last_session[key] = entry
        return started and state == 'playing'

    def _drop_stale(self, now: float) -> None:
        for key, entry in list(self._players.items()):
            if now - entry['seen'] > self._timeout:
                del self._players[key]
        for key, entry in list(self._last_session.items()):
            if now - entry['seen'] > 21600:
                del self._last_session[key]

    def forget_user(self, user_id: int) -> None:
        with self._lock:
            for key in [k for k in self._players if k[0] == user_id]:
                del self._players[key]
            for key in [k for k in self._last_session if k[0] == user_id]:
                del self._last_session[key]

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
