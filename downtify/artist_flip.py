"""Everything the Now Playing "flip" tile shows about an artist, in one call.

The tile on the back of the Now Playing cover art shows the playing
artist's biography, popular songs and popular albums. Each already has its
own YouTube Music route (``/api/artists/info``, ``/api/artists/top_songs``,
``/api/artists/top_albums``) - but those all take a channel id, while the
player only knows the artist's *name*. :func:`artist_overview` resolves the
name once and fetches the three in parallel.

The bio comes from the artist's YouTube Music page (its "About" text). When
that page has none, the saved profile bio (Apple Music / Deezer, see
:mod:`downtify.artist_profile`) is used instead, so the tile isn't blank for
artists the Artist page already knows.

Results are kept in memory for :data:`CACHE_TTL_SECONDS`: flipping back and
forth, or skipping between songs by the same artist, must not cost three
YouTube Music round-trips every time.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

from downtify import artist_profile, providers

#: How long one artist's overview is served from memory.
CACHE_TTL_SECONDS = 6 * 60 * 60
#: Artists kept in memory at most (oldest dropped first).
CACHE_MAX_ENTRIES = 256
#: Popular songs / albums returned at most.
TOP_SONGS_LIMIT = 10
TOP_ALBUMS_LIMIT = 10

BIO_SOURCE_YOUTUBE = 'youtubemusic'
BIO_SOURCE_PROFILE = 'profile'

_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()


def _cache_key(name: str) -> str:
    return ' '.join(name.casefold().split())


def clear_cache() -> None:
    """Forget every cached overview (tests, or a settings change)."""
    with _cache_lock:
        _cache.clear()


def _cached(key: str, now: float) -> Optional[dict[str, Any]]:
    with _cache_lock:
        hit = _cache.get(key)
        if hit is None:
            return None
        stored_at, value = hit
        if now - stored_at > CACHE_TTL_SECONDS:
            _cache.pop(key, None)
            return None
        return value


def _store(key: str, value: dict[str, Any], now: float) -> None:
    with _cache_lock:
        _cache[key] = (now, value)
        while len(_cache) > CACHE_MAX_ENTRIES:
            oldest = min(_cache, key=lambda k: _cache[k][0])
            _cache.pop(oldest, None)


def _saved_profile(download_dir: Path, name: str) -> dict[str, Any]:
    try:
        return artist_profile.load_profile(download_dir, name)
    except Exception:
        logger.opt(exception=True).debug(
            'Could not read the saved profile for {!r}', name
        )
        return {}


def _channel_id(profile: dict[str, Any], name: str) -> str:
    """The artist's YouTube Music channel: the one their saved profile
    already pinned, else a strict exact-name lookup (never a loose first
    search hit - that would show a different artist's page)."""
    platforms = profile.get('platforms_id') or {}
    saved = str(platforms.get('youtubemusic') or '').strip()
    if saved:
        return saved
    try:
        return providers.resolve_artist_id(name) or ''
    except Exception:
        logger.opt(exception=True).debug(
            'YouTube Music artist lookup failed for {!r}', name
        )
        return ''


def _safe(fn: Callable[[str], Any], channel_id: str, empty: Any) -> Any:
    try:
        return fn(channel_id) or empty
    except Exception:
        logger.opt(exception=True).debug(
            '{} failed for {}', getattr(fn, '__name__', 'fetch'), channel_id
        )
        return empty


def artist_overview(
    name: str, download_dir: Path, *, now: Optional[float] = None
) -> dict[str, Any]:
    """``{name, channel_id, url, cover_url, bio, bio_source, top_songs,
    top_albums}`` for the artist called *name*.

    ``top_songs`` is shaped like ``/api/songs/search`` rows and
    ``top_albums`` like ``/api/albums/search`` rows. ``bio_source`` is
    ``'youtubemusic'``, ``'profile'`` (the saved Apple Music/Deezer bio) or
    ``''`` when there is no bio at all. Never raises for a lookup failure -
    the missing parts are just empty.
    """

    clean = name.strip()
    key = _cache_key(clean)
    stamp = time.time() if now is None else now
    if not key:
        return _empty(clean)
    hit = _cached(key, stamp)
    if hit is not None:
        return hit

    profile = _saved_profile(download_dir, clean)
    channel_id = _channel_id(profile, clean)

    info: dict[str, Any] = {}
    songs: list[dict[str, Any]] = []
    albums: list[dict[str, Any]] = []
    if channel_id:
        with ThreadPoolExecutor(max_workers=3) as pool:
            info_f = pool.submit(
                _safe, providers.artist_info_from_channel_id, channel_id, {}
            )
            songs_f = pool.submit(
                _safe,
                providers.artist_top_songs_from_channel_id,
                channel_id,
                [],
            )
            albums_f = pool.submit(
                _safe,
                providers.artist_top_albums_from_channel_id,
                channel_id,
                [],
            )
            info, songs, albums = (
                info_f.result(),
                songs_f.result(),
                albums_f.result(),
            )

    bio = str(info.get('description') or '').strip()
    bio_source = BIO_SOURCE_YOUTUBE if bio else ''
    if not bio:
        bio = str(profile.get('bio') or '').strip()
        bio_source = BIO_SOURCE_PROFILE if bio else ''

    result = {
        'name': str(info.get('name') or clean),
        'channel_id': channel_id,
        'url': (
            f'https://music.youtube.com/channel/{channel_id}'
            if channel_id
            else ''
        ),
        'cover_url': str(info.get('cover_url') or ''),
        'bio': bio,
        'bio_source': bio_source,
        'top_songs': list(songs)[:TOP_SONGS_LIMIT],
        'top_albums': list(albums)[:TOP_ALBUMS_LIMIT],
    }
    # A failed lookup isn't cached: the next flip tries again.
    if channel_id and (bio or songs or albums):
        _store(key, result, stamp)
    return result


def _empty(name: str) -> dict[str, Any]:
    return {
        'name': name,
        'channel_id': '',
        'url': '',
        'cover_url': '',
        'bio': '',
        'bio_source': '',
        'top_songs': [],
        'top_albums': [],
    }
