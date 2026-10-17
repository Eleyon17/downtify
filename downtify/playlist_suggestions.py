"""Playlist Suggestions: songs similar in tone or vibe to a playlist.

Uses YouTube Music's radio mix across representative seed tracks from the playlist
to generate recommendations matching the mood, genre, and sound.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from . import likes, m3u, providers
from .library_catalog import LibraryContext, resolve_library_file
from .library_metadata import read_audio_metadata, _fallback_title_from_filename


def _normalize(text: str) -> str:
    if not text:
        return ''
    t = str(text).lower()
    t = re.sub(
        r'[\(\[][^\)\]]*(feat|ft|remaster|version|edition|official|mix|deluxe)[^\)\]]*[\)\]]',
        ' ',
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(
        r'-\s*(\d{4}\s+)?(remaster|remastered|deluxe|bonus|version).*$',
        ' ',
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(
        r'\b(feat|ft|remaster|remastered|deluxe|version)\b', ' ', t, flags=re.IGNORECASE
    )
    t = re.sub(r'[^\w\s]', '', t)
    return re.sub(r'\s+', ' ', t).strip()


def resolve_playlist_tracks(
    name: str,
    download_dir: Path,
    ctx: Optional[LibraryContext] = None,
    catalog: Optional[Any] = None,
    likes_store: Optional[Any] = None,
) -> list[tuple[str, str]]:
    """Return a list of (artist, title) for all tracks currently in the playlist."""
    tracks: list[tuple[str, str]] = []

    # 1. Liked songs playlist
    if likes.is_liked_playlist(name) and likes_store is not None:
        try:
            paths = likes_store.paths(None)
            for file_path in paths:
                full = (
                    resolve_library_file(file_path, ctx)
                    if ctx
                    else (download_dir / file_path)
                )
                if full and full.is_file():
                    meta = read_audio_metadata(full)
                    title = meta.get('title')
                    artist = meta.get('artist')
                    if not title or not artist:
                        fb_title, fb_artist = _fallback_title_from_filename(full)
                        title = title or fb_title
                        artist = artist or fb_artist
                    if title:
                        tracks.append((str(artist or ''), str(title)))
        except Exception:
            logger.opt(exception=True).debug(
                'Failed resolving liked tracks for suggestions'
            )

    # 2. M3U on disk (manual or imported)
    if not tracks and download_dir.exists():
        m3u_path = m3u.find_m3u_for_name(download_dir, name)
        if m3u_path:
            try:
                slskd_dir = ctx.slskd_dir if ctx else None
                extra_dirs = ctx.extra_dirs if ctx else ()
                files = m3u.read_m3u_tracks(
                    m3u_path,
                    download_dir,
                    slskd_dir=slskd_dir,
                    extra_dirs=extra_dirs,
                    keep_missing=True,
                )
                for file_path in files:
                    full = (
                        resolve_library_file(file_path, ctx)
                        if ctx
                        else (download_dir / file_path)
                    )
                    if full and full.is_file():
                        meta = read_audio_metadata(full)
                        title = meta.get('title')
                        artist = meta.get('artist')
                        if not title or not artist:
                            fb_title, fb_artist = _fallback_title_from_filename(full)
                            title = title or fb_title
                            artist = artist or fb_artist
                        if title:
                            tracks.append((str(artist or ''), str(title)))
                    else:
                        # Fallback parsing directly from the filename
                        stem_path = Path(file_path)
                        fb_title, fb_artist = _fallback_title_from_filename(stem_path)
                        if fb_title:
                            tracks.append((fb_artist, fb_title))
            except Exception:
                logger.opt(exception=True).debug(
                    'Failed reading M3U tracks for suggestions {!r}', name
                )

    # 3. Catalog fallback
    if not tracks and catalog is not None:
        try:
            for row in catalog.list_tracks(name):
                t = str(row.get('title') or '').strip()
                a = str(row.get('artist') or '').strip()
                if t:
                    tracks.append((a, t))
        except Exception:
            logger.opt(exception=True).debug(
                'Failed listing catalog tracks for {!r}', name
            )

    return tracks


def _sample_seed_tracks(
    tracks: list[tuple[str, str]], max_seeds: int = 4
) -> list[tuple[str, str]]:
    """Sample diverse representative seed tracks across the playlist."""
    if not tracks:
        return []
    if len(tracks) <= max_seeds:
        return list(tracks)

    # Pick evenly spaced tracks across the list to preserve playlist variety
    step = len(tracks) / max_seeds
    indices = [int(i * step) for i in range(max_seeds)]
    seen_indices = set()
    seeds: list[tuple[str, str]] = []
    for idx in indices:
        if idx not in seen_indices and idx < len(tracks):
            seen_indices.add(idx)
            seeds.append(tracks[idx])
    return seeds


def get_playlist_suggestions(
    name: str,
    download_dir: Path,
    *,
    limit: int = 20,
    dismissed: Optional[list[str]] = None,
    seed_tracks: Optional[list[dict[str, str]]] = None,
    ctx: Optional[LibraryContext] = None,
    catalog: Optional[Any] = None,
    likes_store: Optional[Any] = None,
    track_index: Optional[Any] = None,
) -> dict[str, Any]:
    """Generate songs similar in tone or vibe to the playlist named *name*.

    Seeds from representative tracks in the playlist (or *seed_tracks* if provided).
    Returns a dictionary with ``playlist`` and ``suggestions`` (list of song dicts).
    """
    dismissed_set = {
        str(d).strip().casefold()
        for d in (dismissed or [])
        if str(d).strip()
    }

    # Extract playlist tracks
    tracks: list[tuple[str, str]] = []
    if seed_tracks:
        for s in seed_tracks:
            a = str(s.get('artist') or '').strip()
            t = str(s.get('title') or s.get('name') or '').strip()
            if t:
                tracks.append((a, t))
    if not tracks:
        tracks = resolve_playlist_tracks(
            name,
            download_dir,
            ctx=ctx,
            catalog=catalog,
            likes_store=likes_store,
        )

    # Track identities already in the playlist (for exclusion)
    existing_normalized: set[tuple[str, str]] = set()
    existing_titles: set[str] = set()
    for a, t in tracks:
        norm_a = _normalize(a)
        norm_t = _normalize(t)
        if norm_t:
            existing_normalized.add((norm_a, norm_t))
            existing_titles.add(norm_t)

    # Select seed tracks
    seeds = _sample_seed_tracks(tracks, max_seeds=4)

    # Collect similar song lists per seed
    candidates_by_seed: list[list[dict[str, Any]]] = []

    if seeds:
        for s_artist, s_title in seeds:
            try:
                res = providers.youtube_similar_tracks(
                    s_artist, s_title, limit=15
                )
                items = res.get('tracks') or []
                if items:
                    candidates_by_seed.append(items)
            except Exception:
                logger.opt(exception=True).debug(
                    'Failed getting similar tracks for seed {} - {}',
                    s_artist,
                    s_title,
                )

    # If playlist was empty or all seeds returned nothing, try using the playlist name as seed
    if not candidates_by_seed and name:
        clean_name = re.sub(r'[\(\[].*?[\)\]]', '', name).strip()
        try:
            res = providers.youtube_similar_tracks(
                '', clean_name or name, limit=20
            )
            items = res.get('tracks') or []
            if items:
                candidates_by_seed.append(items)
        except Exception:
            pass

        # Also try searching songs by playlist title if still empty
        if not candidates_by_seed:
            try:
                search_hits = providers.search_songs(clean_name or name, limit=15)
                if search_hits:
                    candidates_by_seed.append(search_hits)
            except Exception:
                pass

    # Interleave results across seeds for variety
    seen_ids: set[str] = set()
    seen_normalized: set[tuple[str, str]] = set()
    suggestions: list[dict[str, Any]] = []

    max_depth = max((len(c) for c in candidates_by_seed), default=0)
    for depth in range(max_depth):
        for candidate_list in candidates_by_seed:
            if depth >= len(candidate_list):
                continue
            cand = candidate_list[depth]
            sid = str(cand.get('song_id') or cand.get('video_id') or '').strip()
            c_name = str(cand.get('name') or cand.get('title') or '').strip()
            artists_list = cand.get('artists') or (
                [cand['artist']] if cand.get('artist') else []
            )
            c_artist = (
                str(artists_list[0] if artists_list else '').strip()
            )

            if not c_name:
                continue

            # Check dismissed
            if sid and sid.casefold() in dismissed_set:
                continue
            norm_t = _normalize(c_name)
            norm_a = _normalize(c_artist)
            if norm_t and norm_t in dismissed_set:
                continue

            # Check already in playlist
            if (norm_a, norm_t) in existing_normalized or norm_t in existing_titles:
                continue

            # Deduplicate within suggestions
            if sid and sid in seen_ids:
                continue
            if (norm_a, norm_t) in seen_normalized:
                continue

            if sid:
                seen_ids.add(sid)
            seen_normalized.add((norm_a, norm_t))

            # Format song row
            song_entry = {
                'song_id': sid,
                'name': c_name,
                'artist': c_artist,
                'artists': artists_list or [c_artist],
                'album_name': str(cand.get('album_name') or cand.get('album') or '').strip(),
                'duration': int(cand.get('duration') or cand.get('duration_seconds') or 0),
                'cover_url': str(cand.get('cover_url') or cand.get('cover') or ''),
                'url': str(
                    cand.get('url')
                    or (f'https://music.youtube.com/watch?v={sid}' if sid else '')
                ),
                'in_library': False,
            }

            # Check if this track is already in the local library
            local_file: Optional[str] = None
            if track_index is not None:
                try:
                    local_file = track_index.lookup_song(cand) or (
                        track_index.lookup(sid) if sid else None
                    )
                except Exception:
                    pass
            if local_file:
                song_entry['in_library'] = True
                song_entry['file'] = local_file

            suggestions.append(song_entry)
            if len(suggestions) >= limit:
                break
        if len(suggestions) >= limit:
            break

    return {
        'playlist': name,
        'suggestions': suggestions,
    }
