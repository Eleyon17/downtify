"""Detect library file moves and refresh playlist paths + M3U / Navidrome."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import httpx
from loguru import logger

from . import m3u
from .downloader import Downloader
from .library_cache_keys import file_content_key
from .library_catalog import (
    AUDIO_EXTENSIONS,
    PODCASTS_DIRNAME,
    LibraryContext,
    library_context_from_state,
)
from .library_delete import (
    TagMismatchDeleteContext,
    delete_if_spotify_tag_mismatch,
)
from .library_paths import library_stored_path, locate_library_file
from .library_paths_cache import invalidate_library_paths_cache
from .navidrome import (
    _effective_navidrome_settings,
    enrich_song_from_library_file,
    remove_navidrome_playlist_by_name,
    sync_playlist_to_navidrome,
)
from .playlist_catalog import PlaylistCatalog
from .playlist_spotify_cache import PlaylistSpotifyCache, fetch_playlist_tracks
from .track_index import TrackIndex, normalize_spotify_track_id
from .track_tag_match import spotify_aligns_with_file_tags

if TYPE_CHECKING:
    from .monitor import PlaylistMonitorDB


def playlist_refresh_enabled(settings: dict[str, Any]) -> tuple[bool, bool]:
    """Return ``(generate_m3u, sync_navidrome)`` from current settings."""

    generate_m3u = settings.get('generate_m3u', True) is not False
    sync_navidrome = settings.get(
        'sync_navidrome', True
    ) is not False and _effective_navidrome_settings(settings).get('enabled')
    return generate_m3u, sync_navidrome


def build_disk_content_index(ctx: LibraryContext) -> dict[str, str]:
    """Scan library trees: ``content_key`` → current stored relative path."""

    index: dict[str, str] = {}

    def _add(file_path: Path) -> None:
        if not file_path.is_file():
            return
        if file_path.suffix.lower() not in AUDIO_EXTENSIONS:
            return
        try:
            file_path.relative_to(ctx.download_dir / PODCASTS_DIRNAME)
            return  # podcast episode: not part of the music library
        except ValueError:
            pass
        ck = file_content_key(file_path)
        if not ck:
            return
        stored = library_stored_path(
            file_path, ctx.download_dir, ctx.slskd_dir, ctx.extra_dirs
        )
        index[ck] = stored

    if ctx.download_dir.is_dir():
        for path in ctx.download_dir.rglob('*'):
            _add(path)

    if ctx.slskd_dir is not None and ctx.slskd_dir.is_dir():
        try:
            same = ctx.slskd_dir.resolve() == ctx.download_dir.resolve()
        except OSError:
            same = False
        if not same:
            for path in ctx.slskd_dir.rglob('*'):
                _add(path)

    for extra in ctx.extra_dirs:
        if not extra.is_dir():
            continue
        try:
            extra_resolved = extra.resolve()
        except OSError:
            extra_resolved = extra
        try:
            download_resolved = ctx.download_dir.resolve()
        except OSError:
            download_resolved = ctx.download_dir
        if extra_resolved == download_resolved:
            continue
        for path in extra.rglob('*'):
            _add(path)

    return index


def reconcile_library_paths(
    ctx: LibraryContext,
    *,
    track_index: Optional[TrackIndex] = None,
    playlist_catalog: Optional[PlaylistCatalog] = None,
    monitor_db: Optional['PlaylistMonitorDB'] = None,
) -> tuple[int, set[str]]:
    """Update stored paths when files moved but ``content_key`` is unchanged.

    Returns ``(paths_updated, affected_playlist_names)``.
    """

    disk = build_disk_content_index(ctx)
    if not disk:
        return 0, set()

    updated = 0
    affected: set[str] = set()

    if track_index is not None:
        for row in track_index.all_rows():
            ck = str(row.get('content_key') or '').strip()
            old_path = str(row.get('filename') or '').strip()
            tid = str(row.get('spotify_track_id') or '').strip()
            if not ck or not tid:
                continue
            new_path = disk.get(ck)
            if not new_path or new_path == old_path:
                continue
            if locate_library_file(
                old_path, ctx.download_dir, ctx.slskd_dir, ctx.extra_dirs
            ):
                continue
            if track_index.update_filename(tid, new_path, content_key=ck):
                updated += 1
                if monitor_db is not None:
                    affected |= monitor_db.update_filename_for_spotify(
                        tid, new_path
                    )

    if playlist_catalog is not None:
        for row in playlist_catalog.all_track_rows():
            ck = str(row.get('content_key') or '').strip()
            old_path = str(row.get('filename') or '').strip()
            if not ck:
                continue
            new_path = disk.get(ck)
            if not new_path or new_path == old_path:
                continue
            if locate_library_file(
                old_path, ctx.download_dir, ctx.slskd_dir, ctx.extra_dirs
            ):
                continue
            names = playlist_catalog.update_filename_by_content_key(
                ck, new_path
            )
            if names:
                updated += 1
                affected.update(names)

    if updated:
        logger.info(
            'library reconcile: updated {} path(s), {} playlist(s) affected',
            updated,
            len(affected),
        )
    return updated, affected


def prune_stale_and_backfill(
    ctx: LibraryContext,
    *,
    track_index: Optional[TrackIndex] = None,
    playlist_catalog: Optional[PlaylistCatalog] = None,
    navidrome_index: Optional[Any] = None,
) -> tuple[int, int, set[str]]:
    """Remove DB rows for missing files; fill missing ``content_key`` values."""

    pruned = 0
    backfilled = 0
    affected: set[str] = set()

    if playlist_catalog is not None:
        for row in list(playlist_catalog.all_track_rows()):
            old_path = str(row.get('filename') or '').strip()
            pl_name = str(row.get('playlist_name') or '').strip()
            tid = str(row.get('track_spotify_id') or '').strip()
            if not old_path or not pl_name or not tid:
                continue
            full = locate_library_file(
                old_path, ctx.download_dir, ctx.slskd_dir, ctx.extra_dirs
            )
            if full is None:
                # Before removing, check if track_index or library stem knows this track
                alt_stored = track_index.filename_for(tid) if track_index is not None else None
                if alt_stored:
                    alt_full = locate_library_file(
                        alt_stored, ctx.download_dir, ctx.slskd_dir, ctx.extra_dirs
                    )
                    if alt_full is not None:
                        playlist_catalog.update_filename(old_path, alt_stored)
                        continue
                old_stem = Path(old_path).stem
                found_by_stem = None
                for ext in ('.flac', '.mp3', '.m4a', '.opus', '.ogg', '.wav', '.aac'):
                    test_alt = ctx.download_dir / f'{old_stem}{ext}'
                    if test_alt.is_file():
                        found_by_stem = library_stored_path(test_alt, ctx.download_dir, ctx.slskd_dir, ctx.extra_dirs) or f'{old_stem}{ext}'
                        break
                if found_by_stem:
                    playlist_catalog.update_filename(old_path, found_by_stem)
                    continue

                if playlist_catalog.remove_track(pl_name, tid):
                    pruned += 1
                    affected.add(pl_name)
                if navidrome_index is not None:
                    navidrome_index.forget_filename(old_path)
                continue

            canonical = library_stored_path(
                full, ctx.download_dir, ctx.slskd_dir, ctx.extra_dirs
            ) or old_path
            if canonical and canonical != old_path:
                playlist_catalog.update_filename(old_path, canonical)

            ck = str(row.get('content_key') or '').strip()
            if not ck:
                new_ck = file_content_key(full)
                if new_ck:
                    playlist_catalog.set_content_key(pl_name, tid, new_ck)
                    backfilled += 1

    if track_index is not None:
        for row in list(track_index.all_rows()):
            old_path = str(row.get('filename') or '').strip()
            tid = str(row.get('spotify_track_id') or '').strip()
            if not old_path or not tid:
                continue
            full = locate_library_file(
                old_path, ctx.download_dir, ctx.slskd_dir, ctx.extra_dirs
            )
            if full is None:
                old_stem = Path(old_path).stem
                found_by_stem = None
                for ext in ('.flac', '.mp3', '.m4a', '.opus', '.ogg', '.wav', '.aac'):
                    test_alt = ctx.download_dir / f'{old_stem}{ext}'
                    if test_alt.is_file():
                        found_by_stem = library_stored_path(test_alt, ctx.download_dir, ctx.slskd_dir, ctx.extra_dirs) or f'{old_stem}{ext}'
                        break
                if found_by_stem:
                    track_index.remove_by_filename(old_path)
                    track_index.register(tid, found_by_stem)
                    continue
                if track_index.remove_by_filename(old_path):
                    pruned += 1
                if navidrome_index is not None:
                    navidrome_index.forget_filename(old_path)
                continue

            canonical = library_stored_path(
                full, ctx.download_dir, ctx.slskd_dir, ctx.extra_dirs
            ) or old_path
            if canonical and canonical != old_path:
                track_index.remove_by_filename(old_path)
                track_index.register(tid, canonical)

            ck = str(row.get('content_key') or '').strip()
            if not ck:
                new_ck = file_content_key(full)
                if new_ck and track_index.set_content_key(tid, new_ck):
                    backfilled += 1

    if pruned or backfilled:
        logger.info(
            'library reconcile: pruned {} stale row(s), backfilled {} content_key(s)',
            pruned,
            backfilled,
        )
    return pruned, backfilled, affected


def refresh_playlists_after_moves(  # noqa: PLR0914
    playlist_names: set[str],
    *,
    settings: dict[str, Any],
    downloader: Downloader,
    playlist_catalog: PlaylistCatalog,
    track_index: Optional[TrackIndex] = None,
    monitor_db: Optional['PlaylistMonitorDB'] = None,
    navidrome_index: Optional[Any] = None,
    navidrome_scan: bool = False,
    playlist_spotify_cache: Optional[PlaylistSpotifyCache] = None,
    cover_cache: Optional[Any] = None,
    metadata_cache: Optional[Any] = None,
    delete_tag_mismatches: bool = True,
) -> None:
    """Regenerate local M3U and optionally Navidrome for *playlist_names*.

    Library scan is off by default here (deletes / reconcile). New downloads
    call ``sync_playlist_to_navidrome`` directly with scan from settings.
    """

    if not playlist_names:
        return

    generate_m3u, sync_navidrome = playlist_refresh_enabled(settings)
    if not generate_m3u and not sync_navidrome:
        logger.info(
            'library reconcile: skip playlist refresh (M3U and Navidrome sync off)'
        )
        return

    logger.info(
        'library reconcile: refreshing {} playlist(s) after library change: {}',
        len(playlist_names),
        ', '.join(sorted(playlist_names)[:8])
        + ('; ...' if len(playlist_names) > 8 else ''),
    )

    download_dir = Path(downloader.download_dir)
    slskd_dir = (
        Path(str(settings.get('slskd', {}).get('source_dir') or ''))
        if isinstance(settings.get('slskd'), dict)
        and settings.get('slskd', {}).get('source_dir')
        else None
    )
    organize = bool(
        settings.get('organize_by_artist', False)
        or settings.get('organize_by_album', False)
    )
    mismatch_delete: Optional[TagMismatchDeleteContext] = None
    if delete_tag_mismatches:
        mismatch_delete = TagMismatchDeleteContext(
            ctx=library_context_from_state(
                download_dir,
                settings,
                track_index=track_index,
                metadata_cache=metadata_cache,
                playlist_catalog=playlist_catalog,
            ),
            cover_cache=cover_cache,
            metadata_cache=metadata_cache,
            playlist_catalog=playlist_catalog,
            track_index=track_index,
            navidrome_index=navidrome_index,
        )

    for name in sorted(playlist_names):
        catalog_rows = playlist_catalog.list_tracks(name)
        if not catalog_rows:
            if sync_navidrome:
                try:
                    remove_navidrome_playlist_by_name(name, settings)
                except Exception:
                    logger.exception(
                        'library reconcile: Navidrome remove failed for {!r}',
                        name,
                    )
            continue

        spotify_tracks: list[dict[str, Any]] = []
        spotify_id = playlist_catalog.spotify_id_for_playlist(name)
        if spotify_id:
            try:
                _pl_name, spotify_tracks = fetch_playlist_tracks(
                    spotify_id,
                    cache=playlist_spotify_cache,
                )
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                logger.warning(
                    'Playlist refresh: Spotify embed HTTP {} for {!r} '
                    '(id={}); using catalog metadata only',
                    status,
                    name,
                    spotify_id,
                )
                spotify_tracks = []
            except Exception:
                logger.opt(exception=True).warning(
                    'Playlist refresh: Spotify fetch failed for {!r}', name
                )
                spotify_tracks = []

        by_id = {
            normalize_spotify_track_id(t): t
            for t in spotify_tracks
            if normalize_spotify_track_id(t)
        }

        catalog_tids = {row['track_spotify_id'] for row in catalog_rows}
        # Retroactive recovery: check if any missing tracks from spotify_tracks are in the library
        for tid, meta in by_id.items():
            if tid in catalog_tids:
                continue
            stored_file = track_index.filename_for(tid) if track_index is not None else None
            if stored_file:
                found_full = locate_library_file(stored_file, download_dir, slskd_dir)
                if found_full is not None:
                    actual = library_stored_path(found_full, download_dir, slskd_dir) or stored_file
                    playlist_catalog.upsert_track(name, meta, actual, found_full)
                    catalog_rows.append({
                        'playlist_name': name,
                        'track_spotify_id': tid,
                        'filename': actual,
                        'track_order': len(catalog_rows),
                    })
                    catalog_tids.add(tid)

        if monitor_db is not None:
            for mon_pl in monitor_db.list_playlists():
                if mon_pl.name.strip().casefold() == name.strip().casefold() or (mon_pl.spotify_id and mon_pl.spotify_id == spotify_id):
                    for d_track in monitor_db.list_downloaded_tracks(mon_pl.id):
                        dt_tid = str(d_track.get('track_spotify_id') or '').strip()
                        dt_file = str(d_track.get('filename') or '').strip()
                        if dt_tid and dt_tid not in catalog_tids:
                            full_cand = locate_library_file(dt_file, download_dir, slskd_dir)
                            if full_cand is not None:
                                actual_cand = library_stored_path(full_cand, download_dir, slskd_dir) or dt_file
                                meta = by_id.get(dt_tid) or {'song_id': dt_tid}
                                playlist_catalog.upsert_track(name, meta, actual_cand, full_cand)
                                catalog_rows.append({
                                    'playlist_name': name,
                                    'track_spotify_id': dt_tid,
                                    'filename': actual_cand,
                                    'track_order': len(catalog_rows),
                                })
                                catalog_tids.add(dt_tid)

        entries: list[dict[str, Any]] = []
        songs_for_nav: list[dict[str, Any]] = []
        for row in catalog_rows:
            tid = row['track_spotify_id']
            filename = row['filename']
            full = locate_library_file(filename, download_dir, slskd_dir)
            if full is None:
                continue
            actual_stored = library_stored_path(full, download_dir, slskd_dir) or filename
            if actual_stored != filename:
                playlist_catalog.update_filename(filename, actual_stored)
                filename = actual_stored

            meta = by_id.get(tid) or {'song_id': tid}
            song = dict(meta)
            song['filename'] = filename
            song = enrich_song_from_library_file(song, download_dir, slskd_dir)
            if not spotify_aligns_with_file_tags(song):
                if (
                    mismatch_delete is not None
                    and delete_if_spotify_tag_mismatch(
                        song,
                        mismatch_delete,
                        playlist_name=name,
                    )
                ):
                    continue
            entries.append({
                'filename': filename,
                'title': song.get('name') or '',
                'artist': ', '.join(song.get('artists') or []),
                'duration': song.get('duration') or 0,
            })
            songs_for_nav.append(song)

        if generate_m3u and entries:
            pl_subdir = None if organize else m3u.sanitize_playlist_name(name)
            try:
                m3u.write_m3u(
                    download_dir,
                    name,
                    entries,
                    playlist_subdir=pl_subdir,
                    slskd_dir=slskd_dir,
                )
                logger.info(
                    'library reconcile: rewrote M3U for playlist {!r} ({} tracks)',
                    name,
                    len(entries),
                )
            except Exception:
                logger.exception(
                    'library reconcile: M3U failed for playlist {!r}', name
                )

        if sync_navidrome and songs_for_nav:
            try:
                sync_playlist_to_navidrome(
                    name,
                    songs_for_nav,
                    settings,
                    navidrome_index=navidrome_index,
                    download_dir=download_dir,
                    trigger_scan=navidrome_scan,
                    delete_tag_mismatches=mismatch_delete,
                )
            except Exception:
                logger.exception(
                    'library reconcile: Navidrome sync failed for {!r}', name
                )


def reconcile_and_refresh(
    download_dir: Path,
    settings: dict[str, Any],
    downloader: Downloader,
    *,
    track_index: Optional[TrackIndex] = None,
    playlist_catalog: Optional[PlaylistCatalog] = None,
    monitor_db: Optional['PlaylistMonitorDB'] = None,
    navidrome_index: Optional[Any] = None,
    refresh_playlists: bool = True,
    playlist_spotify_cache: Optional[PlaylistSpotifyCache] = None,
    cover_cache: Optional[Any] = None,
    metadata_cache: Optional[Any] = None,
) -> dict[str, Any]:
    """Run path reconciliation and optional playlist / Navidrome refresh."""

    ctx = library_context_from_state(
        download_dir, settings, track_index=track_index
    )
    pruned, backfilled, prune_affected = prune_stale_and_backfill(
        ctx,
        track_index=track_index,
        playlist_catalog=playlist_catalog,
        navidrome_index=navidrome_index,
    )
    count, move_affected = reconcile_library_paths(
        ctx,
        track_index=track_index,
        playlist_catalog=playlist_catalog,
        monitor_db=monitor_db,
    )
    affected = prune_affected | move_affected
    generate_m3u, sync_navidrome = playlist_refresh_enabled(settings)
    did_refresh = False
    if (
        refresh_playlists
        and affected
        and playlist_catalog is not None
        and (generate_m3u or sync_navidrome)
    ):
        refresh_playlists_after_moves(
            affected,
            settings=settings,
            downloader=downloader,
            playlist_catalog=playlist_catalog,
            track_index=track_index,
            monitor_db=monitor_db,
            navidrome_index=navidrome_index,
            playlist_spotify_cache=playlist_spotify_cache,
            cover_cache=cover_cache,
            metadata_cache=metadata_cache,
        )
        did_refresh = True
    invalidate_library_paths_cache()
    if not (count or pruned or backfilled):
        logger.info(
            'library reconcile: no path updates, stale rows, or backfills '
            '(DB already matches disk, or delete was done in the Library UI)'
        )
    return {
        'paths_updated': count,
        'pruned_stale': pruned,
        'content_keys_backfilled': backfilled,
        'playlists_affected': sorted(affected),
        'refresh_m3u': did_refresh and generate_m3u,
        'refresh_navidrome': did_refresh and sync_navidrome,
    }
