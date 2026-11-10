"""The API the Downtify apps use: ``/api/v1``.

Separate from the web app's routes (whose shapes the web app depends on
and which don't change) so this surface can be versioned on its own -
``api_version`` in ``GET /api/server/info`` says which one a server
speaks. Everything is addressed by **track id** (see
:mod:`downtify.library_sync`), never by file path. The full contract,
from discovery to reporting plays, is ``docs/mobile-client-contract.md``.
"""

from __future__ import annotations

import asyncio
import mimetypes
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from loguru import logger

from . import api
from .auth import SIGNED_URL_DEFAULT_TTL, SIGNED_URL_MAX_TTL, Principal
from .cover_thumbs import normalize_size
from .library_catalog import list_library_entries, resolve_library_file
from .library_paths_cache import invalidate_library_paths_cache
from .lyrics import read_track_lyrics
from .playlist_suggestions import get_playlist_suggestions
from .transcode import (
    FORMATS,
    TranscodeError,
    normalize_bitrate,
    serve_original,
)

router = APIRouter(prefix='/api/v1')

#: How long a phone may keep an audio file or cover without asking again.
_PRIVATE_CACHE = 'private, max-age=604800'


def _sync():
    if api.state.library_sync is None:
        raise HTTPException(status_code=503, detail='Starting up')
    return api.state.library_sync


def _refresh() -> int:
    """Bring the track ids in line with what's on disk; the new cursor."""

    return _sync().refresh(list_library_entries(api.library_context()))


def _track_path(track_id: str) -> tuple[dict[str, Any], Path]:
    """A track's row and file, or 404."""

    sync = _sync()
    row = sync.row_for(track_id)
    if row is None:
        _refresh()
        row = sync.row_for(track_id)
    if row is None:
        raise HTTPException(status_code=404, detail='Track not found')
    full = resolve_library_file(row['file'], api.library_context())
    if full is None:
        raise HTTPException(status_code=404, detail='File not found')
    return row, full


# ── The library ─────────────────────────────────────────────────────────


@router.get('/library')
async def library(
    request: Request,
    response: Response,
    since: int = Query(0, ge=0),
    refresh: bool = Query(False),
) -> Any:
    """Tracks added or changed since *since*, and ids of tracks removed.

    ``{cursor, full, tracks, deleted}``; keep ``cursor`` for next time.
    ``full: true`` means ``tracks`` is the whole library (a first sync, or
    a cursor too old to answer): replace everything you have with it.
    The folder scan behind it is cached for a minute or so;
    ``refresh=true`` (pull to refresh) rescans now - for files added to
    the folder by something other than Downtify.
    """

    if refresh:
        invalidate_library_paths_cache(notify=False, drop_entries=True)
    before = await asyncio.to_thread(_sync().cursor)
    cursor = await asyncio.to_thread(_refresh)
    if cursor != before:
        # Found something new on disk: other apps should sync too.
        api.announce_library_changed()
    allowed = api.allowed_entry_keys(request)
    if allowed is not None:
        visible_playlists = await asyncio.to_thread(
            api.playlists_for_request, request
        )
        playlist_paths = [
            f for p in visible_playlists for f in (p.get('files') or [])
        ]
        if playlist_paths:
            extra_keys = await asyncio.to_thread(
                _sync().keys_for_paths, playlist_paths
            )
            allowed = set(allowed) | extra_keys
    scope = 'a' if allowed is None else api.request_user_id(request)
    etag = f'"lib-{cursor}-{since}-{scope}"'
    if request.headers.get('if-none-match') == etag:
        return Response(status_code=304, headers={'ETag': etag})
    response.headers['ETag'] = etag
    response.headers['Cache-Control'] = 'private, no-cache'
    return await asyncio.to_thread(
        _sync().changes, since, allowed_keys=allowed
    )


@router.get('/tracks/{track_id}')
def track(track_id: str) -> dict[str, Any]:
    row, _full = _track_path(track_id)
    return row


@router.get('/tracks/{track_id}/lyrics')
def track_lyrics(
    track_id: str,
    request: Request,
    lang: Optional[str] = None,
) -> dict[str, Any]:
    """``{synced, plain}``: the ``.lrc`` sidecar and the embedded lyrics."""

    _row, full = _track_path(track_id)
    target_lang = lang
    if not target_lang:
        try:
            accept = request.headers.get('accept-language', '')
            if accept:
                target_lang = accept.split(',')[0].split(';')[0].strip()
        except Exception:
            pass
    if not target_lang:
        target_lang = (api.state.settings or {}).get('ui_language') or 'en'
    return read_track_lyrics(full, target_lang=target_lang)


@router.get('/playlists')
async def playlists(request: Request) -> list[dict[str, Any]]:
    """Downloaded playlists as ``{name, liked, manual, public, monitored,
    owner, owner_id, is_owner, can_edit, hidden, count, track_ids, cover}``
    - ``cover`` is a path for ``GET /playlist-cover?file=`` or ``''``.
    A user sees their own playlists, their own liked songs, and any
    Public/Monitored playlists."""

    await asyncio.to_thread(_refresh)
    found = await asyncio.to_thread(api.playlists_for_request, request)
    paths = [f for p in found for f in p['files']]
    ids = await asyncio.to_thread(_sync().ids_for_paths, paths)
    return [
        {
            'name': p['name'],
            'display_name': p.get('display_name') or p.get('title') or p['name'],
            'liked': p['liked'],
            'manual': bool(p.get('manual')),
            'public': bool(p.get('public')),
            'monitored': bool(p.get('monitored')),
            'owner': str(p.get('owner') or ''),
            'owner_id': int(p.get('owner_id') or 0),
            'is_owner': bool(p.get('is_owner')),
            'can_edit': bool(p.get('can_edit')),
            'can_change_owner': bool(p.get('can_change_owner')),
            'hidden': bool(p.get('hidden')),
            'favorite': bool(p.get('favorite')),
            'count': p.get('count', len(p.get('files') or [])),
            'cover': p.get('cover') or '',
            'files': p.get('files') or [],
            'track_ids': [
                ids.get(f) or ids.get(f.replace('\\', '/')) or ids.get(f.replace('/', '\\'))
                for f in p.get('files') or []
                if (ids.get(f) or ids.get(f.replace('\\', '/')) or ids.get(f.replace('/', '\\')))
            ],
        }
        for p in found
    ]


@router.post('/playlists')
async def mobile_create_playlist(request: Request) -> dict[str, Any]:
    """Create a new manual playlist for the signed-in user."""

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    name = str((payload or {}).get('name') or '').strip()
    if not name:
        raise HTTPException(status_code=400, detail='name is required')
    ctx = api.library_context()
    try:
        result = await asyncio.to_thread(api.create_manual_playlist, ctx, name)
    except api.ManualPlaylistError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=str(exc)
        ) from exc
    api.claim_manual_playlist(str(result.get('name') or name), request)
    invalidate_library_paths_cache()
    await api.log_activity(request, 'playlist_create', result.get('name') or name)
    return result


@router.get('/playlists/{name}/suggestions')
async def mobile_playlist_suggestions(
    name: str,
    request: Request,
    limit: int = Query(20, ge=1, le=50),
    dismissed: Optional[list[str]] = Query(None),
) -> dict[str, Any]:
    """Songs matching the tone and vibe of the playlist for mobile apps."""

    api.require_playlist_visible(name, request)
    dismissed_list: list[str] = []
    if dismissed:
        for item in dismissed:
            for piece in str(item).split(','):
                p = piece.strip()
                if p:
                    dismissed_list.append(p)

    ctx = api.library_context()
    dl_dir = (
        Path(api.state.downloader.download_dir)
        if api.state.downloader
        else ctx.download_dir
    )
    return await asyncio.to_thread(
        get_playlist_suggestions,
        name,
        dl_dir,
        limit=limit,
        dismissed=dismissed_list,
        ctx=ctx,
        catalog=api.state.playlist_catalog,
        likes_store=api.state.likes,
        track_index=api.state.track_index,
    )


@router.post('/playlists/{name}/tracks')
async def mobile_add_playlist_track(
    name: str,
    request: Request,
) -> dict[str, Any]:
    """Add a library track by track_id, or download a suggested song directly into the playlist."""

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    track_id = str((payload or {}).get('track_id') or '').strip()
    if not api.is_liked_playlist(name):
        api.require_playlist_owner(name, request)
    user_id = api.request_user_id(request)

    if track_id:
        row = await asyncio.to_thread(_sync().row_for, track_id)
        if row is not None:
            try:
                result = await asyncio.to_thread(
                    api.add_track_to_playlist_internal_sync, name, row['file'], user_id
                )
                return {'status': 'ok', 'playlist': name, 'track_id': track_id, 'result': result}
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc

    # If track is not already in the library, queue download into this playlist on the server
    song_id = str((payload or {}).get('song_id') or (payload or {}).get('video_id') or '').strip()
    title = str((payload or {}).get('title') or (payload or {}).get('name') or '').strip()
    artist = str((payload or {}).get('artist') or '').strip()
    cover_url = str((payload or {}).get('cover_url') or (payload or {}).get('thumbnail') or '').strip()
    url = str((payload or {}).get('url') or '').strip() or (f'https://music.youtube.com/watch?v={song_id}' if song_id else '')

    if not title and not song_id and not track_id:
        raise HTTPException(status_code=400, detail='track_id or song details required')

    song_dict = {
        'song_id': song_id,
        'name': title,
        'title': title,
        'artist': artist,
        'artists': [artist] if artist else [],
        'cover_url': cover_url,
        'thumbnail': cover_url,
        'url': url,
    }
    batch_res = await api._submit_playlist_batch(
        [song_dict],
        playlist_url='',
        generate_m3u=True,
        playlist_name=name,
        cover_url=cover_url or None,
        user_id=user_id,
    )
    return {'status': 'ok', 'playlist': name, 'download_queued': True, 'result': batch_res}


@router.post('/playlists/{name}/tracks/remove')
async def mobile_remove_playlist_track(
    name: str,
    request: Request,
) -> dict[str, Any]:
    """Remove a track by track_id from an owned playlist on mobile."""

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    track_id = str((payload or {}).get('track_id') or '').strip()
    if not track_id:
        raise HTTPException(status_code=400, detail='track_id is required')
    row = await asyncio.to_thread(_sync().row_for, track_id)
    if row is None:
        raise HTTPException(status_code=404, detail='Track not found')
    if api.is_liked_playlist(name):
        await api.apply_like(
            row['file'], False, user_id=api.request_user_id(request)
        )
        return {'status': 'ok', 'playlist': name, 'track_id': track_id}
    match = api.require_playlist_owner(name, request)
    actual_name = str(match.get('name') or name).strip()
    ctx = api.library_context()
    try:
        await asyncio.to_thread(
            lambda: api.edit_manual_playlist(
                ctx,
                actual_name,
                remove=[row['file']],
                allow_imported=True,
            )
        )
    except api.ManualPlaylistError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=str(exc)
        ) from exc
    if api.state.playlist_catalog is not None:
        await asyncio.to_thread(
            api.state.playlist_catalog.remove_track_by_filename,
            actual_name,
            Path(row['file']).name,
        )
    if api.state.library_sync is not None:
        await asyncio.to_thread(api.state.library_sync.touch_all)
    invalidate_library_paths_cache()
    return {'status': 'ok', 'playlist': actual_name, 'track_id': track_id}


@router.put('/playlists/{name}/visibility')
async def mobile_set_playlist_visibility(
    name: str,
    request: Request,
) -> dict[str, Any]:
    """Set whether an owned playlist is Public or Private."""

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    is_public = bool((payload or {}).get('public'))
    result = await asyncio.to_thread(
        api.set_playlist_visibility_sync, name, is_public, request
    )
    await api.log_activity(
        request,
        'playlist_visibility',
        f'{name} -> {"public" if result["public"] else "private"}',
    )
    return result


@router.post('/playlists/{name}/clone')
async def mobile_clone_playlist(
    name: str,
    request: Request,
) -> dict[str, Any]:
    """Clone a visible playlist into a new Private playlist owned by the caller."""

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    new_name = str((payload or {}).get('new_name') or '').strip() or None
    result = await asyncio.to_thread(
        api.clone_playlist_sync, name, new_name, request
    )
    await api.log_activity(
        request, 'playlist_clone', f'{name} -> {result["name"]}'
    )
    return result


@router.put('/playlists/{name}/hide')
async def mobile_set_playlist_hidden(
    name: str,
    request: Request,
) -> dict[str, Any]:
    """Hide or unhide a public playlist belonging to another user."""

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    hidden = bool((payload or {}).get('hidden', True))
    return await asyncio.to_thread(
        api.set_playlist_hidden_sync, name, hidden, request
    )


@router.delete('/playlists/{name}')
async def mobile_delete_playlist(
    name: str,
    request: Request,
) -> dict[str, Any]:
    """Delete an owned playlist (or any playlist if admin) on mobile."""

    clean_name = str(name or '').strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail='Playlist name is required')
    if api.is_liked_playlist(clean_name):
        raise HTTPException(
            status_code=400, detail='Liked songs cannot be deleted'
        )
    result = await api._delete_playlist_by_name(request, clean_name)
    await api.log_activity(request, 'playlist_delete', clean_name)
    return result


@router.put('/playlists/{name}/owner')
async def mobile_change_playlist_owner(
    name: str,
    request: Request,
) -> dict[str, Any]:
    """Change ownership of a playlist (admin only) on mobile."""

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    target_user_id = int((payload or {}).get('user_id', 0) or 0)
    result = await asyncio.to_thread(
        api.change_playlist_owner_sync, name, target_user_id, request
    )
    await api.log_activity(
        request, 'playlist_owner_change', f'{name} -> {result.get("owner")}'
    )
    return result


@router.get('/likes')
async def likes(request: Request) -> dict[str, Any]:
    """The liked tracks, most recently liked first: ``{track_ids}``."""

    store = api.state.likes
    if store is None:
        raise HTTPException(status_code=503, detail='Starting up')
    paths = await asyncio.to_thread(store.paths, api.likes_scope(request))
    ids = await asyncio.to_thread(_sync().ids_for_paths, paths)
    return {'track_ids': [ids[p] for p in paths if p in ids]}


@router.put('/likes')
async def set_like(request: Request) -> dict[str, Any]:
    """Like or unlike a track: ``{track_id, liked}``. Idempotent."""

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    track_id = str((payload or {}).get('track_id') or '')
    if not track_id:
        raise HTTPException(status_code=400, detail='track_id is required')
    row = await asyncio.to_thread(_sync().row_for, track_id)
    if row is None:
        raise HTTPException(status_code=404, detail='Track not found')
    liked = bool(payload.get('liked', True))
    result = await api.apply_like(
        row['file'], liked, user_id=api.request_user_id(request)
    )
    await api.log_activity(request, 'like' if liked else 'unlike', row['file'])
    return {'track_id': track_id, 'liked': result['liked']}


# ── Streaming ───────────────────────────────────────────────────────────

# Players (Android's included) want the registered types, not the
# ``audio/x-flac`` some systems' mime tables give.
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


def _download_name(row: dict[str, Any], extension: str) -> str:
    base = Path(row['file']).stem
    return f"attachment; filename*=UTF-8''{quote(base + extension)}"


async def _wait_or_disconnect(
    request: Request, job: asyncio.Future[Path]
) -> Optional[Path]:
    """The job's result, or ``None`` when the client went away first (the
    job is then cancelled, which stops ffmpeg if nobody else waits)."""

    while True:
        done, _pending = await asyncio.wait({job}, timeout=0.5)
        if done:
            return job.result()
        if await request.is_disconnected():
            job.cancel()
            return None


@router.api_route('/tracks/{track_id}/stream', methods=['GET', 'HEAD'])
async def stream(
    track_id: str,
    request: Request,
    fmt: str = Query('original', alias='format'),
    bitrate: int = Query(0),
    download: bool = Query(False),
) -> Response:
    """The track's audio, with HTTP Range support.

    ``format=original`` (default) is the file as it is. ``opus``, ``aac``
    or ``mp3`` with a ``bitrate`` (kbps) is a transcoded copy - unless the
    original is already lossy and no bigger than that, in which case the
    original comes back (``X-Downtify-Transcoded: no``). ``download=true``
    adds a ``Content-Disposition`` for saving the file.
    """

    row, full = _track_path(track_id)
    fmt = fmt.lower()
    headers = {'Cache-Control': _PRIVATE_CACHE}
    if fmt != 'original':
        transcoder = api.state.transcoder
        kbps = normalize_bitrate(bitrate) or 160
        if fmt not in FORMATS:
            raise HTTPException(status_code=400, detail='Unknown format')
        if transcoder is None or not transcoder.available:
            raise HTTPException(
                status_code=501, detail='Transcoding is not available'
            )
        if not serve_original(row['codec'], int(row['bitrate']), kbps):
            job = asyncio.ensure_future(transcoder.get(full, fmt, kbps))
            try:
                target = await _wait_or_disconnect(request, job)
            except TranscodeError as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            if target is None:
                logger.debug(
                    'Stream {}: client left during transcode', track_id
                )
                return Response(status_code=499)
            headers['X-Downtify-Transcoded'] = f'{fmt}/{kbps}'
            if download:
                headers['Content-Disposition'] = _download_name(
                    row, FORMATS[fmt].extension
                )
            return FileResponse(
                target, media_type=FORMATS[fmt].media_type, headers=headers
            )
        headers['X-Downtify-Transcoded'] = 'no'
    if download:
        headers['Content-Disposition'] = _download_name(row, full.suffix)
    return FileResponse(
        full, media_type=audio_media_type(full), headers=headers
    )


@router.api_route('/tracks/{track_id}/cover', methods=['GET', 'HEAD'])
async def cover(
    track_id: str, request: Request, size: str = Query('')
) -> Response:
    """The track's cover: ``size=150|300|600`` (longest side, px) or full
    size when omitted. Cached on the server, ETag for conditional GETs."""

    _row, full = _track_path(track_id)
    thumbs = api.state.cover_thumbs
    if thumbs is None:
        raise HTTPException(status_code=503, detail='Starting up')
    found = await asyncio.to_thread(thumbs.get, full, normalize_size(size))
    if found is None:
        raise HTTPException(status_code=404, detail='No cover')
    data, mime, etag = found
    headers = {'ETag': etag, 'Cache-Control': _PRIVATE_CACHE}
    if request.headers.get('if-none-match') == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=data, media_type=mime, headers=headers)


# ── Signed URLs ─────────────────────────────────────────────────────────

_SIGNABLE = (
    '/api/v1/tracks/',
    '/downloads/',
    '/media/',
    '/cover',
    '/playlist-cover',
    '/api/stream/',
)


@router.post('/sign')
async def sign(request: Request) -> dict[str, Any]:
    """Signed URLs for players that can't send auth headers (a Cast
    receiver): ``{items: [{path, params}], ttl}`` ->
    ``{urls: [...], expires_at}``. For paired apps and signed-in web sessions,
    and only for audio and cover paths; ``ttl`` is seconds (default 1 h, at most 24 h).
    """

    principal: Optional[Principal] = (request.scope.get('state') or {}).get(
        'principal'
    )
    if principal is None:
        raise HTTPException(
            status_code=401, detail='Sign in required'
        )
    device_id = principal.device_id or (f'u_{principal.user_id}' if principal.user_id else 'web')
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    items = (payload or {}).get('items')
    if not isinstance(items, list) or not items or len(items) > 500:
        raise HTTPException(status_code=400, detail='items is required')
    try:
        ttl = int(payload.get('ttl') or SIGNED_URL_DEFAULT_TTL)
    except (TypeError, ValueError):
        ttl = SIGNED_URL_DEFAULT_TTL
    ttl = max(60, min(ttl, SIGNED_URL_MAX_TTL))
    signer = api.state.auth.signer if api.state.auth else None
    if signer is None:
        raise HTTPException(status_code=503, detail='Starting up')
    urls = []
    for item in items:
        path = str((item or {}).get('path') or '')
        params = (item or {}).get('params') or {}
        if not path.startswith(_SIGNABLE) or '..' in path:
            raise HTTPException(
                status_code=400, detail=f'Cannot sign {path!r}'
            )
        if not isinstance(params, dict):
            raise HTTPException(status_code=400, detail='Bad params')
        urls.append(
            signer.sign_url(
                path,
                [(str(k), str(v)) for k, v in params.items()],
                device_id=device_id,
                ttl=ttl,
            )
        )
    return {'urls': urls, 'expires_at': int(time.time()) + ttl}


# ── Shares (Mobile / APK) ──────────────────────────────────────────────


@router.post('/shares')
async def mobile_create_share(request: Request) -> dict[str, Any]:
    """Create a persistent public share link from mobile / APK."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    kind = str(payload.get('kind') or '').strip().lower()
    track_id = str(payload.get('track_id') or '').strip()
    playlist = str(payload.get('playlist') or '').strip()
    target = str(payload.get('target') or '').strip()
    title = str(payload.get('title') or '').strip()

    if track_id:
        kind = 'track'
        row, _ = _track_path(track_id)
        target = row['file']
        if not title:
            title = row.get('title') or Path(target).stem
    elif playlist:
        kind = 'playlist'
        target = playlist
        if not title:
            title = playlist
    elif not target:
        raise HTTPException(
            status_code=400, detail='track_id, playlist, or target is required'
        )

    if not kind:
        kind = 'track'

    user_id = api.request_user_id(request)
    share = api._require_shares().create_share(
        kind=kind, target=target, title=title, user_id=user_id
    )
    base = str(request.base_url).rstrip('/')
    return {
        **share,
        'url': f'{base}/share/{share["id"]}',
    }


@router.get('/shares')
def mobile_list_shares(request: Request) -> list[dict[str, Any]]:
    """List active shares for mobile."""
    user_id = api.request_user_id(request)
    is_admin = api.request_is_admin(request)
    shares = api._require_shares().list_shares(
        user_id=None if is_admin else user_id
    )
    base = str(request.base_url).rstrip('/')
    return [{**s, 'url': f'{base}/share/{s["id"]}'} for s in shares]


@router.delete('/shares/{share_id}')
def mobile_delete_share(share_id: str, request: Request) -> dict[str, Any]:
    """Delete a share from mobile."""
    user_id = api.request_user_id(request)
    is_admin = api.request_is_admin(request)
    deleted = api._require_shares().delete_share(
        share_id,
        user_id=None if is_admin else user_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail='Share not found')
    return {'deleted': True, 'id': share_id}


@router.get('/suggested-mix')
def mobile_suggested_mix(request: Request) -> dict[str, Any]:
    """A personalized daily mix of songs recommended per user for mobile apps."""
    entries = api.entries_for_request(request)
    user_id = api.request_user_id(request)
    mix = api.build_daily_suggested_mix(
        entries=entries,
        user_id=user_id,
        likes_store=api.state.likes,
        activity_log=api.state.activity,
        target_count=25,
    )
    tracks = mix.get('tracks') or []
    paths = [str(t.get('file') or '') for t in tracks if t.get('file')]
    ids: dict[str, str] = {}
    if paths and api.state.library_sync is not None:
        try:
            ids = _sync().ids_for_paths(paths)
        except Exception:
            ids = {}
    enriched_tracks = []
    track_ids = []
    for t in tracks:
        path = str(t.get('file') or '')
        tid = ids.get(path, '')
        if tid:
            track_ids.append(tid)
        enriched_tracks.append({**t, 'track_id': tid})
    return {
        **mix,
        'tracks': enriched_tracks,
        'track_ids': track_ids,
    }


@router.put('/playlists/{name}/rename')
async def mobile_rename_playlist(name: str, request: Request) -> dict[str, Any]:
    """Rename an owned or monitored playlist from mobile."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    new_name = str((payload or {}).get('new_name') or '').strip()
    if not new_name:
        raise HTTPException(status_code=400, detail='new_name is required')
    api.require_playlist_owner(name, request)
    ctx = api.library_context()
    try:
        result = await asyncio.to_thread(
            api.rename_manual_playlist, ctx, name, new_name
        )
    except api.ManualPlaylistError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=str(exc)
        ) from exc
    actual_new_name = str(result.get('name') or new_name)
    if api.state.playlist_catalog is not None:
        try:
            await asyncio.to_thread(
                api.state.playlist_catalog.rename_playlist,
                name,
                actual_new_name,
            )
        except Exception:
            pass
    if api.state.manual_playlist_owners is not None:
        try:
            await asyncio.to_thread(
                api.state.manual_playlist_owners.rename_owner,
                name,
                actual_new_name,
            )
        except Exception:
            pass
    invalidate_library_paths_cache()
    await api.log_activity(request, 'playlist_rename', f'{name} -> {actual_new_name}')
    return {'name': actual_new_name, 'previous': name}


@router.get('/stats')
async def mobile_my_stats(
    request: Request, days: int = Query(30, ge=0, le=36500)
) -> dict[str, Any]:
    """Listening statistics for the signed-in mobile user."""
    from . import account_routes
    return await account_routes.my_listening_stats(request, days=days)


@router.delete('/stats')
async def mobile_clear_my_stats(request: Request) -> dict[str, Any]:
    """Clear listening statistics for the signed-in mobile user."""
    from . import account_routes
    return await account_routes.clear_my_listening_stats(request)


@router.patch('/me')
async def mobile_update_me(request: Request) -> dict[str, Any]:
    """Update profile (username, email, display_name) for the signed-in mobile user."""
    from . import account_routes
    return await account_routes.update_me(request)


@router.put('/me/preferences')
async def mobile_set_preferences(request: Request) -> dict[str, Any]:
    """Update user preferences for the signed-in mobile user."""
    from . import account_routes
    return await account_routes.set_my_preferences(request)


@router.get('/users')
def mobile_list_users(request: Request) -> list[dict[str, Any]]:
    """List user accounts (admins only, for playlist ownership transfer on mobile)."""
    if not api.request_is_admin(request):
        raise HTTPException(status_code=403, detail='Admin role required')
    if api.state.auth is None:
        return []
    return [
        {
            'id': u['id'],
            'username': u['username'],
            'display_name': u.get('display_name') or '',
            'role': u.get('role') or 'user',
        }
        for u in api.state.auth.users.list()
    ]


@router.get('/covers/search')
async def mobile_search_covers(
    request: Request,
    artist: str = Query(''),
    title: str = Query(''),
    track: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    track_id: Optional[str] = Query(None),
) -> dict[str, Any]:
    """Search album/track cover candidates on mobile (supports track_id)."""
    file_path: Optional[str] = None
    if track_id:
        row = await asyncio.to_thread(_sync().row_for, track_id)
        if row:
            file_path = row.get('file')
            if not artist:
                artist = str(row.get('artist') or '')
            if not title:
                title = str(row.get('album') or '')
            if not track:
                track = str(row.get('title') or '')
    return await api.library_album_covers(
        artist=artist,
        title=title,
        track=track,
        query=query,
        file=file_path,
    )


@router.post('/covers/apply')
async def mobile_apply_cover(request: Request) -> dict[str, Any]:
    """Apply and optionally lock album/track cover on mobile (admins only)."""
    if not api.request_is_admin(request):
        raise HTTPException(status_code=403, detail='Admin role required')
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    track_id = str((payload or {}).get('track_id') or '').strip()
    if track_id and not (payload or {}).get('file'):
        row = await asyncio.to_thread(_sync().row_for, track_id)
        if row and row.get('file'):
            payload = {**payload, 'file': row['file']}
            request._body = __import__('json').dumps(payload).encode('utf-8')
    res = await api.library_set_album_cover(request)
    if api.state.library_sync is not None:
        await asyncio.to_thread(api.state.library_sync.touch_all)
    return res


@router.post('/covers/unlock')
async def mobile_unlock_cover(request: Request) -> dict[str, Any]:
    """Unlock album/track cover on mobile (admins only)."""
    if not api.request_is_admin(request):
        raise HTTPException(status_code=403, detail='Admin role required')
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    track_id = str((payload or {}).get('track_id') or '').strip()
    if track_id and not (payload or {}).get('file'):
        row = await asyncio.to_thread(_sync().row_for, track_id)
        if row and row.get('file'):
            payload = {**payload, 'file': row['file']}
            request._body = __import__('json').dumps(payload).encode('utf-8')
    return await api.library_unlock_album_cover(request)


@router.get('/upgrade')
def mobile_upgrade_status(request: Request) -> dict[str, Any]:
    """Current Library Upgrade status (admins only)."""
    if not api.request_is_admin(request):
        raise HTTPException(status_code=403, detail='Admin role required')
    return api.library_upgrade_status()


@router.post('/upgrade/scan')
async def mobile_upgrade_scan(request: Request) -> dict[str, Any]:
    """Scan library for upgrade candidates from mobile (admins only)."""
    if not api.request_is_admin(request):
        raise HTTPException(status_code=403, detail='Admin role required')
    return await api.library_upgrade_scan()


@router.post('/upgrade/start')
async def mobile_upgrade_start(request: Request) -> dict[str, Any]:
    """Start Library Upgrade from mobile (admins only)."""
    if not api.request_is_admin(request):
        raise HTTPException(status_code=403, detail='Admin role required')
    return await api.library_upgrade_start(request)


