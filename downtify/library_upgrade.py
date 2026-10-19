"""Scan an existing library for tracks worth improving, then improve them.

A library built up over releases carries whatever each Downtify version
could do at the time: covers at the smallest size a source offered, no
lyrics, tags missing an album or a year. Re-downloading everything to fix
that wastes the files that are already fine, so this module looks at what
is on disk and repairs only what is actually behind.

Three categories are handled, all of them writes to tags:

``artwork``
    Replace a cover smaller than the target with the largest one Spotify,
    iTunes or YouTube Music has for the track.
``lyrics``
    Fill in lyrics for tracks that have none, through the ordered
    provider list (see :mod:`downtify.lyrics`).
``metadata``
    Re-read the track from Spotify and write back album, album artist,
    release date and track number.

Audio itself is never replaced: swapping the file a user already has is
a different problem (match confidence, review of uncertain matches,
playlists and M3Us pointing at the old name) and is deliberately left
out rather than done half-way.

Every write goes to a copy beside the original, which is verified and
only then moved into place, so an interrupted or failed upgrade leaves
the existing file untouched.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger
from mutagen import File as MutagenFile

from . import cover_sources, providers, spotify
from . import lyrics as lyrics_mod
from .downloader import embed_lyrics, embed_metadata
from .providers import find_match_youtube_music_only
from .slskd_provider import download_from_slskd

_ORIG_PROVIDERS_FIND_MATCH = providers.find_match
_ORIG_FIND_MATCH_YTM_ONLY = find_match_youtube_music_only
from .library_cache_keys import file_content_key
from .library_catalog import (
    UPGRADE_STAGING_MARKER,
    LibraryContext,
    list_library_entries,
)
from .library_paths import locate_library_file
from .library_upgrade_db import (
    JOB_DONE,
    JOB_FAILED,
    JOB_SKIPPED,
    STATE_CANCELLED,
    STATE_DONE,
    STATE_PAUSED,
    STATE_READY,
    STATE_RUNNING,
    STATE_SCANNING,
    LibraryUpgradeDB,
    check_is_fresh,
)
from .lyrics import read_track_lyrics

#: The name an upgrade writes its working copy under. The extension is
#: kept because the tag writers dispatch on it, and
#: ``UPGRADE_STAGING_MARKER`` keeps the library listing from picking the
#: copy up as a track while it exists.
STAGING_TEMPLATE = '{stem}' + UPGRADE_STAGING_MARKER + '{suffix}'

CATEGORY_ARTWORK = 'artwork'
CATEGORY_LYRICS = 'lyrics'
CATEGORY_METADATA = 'metadata'
CATEGORY_FORMAT = 'format'

DEFAULT_CATEGORIES = (CATEGORY_ARTWORK, CATEGORY_LYRICS, CATEGORY_METADATA)

#: Every category a scan reports on, in the order the UI shows them.
CATEGORIES = (
    CATEGORY_ARTWORK,
    CATEGORY_LYRICS,
    CATEGORY_METADATA,
    CATEGORY_FORMAT,
)

#: How far a rewritten file's duration may drift from the original
#: before it is rejected. Tag writes don't touch audio, so this only
#: catches a truncated or corrupted copy.
_DURATION_TOLERANCE_SECONDS = 2.0

DEFAULT_ARTWORK_MIN_PX = 600
DEFAULT_RECHECK_DAYS = 30

#: Upper bound on how often progress is pushed to connected clients: a
#: run is tens of thousands of tracks long and every message costs a
#: count query plus a broadcast.
_PUBLISH_INTERVAL_SECONDS = 1.0


@dataclass(frozen=True)
class UpgradeOptions:
    """What an upgrade run should do, and how picky it should be."""

    categories: tuple[str, ...] = CATEGORIES
    artwork_min_px: int = DEFAULT_ARTWORK_MIN_PX
    artwork_source: str = cover_sources.PREFERENCE_HIGHEST
    recheck_days: int = DEFAULT_RECHECK_DAYS
    check_format: bool = False
    target_format: str = 'mp3'
    target_bitrate: int = 320
    source_targets: Optional[dict[str, list[dict[str, Any]]]] = None
    audio_providers: Optional[list[str]] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            'categories': list(self.categories),
            'artwork_min_px': self.artwork_min_px,
            'artwork_source': self.artwork_source,
            'recheck_days': self.recheck_days,
            'check_format': self.check_format,
            'target_format': self.target_format,
            'target_bitrate': self.target_bitrate,
            'source_targets': self.source_targets,
            'audio_providers': (
                list(self.audio_providers) if self.audio_providers else None
            ),
        }


def normalize_categories(raw: Any) -> tuple[str, ...]:
    """Keep the known categories from *raw*, in the canonical order."""

    if not isinstance(raw, (list, tuple)):
        return CATEGORIES
    wanted = {str(item) for item in raw}
    picked = tuple(name for name in CATEGORIES if name in wanted)
    return picked or CATEGORIES


def options_from(payload: dict[str, Any]) -> UpgradeOptions:
    """Build options from a request body, clamped to sane values."""

    def _int(key: str, default: int, low: int, high: int) -> int:
        try:
            value = int(payload.get(key, default))
        except (TypeError, ValueError):
            value = default
        return min(high, max(low, value))

    source = str(payload.get('artwork_source') or '')
    if source not in cover_sources.ARTWORK_SOURCES:
        source = cover_sources.PREFERENCE_HIGHEST
    check_format = bool(payload.get('check_format', False))
    target_format = (
        str(payload.get('target_format') or 'mp3').lower().lstrip('.')
    )
    target_bitrate = _int('target_bitrate', 320, 32, 1000)
    raw_targets = payload.get('source_targets')
    raw_providers = payload.get('audio_providers')

    return UpgradeOptions(
        categories=normalize_categories(payload.get('categories')),
        artwork_min_px=_int(
            'artwork_min_px', DEFAULT_ARTWORK_MIN_PX, 100, 3000
        ),
        artwork_source=source,
        recheck_days=_int('recheck_days', DEFAULT_RECHECK_DAYS, 0, 3650),
        check_format=check_format,
        target_format=target_format,
        target_bitrate=target_bitrate,
        source_targets=(
            raw_targets if isinstance(raw_targets, dict) else None
        ),
        audio_providers=(
            list(raw_providers)
            if isinstance(raw_providers, (list, tuple))
            else None
        ),
    )


# ── Detection ─────────────────────────────────────────────────────────
def _metadata_gaps(entry: dict[str, Any]) -> list[str]:
    """Tag fields a downloaded track should have but doesn't."""

    gaps: list[str] = []
    if not str(entry.get('album') or '').strip():
        gaps.append('album')
    if not str(entry.get('album_artist') or '').strip():
        gaps.append('album_artist')
    if not str(entry.get('year') or '').strip():
        gaps.append('year')
    if not int(entry.get('track_number') or 0):
        gaps.append('track_number')
    return gaps


def _summarize(
    jobs: list[dict[str, Any]], recently_checked: int = 0
) -> dict[str, Any]:
    """How many tracks (and bytes) each category accounts for."""

    counts = {name: 0 for name in CATEGORIES}
    sizes = {name: 0 for name in CATEGORIES}
    for job in jobs:
        for name in job.get('categories') or []:
            if name in counts:
                counts[name] += 1
                sizes[name] += int(job.get('size') or 0)
    return {
        'categories': counts,
        'category_bytes': sizes,
        'tracks': len(jobs),
        # Tracks the scan didn't even read, because every category had
        # been looked at recently enough.
        'recently_checked': int(recently_checked),
    }


def track_format_improper(
    entry: dict[str, Any],
    full_path: Path,
    *,
    target_format: str = 'mp3',
    target_bitrate_kbps: int = 320,
    source_targets: Optional[dict[str, list[dict[str, Any]]]] = None,
    audio_providers: Optional[list[str]] = None,
) -> bool:
    """Return True if the track on disk does not match the desired format or quality."""
    file_fmt = full_path.suffix.lower().lstrip('.')

    if source_targets and audio_providers:
        # Check against the top desired target across configured providers
        for prov in audio_providers:
            prov_targets = source_targets.get(prov) or []
            if prov_targets:
                first = prov_targets[0]
                eff_fmt = str(first.get('format') or 'mp3').lower().lstrip('.')
                eff_br_raw = first.get('bitrate') or 320
                try:
                    eff_br = (
                        int(eff_br_raw)
                        if str(eff_br_raw).isdigit()
                        else (0 if eff_fmt == 'flac' else 320)
                    )
                except (TypeError, ValueError):
                    eff_br = 320
                target_format = eff_fmt
                target_bitrate_kbps = eff_br
                break

    target_fmt = str(target_format or 'mp3').lower().lstrip('.')

    if file_fmt != target_fmt:
        return True

    if target_fmt == 'flac':
        return False

    bitrate_bps = int(entry.get('bitrate') or 0)
    if bitrate_bps <= 0:
        try:
            audio = MutagenFile(str(full_path))
            info = getattr(audio, 'info', None)
            bitrate_bps = int(getattr(info, 'bitrate', 0) or 0)
        except Exception:
            bitrate_bps = 0

    if bitrate_bps > 0 and target_bitrate_kbps > 0:
        file_kbps = round(bitrate_bps / 1000)
        if abs(file_kbps - target_bitrate_kbps) > 15:
            return True

    return False


def track_findings(
    entry: dict[str, Any],
    full_path: Path,
    *,
    artwork_min_px: int,
    check_format: bool = False,
    target_format: str = 'mp3',
    target_bitrate_kbps: int = 320,
    source_targets: Optional[dict[str, list[dict[str, Any]]]] = None,
    audio_providers: Optional[list[str]] = None,
) -> list[str]:
    """Which categories this track is behind on."""

    found: list[str] = []
    if int(entry.get('cover_px') or 0) < artwork_min_px:
        found.append(CATEGORY_ARTWORK)
    existing = read_track_lyrics(full_path)
    if not (existing.get('synced') or existing.get('plain')):
        found.append(CATEGORY_LYRICS)
    if _metadata_gaps(entry):
        found.append(CATEGORY_METADATA)
    if check_format and track_format_improper(
        entry,
        full_path,
        target_format=target_format,
        target_bitrate_kbps=target_bitrate_kbps,
        source_targets=source_targets,
        audio_providers=audio_providers,
    ):
        found.append(CATEGORY_FORMAT)
    return found


# ── The song a track describes ────────────────────────────────────────
def _song_from_tags(entry: dict[str, Any]) -> dict[str, Any]:
    artist = str(entry.get('artist') or '')
    artists = [part.strip() for part in artist.split(';') if part.strip()]
    return {
        'name': str(entry.get('title') or ''),
        'artists': artists or ([artist] if artist else []),
        'artist': artist,
        'album_name': str(entry.get('album') or ''),
        'album_artist': str(entry.get('album_artist') or ''),
        'year': str(entry.get('year') or ''),
        'track_number': int(entry.get('track_number') or 0),
        'duration': float(entry.get('duration') or 0.0),
    }


def _merge_remote(
    local: dict[str, Any], remote: dict[str, Any]
) -> dict[str, Any]:
    """Remote metadata wins, but never blanks something the file has."""

    merged = dict(local)
    for key, value in remote.items():
        if value in (None, '', [], 0):
            continue
        merged[key] = value
    if not merged.get('name'):
        merged['name'] = local.get('name', '')
    return merged


def song_for_track(
    entry: dict[str, Any],
    *,
    spotify_id: str = '',
    refresh_metadata: bool = False,
) -> dict[str, Any]:
    """The track as Downtify would describe it when tagging it today.

    Without ``refresh_metadata`` this is only what the file's own tags
    say, which is what an artwork- or lyrics-only upgrade writes back:
    nothing else about the file then changes.
    """

    song = _song_from_tags(entry)
    if spotify_id:
        song['song_id'] = spotify_id
    if not (refresh_metadata and spotify_id):
        return song
    try:
        # The album lookup costs two more requests; only a file with no
        # album tag of its own needs it (single-track downloads before the
        # fix that made them fetch it).
        remote = spotify.track_from_id(
            spotify_id, with_album=not song.get('album_name')
        )
    except Exception:
        logger.opt(exception=True).debug(
            'Library upgrade: Spotify lookup failed for {}', spotify_id
        )
        return song
    return _merge_remote(song, remote or {})


# ── Safe file replacement ─────────────────────────────────────────────
def _audio_length(path: Path) -> float:
    try:
        audio = MutagenFile(str(path))
    except Exception:
        return 0.0
    info = getattr(audio, 'info', None)
    return float(getattr(info, 'length', 0.0) or 0.0)


def _verify_replacement(staged: Path, expected_seconds: float) -> bool:
    """A rewritten file must still be readable audio of the same length."""

    try:
        if staged.stat().st_size <= 0:
            return False
    except OSError:
        return False
    length = _audio_length(staged)
    if length <= 0:
        return False
    if expected_seconds <= 0:
        return True
    return abs(length - expected_seconds) <= _DURATION_TOLERANCE_SECONDS


@dataclass
class _Staged:
    original: Path
    staged: Path
    mtime_ns: int
    atime_ns: int
    duration: float


def staging_path(path: Path) -> Path:
    return path.with_name(
        STAGING_TEMPLATE.format(stem=path.stem, suffix=path.suffix)
    )


def _stage(path: Path) -> _Staged:
    staged = staging_path(path)
    shutil.copy2(str(path), str(staged))
    st = path.stat()
    return _Staged(
        original=path,
        staged=staged,
        mtime_ns=int(st.st_mtime_ns),
        atime_ns=int(st.st_atime_ns),
        duration=_audio_length(path),
    )


def _commit(stage: _Staged) -> bool:
    """Swap the working copy in, or throw it away if it doesn't verify."""

    if not _verify_replacement(stage.staged, stage.duration):
        logger.warning(
            'Library upgrade: staged copy of {} failed verification',
            stage.original.name,
        )
        stage.staged.unlink(missing_ok=True)
        return False
    os.replace(str(stage.staged), str(stage.original))
    # Keep the original timestamp: the Library sorts "recently added" by
    # it, and an upgrade is not a new download.
    try:
        os.utime(str(stage.original), ns=(stage.atime_ns, stage.mtime_ns))
    except OSError:
        pass
    return True


def _discard(stage: _Staged) -> None:
    stage.staged.unlink(missing_ok=True)


# ── Applying one track ────────────────────────────────────────────────
@dataclass
class UpgradeOutcome:
    status: str = JOB_SKIPPED
    detail: str = ''
    changed: list[str] = field(default_factory=list)
    artwork_px: int = 0
    artwork_source: str = ''
    new_path: Optional[str] = None


@dataclass
class UpgradeDeps:
    """Everything an upgrade needs from the running app."""

    context: Callable[[], LibraryContext]
    settings: Callable[[], dict[str, Any]]
    version: str = '0.0.0'
    spotify_id_for: Optional[Callable[[str], str]] = None
    lyrics_cache: Any = None
    publish: Optional[Callable[[dict[str, Any]], None]] = None
    rekey_owners: Optional[Callable[[str, str, str], None]] = None
    downloader: Optional[Callable[[], Any]] = None
    on_track_path_changed: Optional[Callable[[str, str, Path], None]] = None


def resolve_track(stored_path: str, ctx: LibraryContext) -> Optional[Path]:
    return locate_library_file(
        stored_path, ctx.download_dir, ctx.slskd_dir, ctx.extra_dirs
    )


@dataclass
class _Artwork:
    """The cover an upgrade decided on, and where it came from."""

    data: Optional[bytes] = None
    px: int = 0
    source: str = ''


def _library_entry(
    stored_path: str, ctx: LibraryContext
) -> Optional[tuple[Path, dict[str, Any]]]:
    full = resolve_track(stored_path, ctx)
    if full is None or ctx.metadata_cache is None:
        return None
    entries = ctx.metadata_cache.get_entries_batch([(stored_path, full)])
    return (full, entries[0]) if entries else None


def _pick_artwork(
    song: dict[str, Any],
    full: Path,
    entry: dict[str, Any],
    *,
    options: UpgradeOptions,
) -> _Artwork:
    """A bigger cover than the file has, or the file's own size."""

    have = int(entry.get('cover_px') or 0)
    if CATEGORY_ARTWORK not in options.categories:
        return _Artwork(px=have)
    if have >= options.artwork_min_px:
        return _Artwork(px=have)
    better = cover_sources.best_cover(
        song,
        current=cover_sources.current_cover(full),
        preference=options.artwork_source,
    )
    if better is None:
        return _Artwork(px=have)
    return _Artwork(data=better.data, px=better.width, source=better.source)


def _pick_lyrics(
    song: dict[str, Any],
    full: Path,
    *,
    deps: UpgradeDeps,
    options: UpgradeOptions,
) -> Optional[lyrics_mod.Lyrics]:
    """Lyrics for a track that has none, or ``None`` to leave it be."""

    if CATEGORY_LYRICS not in options.categories:
        return None
    existing = read_track_lyrics(full)
    if existing.get('synced') or existing.get('plain'):
        return None
    providers = list(deps.settings().get('lyrics_providers') or [])
    if not providers:
        return None
    found = lyrics_mod.fetch(song, providers, deps.lyrics_cache)
    return found if found is not None and found.has_any() else None


def _write_upgrade(
    full: Path,
    song: dict[str, Any],
    *,
    artwork: _Artwork,
    new_lyrics: Optional[lyrics_mod.Lyrics],
    write_tags: bool,
) -> Optional[str]:
    """Rewrite *full* through a verified working copy; error text or ``None``."""

    try:
        stage = _stage(full)
    except OSError as exc:
        return f'Could not stage a copy: {exc}'

    try:
        if write_tags:
            # The existing cover is written back when nothing better was
            # found, so a metadata-only pass never strips artwork.
            keep = cover_sources.current_cover(full)
            embed_metadata(
                stage.staged,
                song,
                download_cover=True,
                cover_bytes=artwork.data
                or (keep.data if keep is not None else None),
            )
        if new_lyrics is not None:
            embed_lyrics(
                stage.staged,
                new_lyrics,
                sidecar=stage.staged.with_suffix('.lrc'),
            )
    except Exception as exc:
        _discard(stage)
        logger.opt(exception=True).warning(
            'Library upgrade failed for {}', full.name
        )
        return str(exc)[:200]

    staged_lrc = stage.staged.with_suffix('.lrc')
    if not _commit(stage):
        staged_lrc.unlink(missing_ok=True)
        return 'The rewritten file did not verify; kept the original'
    if new_lyrics is not None and staged_lrc.exists():
        dest_lrc = lyrics_mod.lrc_path_for(full)
        dest_lrc.parent.mkdir(parents=True, exist_ok=True)
        os.replace(str(staged_lrc), str(dest_lrc))
        beside = full.with_suffix('.lrc')
        if dest_lrc != beside:
            beside.unlink(missing_ok=True)
    return None


def _outcome_detail(
    changed: list[str],
    artwork: _Artwork,
    target_format: str = '',
    target_bitrate: int = 0,
) -> str:
    parts: list[str] = []
    for name in changed:
        if name == CATEGORY_ARTWORK and artwork.px:
            parts.append(f'artwork {artwork.px}px ({artwork.source})')
        elif name == CATEGORY_FORMAT:
            fmt_str = target_format or 'format'
            if target_bitrate and fmt_str != 'flac':
                parts.append(f'format {fmt_str} ({target_bitrate}k)')
            else:
                parts.append(f'format {fmt_str}')
        else:
            parts.append(name)
    return ', '.join(parts)


def upgrade_track(
    stored_path: str,
    *,
    deps: UpgradeDeps,
    options: UpgradeOptions,
    on_stage: Optional[Callable[[str], None]] = None,
) -> UpgradeOutcome:
    """Apply the requested categories to one library track."""

    def stage_now(name: str) -> None:
        if on_stage:
            on_stage(name)

    ctx = deps.context()
    found = _library_entry(stored_path, ctx)
    if found is None:
        return UpgradeOutcome(JOB_SKIPPED, 'File is no longer in the library')
    full, entry = found

    spotify_id = (
        deps.spotify_id_for(stored_path) or ''
        if deps.spotify_id_for is not None
        else ''
    )
    stage_now('matching')
    song = song_for_track(
        entry,
        spotify_id=spotify_id,
        refresh_metadata=CATEGORY_METADATA in options.categories,
    )

    stage_now('artwork')
    artwork = _pick_artwork(song, full, entry, options=options)
    stage_now('lyrics')
    new_lyrics = _pick_lyrics(song, full, deps=deps, options=options)

    changed: list[str] = []
    if artwork.data is not None:
        changed.append(CATEGORY_ARTWORK)
    if (
        CATEGORY_METADATA in options.categories
        and spotify_id
        and _metadata_gaps(entry)
    ):
        changed.append(CATEGORY_METADATA)

    format_needed = (
        CATEGORY_FORMAT in options.categories
        and track_format_improper(
            entry,
            full,
            target_format=options.target_format,
            target_bitrate_kbps=options.target_bitrate,
            source_targets=options.source_targets,
            audio_providers=options.audio_providers,
        )
    )

    if format_needed:
        downloader = deps.downloader() if deps.downloader is not None else None
        if downloader is None:
            from .downloader import Downloader

            downloader = Downloader(
                ctx.download_dir,
                audio_format=options.target_format,
                audio_bitrate=str(options.target_bitrate),
                slskd_settings=(deps.settings() or {}).get('slskd'),
            )

        audio_providers = (
            options.audio_providers
            or getattr(downloader, 'audio_providers', None)
            or ['youtube-music']
        )
        source_targets = (
            options.source_targets
            or getattr(downloader, 'source_targets', None)
            or {}
        )

        curr_fmt = full.suffix.lower().lstrip('.')
        curr_bitrate_bps = int(entry.get('bitrate') or 0)
        if curr_bitrate_bps <= 0:
            try:
                audio_meta = MutagenFile(str(full))
                info = getattr(audio_meta, 'info', None)
                curr_bitrate_bps = int(getattr(info, 'bitrate', 0) or 0)
            except Exception:
                curr_bitrate_bps = 0
        curr_bitrate_kbps = (
            round(curr_bitrate_bps / 1000) if curr_bitrate_bps > 0 else 0
        )
        if curr_fmt == 'flac':
            curr_bitrate_kbps = 9999

        stage_now('downloading')
        basename = f'{full.stem}{UPGRADE_STAGING_MARKER}'
        stat = full.stat()
        try:
            old_key = file_content_key(full) or ''
        except Exception:
            old_key = ''

        staged_path: Optional[Path] = None
        effective_target_fmt = ''
        effective_target_bitrate = 0

        try:
            for provider in audio_providers:
                p_targets = source_targets.get(provider) or [{
                    'format': options.target_format or 'mp3',
                    'bitrate': str(options.target_bitrate or 320),
                }]

                for tgt in p_targets:
                    t_fmt = str(tgt.get('format') or 'mp3').lower().lstrip('.')
                    t_br_str = str(tgt.get('bitrate') or '320')
                    try:
                        t_br = (
                            int(t_br_str)
                            if t_br_str.isdigit()
                            else (0 if t_fmt == 'flac' else 320)
                        )
                    except (TypeError, ValueError):
                        t_br = 320

                    if curr_fmt == 'flac' and t_fmt != 'flac':
                        continue
                    if curr_fmt == t_fmt and t_fmt == 'flac':
                        continue
                    if (
                        curr_fmt == t_fmt
                        and curr_bitrate_kbps >= (t_br - 15)
                        and t_br > 0
                    ):
                        continue

                    if provider == 'slskd':
                        slskd_settings = (
                            getattr(downloader, 'slskd_settings', None)
                            or (deps.settings() or {}).get('slskd')
                            or {}
                        )
                        if not slskd_settings.get('enabled'):
                            continue

                        local_source = download_from_slskd(
                            song,
                            slskd_settings,
                            target_format=t_fmt,
                            min_bitrate=t_br,
                        )
                        if local_source is not None and local_source.is_file():
                            staged_dest = (
                                full.parent
                                / f'{full.stem}{UPGRADE_STAGING_MARKER}.{t_fmt}'
                            )
                            shutil.copy2(local_source, staged_dest)
                            staged_path = staged_dest
                            effective_target_fmt = t_fmt
                            effective_target_bitrate = t_br
                            break

                    elif provider == 'youtube-music':
                        if providers.find_match != _ORIG_PROVIDERS_FIND_MATCH:
                            video_id, ytm_match = providers.find_match(song)
                        elif find_match_youtube_music_only != _ORIG_FIND_MATCH_YTM_ONLY:
                            video_id, ytm_match = find_match_youtube_music_only(song)
                        else:
                            video_id, ytm_match = find_match_youtube_music_only(song)
                            if not video_id:
                                video_id, ytm_match = providers.find_match(song)
                        if video_id:
                            try:
                                staged_path = downloader.fetch_audio(
                                    video_id,
                                    full.parent,
                                    basename,
                                    song=song,
                                    provider='youtube-music',
                                    audio_format=t_fmt,
                                    audio_bitrate=str(t_br or '320'),
                                )
                                if (
                                    staged_path
                                    and staged_path.is_file()
                                    and staged_path.stat().st_size > 0
                                ):
                                    effective_target_fmt = t_fmt
                                    effective_target_bitrate = t_br
                                    break
                                staged_path = None
                            except Exception:
                                staged_path = None

                    elif provider == 'youtube':
                        video_id = providers.find_match_youtube_only(song)
                        if not video_id:
                            v_id, match = providers.find_match(song)
                            if v_id and match is None:
                                video_id = v_id
                        if video_id:
                            try:
                                staged_path = downloader.fetch_audio(
                                    video_id,
                                    full.parent,
                                    basename,
                                    song=song,
                                    provider='youtube',
                                    audio_format=t_fmt,
                                    audio_bitrate=str(t_br or '320'),
                                )
                                if (
                                    staged_path
                                    and staged_path.is_file()
                                    and staged_path.stat().st_size > 0
                                ):
                                    effective_target_fmt = t_fmt
                                    effective_target_bitrate = t_br
                                    break
                                staged_path = None
                            except Exception:
                                staged_path = None

                if staged_path is not None:
                    break

            if (
                not staged_path
                or not staged_path.is_file()
                or staged_path.stat().st_size <= 0
            ):
                return UpgradeOutcome(
                    JOB_FAILED,
                    f"No verified audio match found for {song.get('name')!r}",
                )

            after_length = _audio_length(staged_path)
            if after_length <= 0:
                return UpgradeOutcome(
                    JOB_FAILED, 'Downloaded audio could not be read'
                )

            stage_now('writing')
            keep_cover = cover_sources.current_cover(full)
            cover_bytes = artwork.data or (
                keep_cover.data if keep_cover is not None else None
            )
            embed_metadata(
                staged_path,
                song,
                download_cover=True,
                cover_bytes=cover_bytes,
            )
            eff_lyrics = new_lyrics
            if eff_lyrics is None:
                from .lyrics import Lyrics, read_track_lyrics

                ex = read_track_lyrics(full)
                if ex.get('synced') or ex.get('plain'):
                    eff_lyrics = Lyrics(
                        synced=ex.get('synced') or '',
                        plain=ex.get('plain') or '',
                        provider=ex.get('provider') or '',
                    )
            if eff_lyrics is not None:
                embed_lyrics(
                    staged_path,
                    eff_lyrics,
                    sidecar=staged_path.with_suffix('.lrc'),
                )

            final_path = full.with_name(f'{full.stem}.{effective_target_fmt}')
            os.replace(str(staged_path), str(final_path))
            staged_path = None

            if final_path != full:
                full.unlink(missing_ok=True)
                old_lrc = full.with_suffix('.lrc')
                new_lrc = final_path.with_suffix('.lrc')
                if old_lrc.is_file() and not new_lrc.exists():
                    try:
                        os.replace(str(old_lrc), str(new_lrc))
                    except Exception:
                        pass

            try:
                os.utime(str(final_path), ns=(stat.st_atime_ns, stat.st_mtime_ns))
            except OSError:
                pass

            changed.append(CATEGORY_FORMAT)
            if new_lyrics is not None:
                changed.append(CATEGORY_LYRICS)

            old_stored = stored_path
            new_stored = str(
                Path(stored_path).with_suffix(f'.{effective_target_fmt}')
            )
            if ctx.metadata_cache is not None:
                try:
                    if new_stored != old_stored:
                        ctx.metadata_cache.forget(old_stored, full_path=full)
                    ctx.metadata_cache.refresh(new_stored, final_path)
                except Exception:
                    logger.debug('Metadata cache refresh failed')

            if new_stored != old_stored:
                if ctx.download_dir:
                    try:
                        from .m3u import iter_m3u_files
                        for m3u_path in iter_m3u_files(ctx.download_dir):
                            try:
                                text = m3u_path.read_text(encoding='utf-8')
                                if old_stored in text:
                                    m3u_path.write_text(
                                        text.replace(old_stored, new_stored),
                                        encoding='utf-8',
                                    )
                            except Exception:
                                pass
                    except Exception:
                        pass

                try:
                    from .library_catalog import (
                        drop_library_listing_files,
                        merge_library_listing_file,
                    )

                    drop_library_listing_files(ctx, [old_stored])
                    merge_library_listing_file(ctx, new_stored)
                except Exception:
                    logger.opt(exception=True).debug(
                        'Library listing RAM update failed'
                    )

                try:
                    from .library_paths_cache import (
                        invalidate_library_paths_cache,
                    )

                    invalidate_library_paths_cache(
                        drop_entries=True, notify=True
                    )
                except Exception:
                    logger.opt(exception=True).debug(
                        'Library paths cache invalidation failed'
                    )

                if old_key and deps.rekey_owners is not None:
                    try:
                        new_key = file_content_key(final_path) or ''
                        if new_key:
                            deps.rekey_owners(old_key, new_key, new_stored)
                    except Exception:
                        logger.opt(exception=True).debug(
                            'Library upgrade: could not rekey owners for {}',
                            new_stored,
                        )

                if deps.on_track_path_changed is not None:
                    try:
                        deps.on_track_path_changed(
                            old_stored, new_stored, final_path
                        )
                    except Exception:
                        logger.opt(exception=True).debug(
                            'on_track_path_changed hook failed'
                        )

            return UpgradeOutcome(
                JOB_DONE,
                _outcome_detail(
                    changed,
                    artwork,
                    target_format=effective_target_fmt,
                    target_bitrate=effective_target_bitrate,
                ),
                changed=changed,
                artwork_px=artwork.px,
                artwork_source=artwork.source,
                new_path=new_stored if new_stored != old_stored else None,
            )
        except Exception as exc:
            logger.opt(exception=True).warning(
                'Format upgrade failed for {}: {}', full.name, exc
            )
            return UpgradeOutcome(JOB_FAILED, f'Format upgrade failed: {exc}')
        finally:
            if staged_path is not None and staged_path.is_file():
                staged_path.unlink(missing_ok=True)
            for leftover in full.parent.glob(f"{basename}.*"):
                if leftover.is_file():
                    leftover.unlink(missing_ok=True)

    if not changed and new_lyrics is None:
        return UpgradeOutcome(
            JOB_SKIPPED,
            'Already up to date',
            artwork_px=artwork.px,
            artwork_source=artwork.source,
        )

    stage_now('writing')
    try:
        old_key = file_content_key(full) or ''
    except Exception:
        old_key = ''
    error = _write_upgrade(
        full,
        song,
        artwork=artwork,
        new_lyrics=new_lyrics,
        write_tags=bool(changed),
    )
    if error:
        return UpgradeOutcome(JOB_FAILED, error)
    if old_key and deps.rekey_owners is not None:
        try:
            new_key = file_content_key(full) or ''
            if new_key:
                deps.rekey_owners(old_key, new_key, stored_path)
        except Exception:
            logger.opt(exception=True).debug(
                'Library upgrade: could not rekey owners for {}',
                stored_path,
            )

    if new_lyrics is not None:
        changed.append(CATEGORY_LYRICS)
    if ctx.metadata_cache is not None:
        try:
            ctx.metadata_cache.refresh(stored_path, full)
        except Exception:
            logger.debug('Library upgrade: metadata cache refresh failed')

    return UpgradeOutcome(
        JOB_DONE,
        _outcome_detail(
            changed,
            artwork,
            target_format=options.target_format,
            target_bitrate=options.target_bitrate,
        ),
        changed=changed,
        artwork_px=artwork.px,
        artwork_source=artwork.source,
    )


# ── Scan + queue runner ───────────────────────────────────────────────
class LibraryUpgradeRunner:
    """Owns the scan and the worker thread that drains the queue."""

    def __init__(self, db: LibraryUpgradeDB, deps: UpgradeDeps) -> None:
        self.db = db
        self.deps = deps
        self._lock = threading.Lock()
        self._worker: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._cancelled = False
        self._scanned = 0
        self._scan_total = 0
        self._last_publish = 0.0

    # -- helpers --
    def _publish(
        self,
        extra: Optional[dict[str, Any]] = None,
        *,
        throttle: bool = False,
    ) -> None:
        """Broadcast progress, at most once a second while grinding."""

        if self.deps.publish is None:
            return
        now = time.monotonic()
        if throttle and now - self._last_publish < _PUBLISH_INTERVAL_SECONDS:
            return
        self._last_publish = now
        try:
            self.deps.publish(self.status(extra))
        except Exception:
            logger.debug('Library upgrade: progress broadcast failed')

    def status(self, extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        run = self.db.latest_run()
        if run is None:
            return {'state': 'idle', 'run': None, 'counts': {}, 'scan': {}}
        counts = self.db.counts(int(run['id']))
        payload: dict[str, Any] = {
            'state': run['state'],
            'run': run,
            'counts': counts,
            # Carried by every progress message, not only the initial
            # GET, so a client that only ever sees WebSocket updates
            # still knows what the scan found.
            'summary': self._summary_for(run),
            'scan': {
                'scanned': self._scanned,
                'total': self._scan_total,
            },
        }
        if extra:
            payload.update(extra)
        return payload

    def busy(self) -> bool:
        worker = self._worker
        return worker is not None and worker.is_alive()

    # -- scanning --
    def start_scan(self, options: UpgradeOptions) -> dict[str, Any]:
        with self._lock:
            if self.busy():
                raise RuntimeError('A library upgrade is already running')
            active_cats = [
                c for c in CATEGORIES
                if c != CATEGORY_FORMAT or options.check_format
            ]
            run_id = self.db.create_run(active_cats, options.as_dict())
            self._cancelled = False
            self._stop.clear()
            self._scanned = 0
            self._scan_total = 0
            self._worker = threading.Thread(
                target=self._scan,
                args=(run_id, options),
                name='downtify-upgrade-scan',
                daemon=True,
            )
            self._worker.start()
        return self.status()

    def _scan(self, run_id: int, options: UpgradeOptions) -> None:
        try:
            ctx = self.deps.context()
            entries = list_library_entries(ctx)
            self._scan_total = len(entries)
            checks = self.db.checks_for([str(e['file']) for e in entries])
            jobs: list[dict[str, Any]] = []
            checked: list[tuple[str, list[str]]] = []
            total_bytes = 0
            skipped = 0
            active_cats = [
                c for c in CATEGORIES
                if c != CATEGORY_FORMAT or options.check_format
            ]
            for index, entry in enumerate(entries, start=1):
                if self._stop.is_set():
                    self.db.set_state(run_id, STATE_CANCELLED)
                    self._publish()
                    return
                stored = str(entry['file'])
                total_bytes += int(entry.get('size') or 0)
                self._scanned = index
                self._publish(throttle=True)
                due = self._categories_due(
                    checks.get(stored) or {},
                    options.recheck_days,
                    check_format=options.check_format,
                )
                if not due:
                    # Every category was looked at recently: don't even
                    # read the file.
                    skipped += 1
                    continue
                full = resolve_track(stored, ctx)
                if full is None:
                    continue
                behind = set(
                    track_findings(
                        entry,
                        full,
                        artwork_min_px=options.artwork_min_px,
                        check_format=options.check_format,
                        target_format=options.target_format,
                        target_bitrate_kbps=options.target_bitrate,
                        source_targets=options.source_targets,
                        audio_providers=options.audio_providers,
                    )
                )
                found = [name for name in active_cats if name in due & behind]
                # Looking and finding nothing counts as a check, so the
                # next scan doesn't read this file again for those.
                clean = sorted(due - behind)
                if clean:
                    checked.append((stored, clean))
                if found:
                    jobs.append({
                        'file': stored,
                        'categories': found,
                        'size': int(entry.get('size') or 0),
                        'title': str(entry.get('title') or ''),
                        'artist': str(entry.get('artist') or ''),
                    })
            self.db.record_checks(checked, app_version=self.deps.version)
            self.db.add_jobs(run_id, jobs)
            self.db.set_totals(run_id, len(entries), total_bytes)
            self.db.set_summary(run_id, _summarize(jobs, skipped))
            self.db.set_state(run_id, STATE_READY)
        except Exception:
            logger.opt(exception=True).error('Library upgrade scan failed')
            self.db.set_state(run_id, STATE_CANCELLED)
        self._publish()

    def _categories_due(
        self,
        track_checks: dict[str, Any],
        recheck_days: int,
        check_format: bool = False,
    ) -> set[str]:
        """Categories this track hasn't had looked at recently.

        Kept per category: repairing a track's artwork says nothing
        about whether anyone ever went looking for its lyrics, so a
        later run for another category must still consider it.
        """

        due = {
            name
            for name in DEFAULT_CATEGORIES
            if not check_is_fresh(
                track_checks.get(name),
                app_version=self.deps.version,
                max_age_days=recheck_days,
            )
        }
        if check_format:
            due.add(CATEGORY_FORMAT)
        return due

    @staticmethod
    def _summary_for(run: dict[str, Any]) -> dict[str, Any]:
        stored = run.get('summary') or {}
        return {
            'categories': stored.get('categories') or {},
            'category_bytes': stored.get('category_bytes') or {},
            'tracks': int(stored.get('tracks') or 0),
            'recently_checked': int(stored.get('recently_checked') or 0),
            'library_tracks': int(run['total_tracks'] or 0),
            'library_bytes': int(run['total_bytes'] or 0),
        }

    def scan_summary(self) -> dict[str, Any]:
        """Per-category counts for the finished scan of the latest run."""

        run = self.db.latest_run()
        if run is None:
            return {'categories': {}, 'category_bytes': {}, 'tracks': 0}
        return self._summary_for(run)

    # -- running --
    def start(self, categories: tuple[str, ...]) -> dict[str, Any]:
        with self._lock:
            if self.busy():
                raise RuntimeError('A library upgrade is already running')
            run = self.db.latest_run()
            if run is None or run['state'] not in {
                STATE_READY,
                STATE_PAUSED,
            }:
                raise RuntimeError('Scan the library before upgrading it')
            run_id = int(run['id'])
            # Remembered so a resume after a restart runs the same
            # categories the user picked, not everything the scan found.
            self.db.set_categories(run_id, list(categories))
            opts = run.get('options') or {}
            options = UpgradeOptions(
                categories=categories,
                artwork_min_px=int(
                    opts.get('artwork_min_px')
                    or DEFAULT_ARTWORK_MIN_PX
                ),
                artwork_source=str(
                    opts.get('artwork_source')
                    or cover_sources.PREFERENCE_HIGHEST
                ),
                recheck_days=int(
                    opts.get('recheck_days') or DEFAULT_RECHECK_DAYS
                ),
                check_format=bool(opts.get('check_format', False)),
                target_format=str(opts.get('target_format') or 'mp3'),
                target_bitrate=int(opts.get('target_bitrate') or 320),
            )
            self._begin(run_id, options)
        return self.status()

    def _begin(self, run_id: int, options: UpgradeOptions) -> None:
        self._cancelled = False
        self._stop.clear()
        self.db.requeue_running(run_id)
        self.db.set_state(run_id, STATE_RUNNING)
        self._worker = threading.Thread(
            target=self._run,
            args=(run_id, options),
            name='downtify-upgrade',
            daemon=True,
        )
        self._worker.start()

    def _run(self, run_id: int, options: UpgradeOptions) -> None:
        wanted = set(options.categories)
        while not self._stop.is_set():
            job = self.db.take_next(run_id)
            if job is None:
                self.db.set_state(run_id, STATE_DONE)
                break
            stored = str(job['file'])
            todo = [name for name in job['categories'] if name in wanted]
            if not todo:
                self.db.finish_job(
                    run_id, stored, JOB_SKIPPED, detail='Not selected'
                )
                continue
            self._process(run_id, stored, options, todo)
            self._publish(throttle=True)
        else:
            state = STATE_CANCELLED if self._cancelled else STATE_PAUSED
            self.db.requeue_running(run_id)
            self.db.set_state(run_id, state)
        try:
            from .library_paths_cache import invalidate_library_paths_cache
            invalidate_library_paths_cache(drop_entries=True, notify=True)
        except Exception:
            pass
        self._publish()

    def _process(
        self,
        run_id: int,
        stored: str,
        options: UpgradeOptions,
        todo: list[str],
    ) -> None:
        def on_stage(stage: str) -> None:
            self.db.set_stage(run_id, stored, stage)

        try:
            outcome = upgrade_track(
                stored,
                deps=self.deps,
                options=UpgradeOptions(
                    categories=tuple(todo),
                    artwork_min_px=options.artwork_min_px,
                    artwork_source=options.artwork_source,
                    recheck_days=options.recheck_days,
                    check_format=options.check_format,
                    target_format=options.target_format,
                    target_bitrate=options.target_bitrate,
                ),
                on_stage=on_stage,
            )
        except Exception as exc:
            logger.opt(exception=True).warning(
                'Library upgrade: {} failed', stored
            )
            outcome = UpgradeOutcome(JOB_FAILED, str(exc)[:200])

        target_stored = outcome.new_path or stored
        if outcome.new_path and outcome.new_path != stored:
            try:
                self.db.rekey_track(stored, outcome.new_path)
            except Exception:
                pass

        self.db.finish_job(
            run_id,
            target_stored,
            outcome.status,
            detail=outcome.detail,
            changed=outcome.changed,
        )
        if outcome.status != JOB_FAILED:
            # Only the categories this run actually looked at: the rest
            # stay due, so a later run for them still considers the
            # track.
            self.db.record_check(
                target_stored,
                todo,
                app_version=self.deps.version,
                artwork_px=outcome.artwork_px,
                artwork_source=outcome.artwork_source,
            )

    def pause(self) -> dict[str, Any]:
        self._cancelled = False
        self._stop.set()
        return self.status()

    def cancel(self) -> dict[str, Any]:
        run = self.db.latest_run()
        self._cancelled = True
        self._stop.set()
        if run is not None and not self.busy():
            self.db.set_state(int(run['id']), STATE_CANCELLED)
        return self.status()

    def resume(self) -> dict[str, Any]:
        run = self.db.latest_run()
        if run is None or run['state'] != STATE_PAUSED:
            raise RuntimeError('Nothing to resume')
        return self.start(normalize_categories(run['categories']))

    def resume_after_restart(self) -> None:
        """Pick a run back up when the process died mid-upgrade."""

        run = self.db.latest_run()
        if run is None:
            return
        run_id = int(run['id'])
        if run['state'] == STATE_SCANNING:
            # A half-finished scan can't be trusted; drop it.
            self.db.delete_run_jobs(run_id)
            self.db.set_state(run_id, STATE_CANCELLED)
            return
        if run['state'] != STATE_RUNNING:
            return
        requeued = self.db.requeue_running(run_id)
        opts = run.get('options') or {}
        options = UpgradeOptions(
            categories=normalize_categories(run['categories']),
            artwork_min_px=int(
                opts.get('artwork_min_px') or DEFAULT_ARTWORK_MIN_PX
            ),
            artwork_source=str(
                opts.get('artwork_source')
                or cover_sources.PREFERENCE_HIGHEST
            ),
            recheck_days=int(
                opts.get('recheck_days') or DEFAULT_RECHECK_DAYS
            ),
            check_format=bool(opts.get('check_format', False)),
            target_format=str(opts.get('target_format') or 'mp3'),
            target_bitrate=int(opts.get('target_bitrate') or 320),
        )
        logger.info(
            'Library upgrade: resuming run {} ({} track(s) re-queued)',
            run_id,
            requeued,
        )
        with self._lock:
            self._begin(run_id, options)
