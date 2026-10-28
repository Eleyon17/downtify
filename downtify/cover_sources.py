"""Find the best cover art available for a track already on disk.

A library downloaded by an older Downtify often carries the smallest
image its source offered — 300x300 is common — while the same release is
published at 1200px or more elsewhere. This module gathers the covers
the known sources can offer for one track, measures them, and hands back
the one the user's preference asks for.

Nothing here writes to the file; :mod:`downtify.library_upgrade` decides
whether a candidate is worth embedding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus

import httpx
from loguru import logger

from . import itunes, providers, spotify
from .cover_art import extract_cover_art
from .image_size import image_short_side

_TIMEOUT = 20

#: What to ask iTunes for. Their CDN happily resizes past the master, so
#: a larger request is measured like any other candidate rather than
#: trusted.
ITUNES_REQUEST_PX = 1200

SOURCE_FILE = 'file'
SOURCE_SPOTIFY = 'spotify'
SOURCE_ITUNES = 'itunes'
SOURCE_YOUTUBE = 'youtube-music'

#: Settings values for "where should artwork come from".
PREFERENCE_HIGHEST = 'highest'
ARTWORK_SOURCES = (
    PREFERENCE_HIGHEST,
    SOURCE_SPOTIFY,
    SOURCE_ITUNES,
    SOURCE_YOUTUBE,
)

#: Spotify serves one image per size under a fixed id prefix. A library
#: tagged from the 300px variant can be pointed at the 640px one without
#: another API call.
_SPOTIFY_SIZE_PREFIXES = ('ab67616d00001e02', 'ab67616d00004851')
_SPOTIFY_LARGEST_PREFIX = 'ab67616d0000b273'
_SPOTIFY_IMAGE_HOST = 'i.scdn.co/image/'


@dataclass(frozen=True)
class CoverCandidate:
    """One cover image, already fetched and measured."""

    source: str
    data: bytes
    width: int
    url: str = ''

    @property
    def size_label(self) -> str:
        return f'{self.width}x{self.width}' if self.width else 'unknown'


def spotify_upgrade_url(url: str) -> str:
    """Point a small Spotify image URL at the largest published size."""

    if not url or _SPOTIFY_IMAGE_HOST not in url:
        return url
    for prefix in _SPOTIFY_SIZE_PREFIXES:
        if prefix in url:
            return url.replace(prefix, _SPOTIFY_LARGEST_PREFIX)
    return url


def _fetch(url: str) -> Optional[bytes]:
    if not url:
        return None
    try:
        resp = httpx.get(url, timeout=_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
    except Exception:
        logger.debug('Cover fetch failed: {}', url[:120])
        return None
    data = resp.content
    return data if data else None


def _candidate(source: str, url: str) -> Optional[CoverCandidate]:
    data = _fetch(url)
    if data is None:
        return None
    width = image_short_side(data)
    if not width:
        return None
    return CoverCandidate(source=source, data=data, width=width, url=url)


def _youtube_cover_url(song: dict[str, Any]) -> str:
    """A YouTube Music thumbnail for *song*, at the configured size."""

    artists = song.get('artists') or []
    artist = artists[0] if artists else (song.get('artist') or '')
    title = song.get('name') or song.get('title') or ''
    query = f'{artist} {title}'.strip()
    if not title:
        return ''
    try:
        results = providers.search_songs(query, limit=3)
    except Exception:
        logger.debug('Cover lookup: YouTube Music search failed')
        return ''
    for result in results:
        url = str(result.get('cover_url') or '')
        if url:
            return url
    return ''


def _spotify_cover_url(song: dict[str, Any]) -> str:
    url = spotify_upgrade_url(str(song.get('cover_url') or ''))
    if url:
        return url
    track_id = str(song.get('song_id') or '').strip()
    if not re.fullmatch(r'[A-Za-z0-9]{22}', track_id):
        return ''
    try:
        fetched = spotify.track_from_id(track_id)
    except Exception:
        logger.debug('Cover lookup: Spotify track {} failed', track_id)
        return ''
    return spotify_upgrade_url(str((fetched or {}).get('cover_url') or ''))


def current_cover(path: Path) -> Optional[CoverCandidate]:
    """The cover already embedded in (or sitting next to) *path*."""

    data, _mime = extract_cover_art(path)
    if not data:
        return None
    return CoverCandidate(
        source=SOURCE_FILE, data=data, width=image_short_side(data)
    )


def collect_candidates(
    song: dict[str, Any], *, sources: tuple[str, ...]
) -> list[CoverCandidate]:
    """Fetch and measure one cover per requested source, in order."""

    found: list[CoverCandidate] = []
    for source in sources:
        if source == SOURCE_SPOTIFY:
            url = _spotify_cover_url(song)
        elif source == SOURCE_ITUNES:
            url = itunes.fetch_artwork_url(song, size=ITUNES_REQUEST_PX)
        elif source == SOURCE_YOUTUBE:
            url = _youtube_cover_url(song)
        else:
            continue
        candidate = _candidate(source, url)
        if candidate is not None:
            found.append(candidate)
    return found


def _preferred_order(preference: str) -> tuple[str, ...]:
    remote = (SOURCE_SPOTIFY, SOURCE_ITUNES, SOURCE_YOUTUBE)
    if preference in remote:
        return (preference,) + tuple(s for s in remote if s != preference)
    return remote


def best_cover(
    song: dict[str, Any],
    *,
    current: Optional[CoverCandidate],
    preference: str = PREFERENCE_HIGHEST,
) -> Optional[CoverCandidate]:
    """The cover worth embedding, or ``None`` to leave the file alone.

    With a named preference, that source wins as long as it beats what
    the file already has; the others are only tried when it has nothing.
    With ``highest`` every source is asked and the largest image wins.
    A candidate has to be strictly larger than the current cover, so a
    re-run never rewrites a file for nothing.
    """

    have = current.width if current else 0
    order = _preferred_order(preference)

    if preference == PREFERENCE_HIGHEST:
        candidates = collect_candidates(song, sources=order)
    else:
        candidates = []
        for source in order:
            candidates = collect_candidates(song, sources=(source,))
            if candidates:
                # The preferred source answered; the rest are a fallback
                # for when it has nothing at all, not a size contest.
                break

    if not candidates:
        return None
    best = max(candidates, key=lambda c: c.width)
    return best if best.width > have else None


def search_cover_options(
    artist: str,
    album: str,
    *,
    file_path: Optional[Path] = None,
    query_override: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Gather high-resolution album cover options from iTunes, Deezer, Spotify, and YouTube Music."""

    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    clean_artist = str(artist or '').strip()
    clean_album = str(album or '').strip()
    search_query = (query_override or f'{clean_artist} {clean_album}').strip()

    def add_candidate(
        source: str, url: str, width: int, title: str = '', subtitle: str = ''
    ) -> None:
        if not url or url in seen_urls:
            return
        seen_urls.add(url)
        source_labels = {
            'itunes': 'iTunes',
            'deezer': 'Deezer',
            'spotify': 'Spotify',
            'youtube-music': 'YouTube Music',
            'current': 'Current Track Art',
        }
        candidates.append({
            'source': source,
            'source_label': source_labels.get(source, source.capitalize()),
            'url': url,
            'width': width,
            'height': width,
            'title': title or clean_album,
            'artist': subtitle or clean_artist,
        })

    # 1. iTunes Search (offers up to 1400x1400)
    if search_query:
        try:
            itunes_albums: list[dict[str, Any]] = []
            for entity in ('album', 'song'):
                params = f'term={quote_plus(search_query)}&entity={entity}&limit=5'
                url = f'https://itunes.apple.com/search?{params}'
                try:
                    resp = httpx.get(url, timeout=10)
                    if resp.status_code == 200:
                        itunes_albums.extend(
                            (resp.json() or {}).get('results') or []
                        )
                except Exception:
                    pass
                if len(itunes_albums) >= 4:
                    break

            for item in itunes_albums:
                raw_url = str(item.get('artworkUrl100') or '')
                if not raw_url:
                    continue
                hi_res = re.sub(r'/\d+x\d+bb\.', '/1400x1400bb.', raw_url)
                med_res = re.sub(r'/\d+x\d+bb\.', '/1000x1000bb.', raw_url)
                item_title = str(
                    item.get('collectionName')
                    or item.get('trackName')
                    or clean_album
                )
                item_artist = str(item.get('artistName') or clean_artist)
                add_candidate('itunes', hi_res, 1400, item_title, item_artist)
                add_candidate('itunes', med_res, 1000, item_title, item_artist)
        except Exception:
            logger.opt(exception=True).debug(
                'iTunes cover options search failed'
            )

    # 2. Deezer Search (offers cover_xl 1000x1000 and cover_big 500x500)
    try:
        from . import deezer

        deezer_rows = (
            deezer.search_albums_by(clean_artist, clean_album)
            if clean_artist and clean_album
            else []
        )
        if not deezer_rows and search_query:
            q = f'{clean_artist} {clean_album}'.strip() or search_query
            try:
                deezer_data = (
                    deezer._get_json(
                        f'{deezer._FINDER_SEARCH_URL}/album', q=q, limit=5
                    ).get('data')
                    or []
                )
                deezer_rows = deezer._map_rows(
                    deezer_data, deezer._finder_album_row
                )
            except Exception:
                deezer_rows = []

        for row in deezer_rows:
            c_url = str(row.get('cover_url') or '')
            if c_url:
                add_candidate(
                    'deezer',
                    c_url,
                    1000,
                    str(row.get('title') or clean_album),
                    str(row.get('artist') or clean_artist),
                )
    except Exception:
        logger.opt(exception=True).debug('Deezer cover options search failed')

    # 3. Spotify Search (offers 640x640)
    try:
        sp_results = spotify.search(search_query)
        for alb in sp_results.get('albums') or []:
            sp_url = spotify_upgrade_url(str(alb.get('cover_url') or ''))
            if sp_url:
                add_candidate(
                    'spotify',
                    sp_url,
                    640,
                    str(alb.get('name') or alb.get('title') or clean_album),
                    str(alb.get('artist') or clean_artist),
                )
    except Exception:
        logger.opt(exception=True).debug('Spotify cover options search failed')

    # 4. YouTube Music Search
    try:
        ytm_songs = providers.search_songs(search_query, limit=3)
        for s in ytm_songs:
            ytm_url = str(s.get('cover_url') or '')
            if ytm_url:
                upscaled = re.sub(r'=w\d+-h\d+', '=w800-h800', ytm_url)
                add_candidate(
                    'youtube-music',
                    upscaled,
                    800,
                    str(s.get('name') or clean_album),
                    str((s.get('artists') or [clean_artist])[0]),
                )
    except Exception:
        logger.opt(exception=True).debug(
            'YouTube Music cover options search failed'
        )

    # Sort candidates by resolution descending (largest first)
    candidates.sort(key=lambda c: int(c.get('width') or 0), reverse=True)
    return candidates
