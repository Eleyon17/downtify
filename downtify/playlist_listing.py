"""The downloaded playlists, as ``GET /playlists`` lists them (and, by
track id, ``GET /api/v1/playlists``)."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Optional

from . import m3u
from .library_paths import library_stored_path
from .library_paths_cache import get_cached_playlists, peek_cached_path_pairs
from .likes import is_liked_playlist


def list_library_playlists(
    download_dir: Path,
    slskd_dir: Optional[Path] = None,
    extra_dirs: Optional[Sequence[Path]] = None,
    *,
    stale_ok: bool = False,
) -> list[dict[str, Any]]:
    """Every playlist on disk, from the ``.m3u`` files Downtify writes for
    playlist/album downloads and Playlist Monitor sweeps (see
    ``downtify/m3u.py``), plus playlists the user created in the Library.

    Each M3U file on disk is one playlist, regardless of whether
    *Organize by artist/album* put its tracks in a per-playlist folder or
    scattered them into artist/album folders — the M3U is the one place
    that still records "these tracks belong together, in this order"
    either way. Single tracks and albums downloaded without an M3U
    aren't playlists and don't show up here. The liked songs playlist
    comes first, then the rest by name.
    """

    extras = tuple(extra_dirs or ())
    return get_cached_playlists(
        Path(download_dir),
        slskd_dir,
        extras,
        lambda: _scan_library_playlists(Path(download_dir), slskd_dir, extras),
        stale_ok=stale_ok,
    )


def _known_library_files(
    download_dir: Path,
    slskd_dir: Optional[Path],
    extra_dirs: tuple[Path, ...],
) -> Optional[set[str]]:
    from .library_catalog import LibraryContext  # noqa: PLC0415

    ctx = LibraryContext(
        download_dir=download_dir,
        slskd_dir=slskd_dir,
        extra_dirs=extra_dirs,
    )
    pairs = peek_cached_path_pairs(ctx)
    if pairs is None:
        return None
    return {stored for stored, _resolved in pairs}


def _scan_library_playlists(
    download_dir: Path,
    slskd_dir: Optional[Path],
    extra_dirs: tuple[Path, ...],
) -> list[dict[str, Any]]:
    base = Path(download_dir).resolve()
    if not base.exists():
        return []
    known = _known_library_files(download_dir, slskd_dir, extra_dirs)
    known_by_stem: dict[str, str] = {}
    known_by_basename: dict[str, str] = {}
    if known is not None:
        for k in known:
            kn = k.replace('\\', '/')
            stem, _ = os.path.splitext(kn)
            known_by_stem[stem] = kn
            base_stem, _ = os.path.splitext(os.path.basename(kn))
            if base_stem not in known_by_basename:
                known_by_basename[base_stem] = kn

    playlists: list[dict[str, Any]] = []
    for m3u_path in m3u.iter_m3u_files(base):
        manual = m3u.is_manual_m3u(m3u_path)
        raw_tracks = m3u.read_m3u_tracks(
            m3u_path,
            base,
            slskd_dir,
            extra_dirs,
            keep_missing=True,
        )
        tracks: list[str] = []
        for stored in raw_tracks:
            stored_norm = stored.replace('\\', '/')
            if known is None or stored_norm in known:
                tracks.append(stored_norm)
                continue
            # Try matching by stem (e.g. format upgrade .mp3 -> .flac)
            stem, _ = os.path.splitext(stored_norm)
            if stem in known_by_stem:
                tracks.append(known_by_stem[stem])
                continue
            # Try matching by basename stem (e.g. reorganized into artist/album folder)
            base_stem, _ = os.path.splitext(os.path.basename(stored_norm))
            if base_stem in known_by_basename:
                tracks.append(known_by_basename[base_stem])
                continue
            tracks.append(stored_norm)

        if not tracks and not manual:
            continue

        # Retroactive playlist healing: check if the playlist's folder on disk
        # contains downloaded audio tracks that were dropped or missing from the M3U.
        audio_extensions = ('.flac', '.mp3', '.m4a', '.opus', '.ogg', '.wav', '.aac')
        existing_stems = {
            os.path.splitext(os.path.basename(t.replace('\\', '/')))[0].casefold()
            for t in tracks
        }
        existing_names = {
            os.path.basename(t.replace('\\', '/')).casefold() for t in tracks
        }
        recovered: list[str] = []

        safe_name = m3u.sanitize_playlist_name(m3u_path.stem)
        playlist_dirs = set()
        if m3u_path.parent != base and m3u_path.parent != base / 'Playlists':
            playlist_dirs.add(m3u_path.parent)
        cand_pdir = base / safe_name
        if cand_pdir.is_dir():
            playlist_dirs.add(cand_pdir)
        cand_pdir_raw = base / m3u_path.stem
        if cand_pdir_raw.is_dir():
            playlist_dirs.add(cand_pdir_raw)

        for pdir in playlist_dirs:
            try:
                for f in sorted(pdir.iterdir()):
                    if f.is_file() and f.suffix.lower() in audio_extensions:
                        f_stem = f.stem.casefold()
                        f_name = f.name.casefold()
                        if f_stem not in existing_stems and f_name not in existing_names:
                            cand_stored = library_stored_path(
                                f, base, slskd_dir, extra_dirs
                            )
                            if cand_stored:
                                recovered.append(cand_stored)
                                existing_stems.add(f_stem)
                                existing_names.add(f_name)
            except OSError:
                pass

        if recovered:
            tracks.extend(recovered)
            try:
                m3u_entries = [{'filename': t} for t in tracks]
                if m3u_path.parent == base / 'Playlists':
                    pl_sub = None
                elif m3u_path.parent != base:
                    pl_sub = m3u_path.parent.name
                else:
                    pl_sub = safe_name
                m3u.write_m3u(
                    base,
                    m3u_path.stem,
                    m3u_entries,
                    playlist_subdir=pl_sub,
                    slskd_dir=slskd_dir,
                    extra_dirs=extra_dirs,
                    manual=manual,
                    allow_empty=True,
                )
            except Exception:
                pass

        # The sidecar artwork save_playlist_cover writes beside the M3U,
        # when the playlist has one of its own.
        cover = m3u_path.with_suffix('.jpg')
        playlists.append({
            'name': m3u_path.stem,
            'files': tracks,
            'count': len(tracks),
            'added': int(m3u_path.stat().st_mtime),
            'cover': (
                library_stored_path(cover, base, slskd_dir, extra_dirs)
                if cover.is_file()
                else ''
            ),
            # The playlist of hearted songs, not a downloaded one.
            'liked': is_liked_playlist(m3u_path.stem),
            'manual': manual,
            '_m3u_path': m3u_path,
        })

    # Deduplicate playlists with the same casefolded name (e.g. if both
    # Playlists/<name>.m3u and <name>/<name>.m3u were written), merging tracks.
    by_key: dict[str, dict[str, Any]] = {}
    for pl in playlists:
        m3u_file: Optional[Path] = pl.pop('_m3u_path', None)
        key = str(pl['name']).strip().casefold()
        if key not in by_key:
            pl['_m3u_path'] = m3u_file
            by_key[key] = pl
            continue
        existing_pl = by_key[key]
        existing_m3u: Optional[Path] = existing_pl.get('_m3u_path')
        merged_files: list[str] = list(existing_pl['files'])
        seen_stems = {
            os.path.splitext(os.path.basename(f.replace('\\', '/')))[0].casefold()
            for f in merged_files
        }
        seen_paths = {f.replace('\\', '/') for f in merged_files}
        for f in pl['files']:
            fn = f.replace('\\', '/')
            st = os.path.splitext(os.path.basename(fn))[0].casefold()
            if fn not in seen_paths and st not in seen_stems:
                merged_files.append(fn)
                seen_paths.add(fn)
                seen_stems.add(st)
        existing_pl['files'] = merged_files
        existing_pl['count'] = len(merged_files)
        existing_pl['added'] = max(existing_pl['added'], pl['added'])
        if not existing_pl['cover'] and pl['cover']:
            existing_pl['cover'] = pl['cover']
        existing_pl['manual'] = existing_pl['manual'] or pl['manual']
        # Keep the M3U that originally had more tracks and remove the duplicate
        if m3u_file is not None and existing_m3u is not None and m3u_file != existing_m3u:
            try:
                m3u_file.unlink(missing_ok=True)
            except OSError:
                pass
            try:
                pl_sub = (
                    None
                    if existing_m3u.parent == base / 'Playlists'
                    else (
                        existing_m3u.parent.name
                        if existing_m3u.parent != base
                        else m3u.sanitize_playlist_name(existing_pl['name'])
                    )
                )
                m3u.write_m3u(
                    base,
                    existing_pl['name'],
                    [{'filename': f} for f in merged_files],
                    playlist_subdir=pl_sub,
                    slskd_dir=slskd_dir,
                    extra_dirs=extra_dirs,
                    manual=existing_pl['manual'],
                    allow_empty=True,
                )
            except Exception:
                pass

    deduped = []
    for pl in by_key.values():
        pl.pop('_m3u_path', None)
        deduped.append(pl)
    deduped.sort(key=lambda p: (not p['liked'], p['name'].casefold()))
    return deduped
