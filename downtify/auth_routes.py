"""HTTP routes for signing in, pairing apps and the server's identity.

The rules for who may call what live in :mod:`downtify.auth`
(:data:`downtify.auth.RULES`); these routes only do the work. Listed in
:mod:`downtify.api`'s module docstring with the rest of the API.
"""

from __future__ import annotations

import asyncio
import base64
import json
import secrets
import urllib.parse
from ipaddress import ip_address
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from loguru import logger

from . import api
from .auth import (
    SESSION_COOKIE,
    SESSION_TTL,
    AuthStore,
    Principal,
    client_ip,
    identify,
    open_principal,
    session_cookie,
    trusted_proxies_from_env,
)
from .server_identity import server_info
from .server_port import (
    MAX_PORT,
    MIN_PORT,
    PortError,
    can_restart,
    clean_port,
    in_docker,
    locked_by,
    port_available,
    request_restart,
    resolve_port,
)
from .users import MIN_PASSWORD_LENGTH, ROLE_ADMIN, UserError

router = APIRouter()

_TRUSTED = trusted_proxies_from_env()


def _store() -> AuthStore:
    if api.state.auth is None:
        raise HTTPException(status_code=500, detail='Sign-in is not ready')
    return api.state.auth


def _ip(request: Request) -> str:
    return client_ip(request.scope, _TRUSTED)


def _principal(request: Request) -> Optional[Principal]:
    return (request.scope.get('state') or {}).get('principal')


def _me(request: Request) -> Principal:
    """The signed-in user making *request* (the middleware made sure
    there is one)."""

    principal = _principal(request)
    if principal is None or not principal.user_id:
        raise HTTPException(status_code=401, detail='Sign in required')
    return principal


def _me_admin(request: Request) -> Principal:
    principal = _me(request)
    store = _store()
    user = store.users.get(principal.user_id)
    if not user or user.get('role') != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail='This needs an admin')
    return principal


def _own_device(request: Request, device_id: str) -> dict[str, Any]:
    """*device_id*, when the user may manage it (theirs, or anyone's for
    an admin); else 404."""

    me = _me(request)
    device = _store().get_device(device_id)
    if (
        device is None
        or device.get('revoked_at')
        or (not me.is_admin and int(device['user_id']) != me.user_id)
    ):
        raise HTTPException(status_code=404, detail='Device not found')
    return device


def _is_https(request: Request) -> bool:
    if request.url.scheme == 'https':
        return True
    peer = request.client.host if request.client else ''
    forwarded = request.headers.get('x-forwarded-proto', '')
    return bool(
        _TRUSTED
        and forwarded.lower() == 'https'
        and any(_in(peer, net) for net in _TRUSTED)
    )


def _in(address: str, network: Any) -> bool:
    try:
        return ip_address(address) in network
    except ValueError:
        return False


def _set_session(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        samesite='lax',
        secure=_is_https(request),
        path='/',
    )


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail='Too many attempts. Try again later.',
        headers={'Retry-After': str(retry_after)},
    )


async def _json(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


# ── Server identity ─────────────────────────────────────────────────────


@router.get('/api/server/info')
def get_server_info() -> dict[str, Any]:
    """Who this server is and what it can do - public, for an app to
    check an address before it has credentials."""

    identity = api.state.identity
    if identity is None:
        raise HTTPException(status_code=503, detail='Starting up')
    transcoder = getattr(api.state, 'transcoder', None)
    return server_info(
        identity,
        version=api.state.version,
        require_sign_in=not (api.state.auth and api.state.auth.auth_disabled),
        transcoding=transcoder.capability() if transcoder else None,
    )


@router.patch('/api/server')
async def update_server(request: Request) -> dict[str, Any]:
    """Rename the server (``{name}``) - what apps and LAN discovery show."""

    identity = api.state.identity
    if identity is None:
        raise HTTPException(status_code=503, detail='Starting up')
    payload = await _json(request)
    try:
        await asyncio.to_thread(identity.set_name, payload.get('name'))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    announcer = getattr(api.state, 'discovery', None)
    if announcer is not None:
        await announcer.update(identity.name)
    return get_server_info()


def _port_status() -> dict[str, Any]:
    identity = api.state.identity
    listen = api.state.listen or {}
    saved = identity.port if identity else None
    current = int(listen.get('port') or 0)
    source = str(listen.get('source') or 'default')
    # What the next start would use, with the environment as it is now.
    cli = current if source == '--port' else None
    next_port, next_source = resolve_port(cli, saved)
    return {
        'port': current,
        'saved': saved,
        'next': next_port,
        'locked_by': locked_by(next_source),
        'in_docker': in_docker(),
        'can_restart': can_restart(),
        'min': MIN_PORT,
        'max': MAX_PORT,
    }


@router.get('/api/server/port')
def get_server_port() -> dict[str, Any]:
    """The port the server listens on and the one it starts on next:
    ``{port, saved, next, locked_by, in_docker, can_restart, min, max}``.
    ``locked_by`` names what chose the port instead of Settings
    (``DOWNTIFY_PORT``, ``PORT`` or ``--port``), ``''`` when nothing."""

    if api.state.identity is None:
        raise HTTPException(status_code=503, detail='Starting up')
    return _port_status()


@router.put('/api/server/port')
async def set_server_port(request: Request) -> dict[str, Any]:
    """Choose the port: ``{port, restart}``. Saved for the next start;
    ``restart: true`` restarts the server on it right away (the response
    comes first). ``409`` when the environment or the command line sets
    the port, or the port is taken."""

    identity = api.state.identity
    if identity is None:
        raise HTTPException(status_code=503, detail='Starting up')
    status = _port_status()
    if status['locked_by']:
        raise HTTPException(
            status_code=409,
            detail=f'The port is set by {status["locked_by"]}',
        )
    payload = await _json(request)
    try:
        port = clean_port(payload.get('port'))
    except PortError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    host = str((api.state.listen or {}).get('host') or '0.0.0.0')
    if port != status['port'] and not await asyncio.to_thread(
        port_available, host, port
    ):
        raise HTTPException(
            status_code=409, detail=f'Port {port} is already in use'
        )
    await asyncio.to_thread(identity.set_port, port)
    await api.log_activity(
        request, 'settings_changed', 'port', {'keys': ['port']}
    )
    restart = bool(payload.get('restart')) and port != status['port']
    if restart and can_restart():
        logger.warning('Port changed to {}: restarting', port)
        # After this response has gone out.
        asyncio.get_running_loop().call_later(0.5, request_restart)
    else:
        restart = False
        logger.info('Port {} saved for the next start', port)
    return {**_port_status(), 'restarting': restart}


# ── Status, sign in and out ─────────────────────────────────────────────


@router.get('/api/auth/status')
def auth_status(request: Request) -> dict[str, Any]:
    """Who this request is signed in as.

    ``signed_in`` is what the web app checks before showing the sign-in
    page; ``via`` is ``session`` (a browser), ``device`` (a paired app) or
    ``null``; ``user`` is ``{id, username, role, default_password}``.
    ``notice`` (only while signed out) is the one-time "accounts are
    here" message for a server upgraded from a version without them:
    ``{username, password}`` - ``password`` is ``null`` when the old
    sign-in password was kept.
    """

    store = _store()
    principal, bad = identify(request.scope, store, _ip(request))
    if principal is None and not bad:
        principal = open_principal(store)
    device = None
    user = None
    if principal is not None:
        user = store.users.get(principal.user_id)
        if principal.kind == 'device':
            found = store.get_device(principal.device_id)
            device = {
                'id': principal.device_id,
                'name': (found or {}).get('name'),
            }
    google_client_id = store.users.get_google_client_id()
    return {
        'require_sign_in': not store.auth_disabled,
        'auth_disabled': store.auth_disabled,
        'min_password_length': MIN_PASSWORD_LENGTH,
        'signed_in': principal is not None,
        'via': principal.kind if principal else None,
        'user': user,
        'device': device,
        'notice': None
        if principal or store.auth_disabled
        else store.users.notice(),
        'google_auth_enabled': bool(google_client_id),
        'google_client_id': google_client_id or '',
    }


@router.post('/api/auth/login')
async def login(request: Request, response: Response) -> dict[str, Any]:
    """Sign a browser in: ``{username, password}`` -> ``{signed_in,
    user}``. Rate-limited per address."""

    store = _store()
    if store.auth_disabled:
        raise HTTPException(
            status_code=409,
            detail='Sign-in is turned off (DOWNTIFY_DISABLE_AUTH)',
        )
    ip = _ip(request)
    wait = api.state.login_limiter.retry_after(ip)
    if wait:
        raise _too_many(wait)
    payload = await _json(request)
    username = str(payload.get('username') or '').strip()[:64]
    password = str(payload.get('password') or '')
    user = await asyncio.to_thread(
        store.users.authenticate, username, password
    )
    log = api.state.activity
    if user is None:
        api.state.login_limiter.fail(ip)
        logger.warning('Sign-in: wrong username or password from {}', ip)
        if log is not None:
            await asyncio.to_thread(
                log.record,
                'login_failed',
                username=username,
                summary=username,
                client=api.client_label(request, None),
                ip=ip,
            )
        raise HTTPException(
            status_code=401, detail='Wrong username or password'
        )
    api.state.login_limiter.reset(ip)
    token = await asyncio.to_thread(
        store.create_session,
        user['id'],
        ip,
        request.headers.get('user-agent', ''),
    )
    await asyncio.to_thread(store.users.record_login, user['id'], ip)
    if user['role'] == ROLE_ADMIN:
        # An admin has seen the server with accounts: the notice is done.
        await asyncio.to_thread(store.users.clear_notice)
    if log is not None:
        await asyncio.to_thread(
            log.record,
            'login',
            user_id=user['id'],
            username=user['username'],
            client=api.client_label(request, None),
            ip=ip,
        )
    _set_session(response, request, token)
    return {'signed_in': True, 'user': user}


@router.post('/api/auth/signup')
async def signup(request: Request, response: Response) -> dict[str, Any]:
    """Register a new user account: {username, password, email, display_name}."""
    store = api.state.auth
    if store is None or store.auth_disabled:
        raise HTTPException(
            status_code=409,
            detail='Sign-in is turned off (DOWNTIFY_DISABLE_AUTH)',
        )
    ip = _ip(request)
    wait = api.state.login_limiter.retry_after(ip)
    if wait:
        raise _too_many(wait)
    payload = await _json(request)
    username = str(payload.get('username') or '').strip()
    password = str(payload.get('password') or '')
    email = str(payload.get('email') or '').strip() or None
    display_name = str(
        payload.get('display_name') or payload.get('name') or ''
    ).strip()
    try:
        user = await asyncio.to_thread(
            store.users.sign_up,
            username=username or None,
            password=password,
            email=email,
            display_name=display_name,
        )
    except UserError as exc:
        api.state.login_limiter.fail(ip)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    api.state.login_limiter.reset(ip)
    token = await asyncio.to_thread(
        store.create_session,
        user['id'],
        ip,
        request.headers.get('user-agent', ''),
    )
    await asyncio.to_thread(store.users.record_login, user['id'], ip)
    log = api.state.activity
    if log is not None:
        await asyncio.to_thread(
            log.record,
            'user_created',
            user_id=user['id'],
            username=user['username'],
            summary=f"Signed up ({user['username']})",
            client=api.client_label(request, None),
            ip=ip,
        )
    _set_session(response, request, token)
    return {'signed_in': True, 'user': user}


@router.post('/api/auth/google')
async def google_auth(request: Request, response: Response) -> dict[str, Any]:
    """Authenticate or register via Google OAuth.
    Accepts { credential } (Google ID Token) or { google_id, email, name }.
    """
    store = api.state.auth
    if store is None or store.auth_disabled:
        raise HTTPException(
            status_code=409,
            detail='Sign-in is turned off (DOWNTIFY_DISABLE_AUTH)',
        )
    ip = _ip(request)
    payload = await _json(request)
    credential = str(payload.get('credential') or '').strip()
    google_id = str(payload.get('google_id') or payload.get('sub') or '').strip()
    email = str(payload.get('email') or '').strip()
    name = str(payload.get('name') or payload.get('display_name') or '').strip()

    if credential:
        try:
            claims = None
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    token_info_resp = await client.get(
                        f'https://oauth2.googleapis.com/tokeninfo?id_token={credential}'
                    )
                    if token_info_resp.status_code == 200:
                        claims = token_info_resp.json()
            except Exception:
                pass

            if not claims:
                parts = credential.split('.')
                if len(parts) >= 2:
                    padded = parts[1] + '=' * (-len(parts[1]) % 4)
                    claims = json.loads(base64.urlsafe_b64decode(padded))

            if claims:
                google_id = str(claims.get('sub') or google_id)
                email = str(claims.get('email') or email)
                name = str(claims.get('name') or claims.get('given_name') or name)
        except Exception as exc:
            logger.warning('Failed to decode or verify Google credential: {}', exc)
            raise HTTPException(
                status_code=400, detail='Invalid Google token'
            ) from exc

    if not google_id or not email:
        raise HTTPException(
            status_code=400,
            detail='Google authentication requires valid account ID and email',
        )

    try:
        user = await asyncio.to_thread(
            store.users.authenticate_google,
            google_id=google_id,
            email=email,
            display_name=name,
        )
    except UserError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = await asyncio.to_thread(
        store.create_session,
        user['id'],
        ip,
        request.headers.get('user-agent', ''),
    )
    await asyncio.to_thread(store.users.record_login, user['id'], ip)
    log = api.state.activity
    if log is not None:
        await asyncio.to_thread(
            log.record,
            'login',
            user_id=user['id'],
            username=user['username'],
            summary=f"Google sign-in ({user['username']})",
            client=api.client_label(request, None),
            ip=ip,
        )
    _set_session(response, request, token)
    return {'signed_in': True, 'user': user}


@router.get('/api/auth/google/login')
def google_login(request: Request) -> Response:
    """Redirect to Google's OAuth 2.0 authorization page."""
    store = _store()
    if store.auth_disabled:
        raise HTTPException(
            status_code=409,
            detail='Sign-in is turned off (DOWNTIFY_DISABLE_AUTH)',
        )
    client_id = store.users.get_google_client_id()
    if not client_id:
        raise HTTPException(
            status_code=400,
            detail='Google Sign-In is not configured on this server.',
        )

    base_url = str(request.base_url).rstrip('/')
    if _is_https(request) and base_url.startswith('http://'):
        base_url = 'https://' + base_url[7:]
    redirect_uri = f'{base_url}/api/auth/google/callback'

    state = secrets.token_urlsafe(24)
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'prompt': 'select_account',
    }
    url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(params)
    resp = RedirectResponse(url, status_code=303)
    resp.set_cookie(
        'downtify_oauth_state',
        state,
        max_age=600,
        httponly=True,
        samesite='lax',
        secure=_is_https(request),
        path='/',
    )
    return resp


@router.get('/api/auth/google/callback')
async def google_callback(
    request: Request,
    response: Response,
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
) -> Response:
    """OAuth 2.0 callback handling after user signs in with Google."""
    store = _store()
    if error:
        logger.warning('Google OAuth returned error: {}', error)
        return RedirectResponse(f'/?error={urllib.parse.quote(error)}', status_code=303)
    if not code:
        return RedirectResponse('/?error=missing_code', status_code=303)

    client_id = store.users.get_google_client_id()
    client_secret = store.users.get_google_client_secret()

    base_url = str(request.base_url).rstrip('/')
    if _is_https(request) and base_url.startswith('http://'):
        base_url = 'https://' + base_url[7:]
    redirect_uri = f'{base_url}/api/auth/google/callback'

    token_url = 'https://oauth2.googleapis.com/token'
    data = {
        'code': code,
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }
    if client_secret:
        data['client_secret'] = client_secret

    userinfo: dict[str, Any] = {}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(token_url, data=data)
            if token_resp.status_code != 200:
                logger.error('Google token exchange error: {}', token_resp.text)
                return RedirectResponse('/?error=token_exchange_failed', status_code=303)
            token_json = token_resp.json()
            access_token = token_json.get('access_token')
            id_token = token_json.get('id_token')

            if access_token:
                userinfo_resp = await client.get(
                    'https://www.googleapis.com/oauth2/v3/userinfo',
                    headers={'Authorization': f'Bearer {access_token}'},
                )
                if userinfo_resp.status_code == 200:
                    userinfo = userinfo_resp.json()

            if not userinfo and id_token:
                parts = id_token.split('.')
                if len(parts) >= 2:
                    padded = parts[1] + '=' * (-len(parts[1]) % 4)
                    userinfo = json.loads(base64.urlsafe_b64decode(padded))
    except Exception as exc:
        logger.error('Failed to communicate with Google during OAuth callback: {}', exc)
        return RedirectResponse('/?error=google_auth_failed', status_code=303)

    google_id = str(userinfo.get('sub') or '').strip()
    email = str(userinfo.get('email') or '').strip()
    name = str(userinfo.get('name') or userinfo.get('given_name') or '').strip()

    if not google_id or not email:
        logger.error('Google userinfo missing sub or email: {}', userinfo)
        return RedirectResponse('/?error=google_missing_profile', status_code=303)

    try:
        user = await asyncio.to_thread(
            store.users.authenticate_google,
            google_id=google_id,
            email=email,
            display_name=name,
        )
    except UserError as exc:
        logger.warning('Failed to authenticate Google user: {}', exc)
        return RedirectResponse(f'/?error={urllib.parse.quote(str(exc))}', status_code=303)

    ip = _ip(request)
    session_token = await asyncio.to_thread(
        store.create_session,
        user['id'],
        ip,
        request.headers.get('user-agent', ''),
    )
    await asyncio.to_thread(store.users.record_login, user['id'], ip)

    log = api.state.activity
    if log is not None:
        await asyncio.to_thread(
            log.record,
            'login',
            user_id=user['id'],
            username=user['username'],
            summary=f"Google sign-in ({user['username']})",
            client=api.client_label(request, None),
            ip=ip,
        )

    redirect = RedirectResponse('/', status_code=303)
    _set_session(redirect, request, session_token)
    return redirect


@router.get('/api/auth/google/config')
def get_google_config(request: Request) -> dict[str, Any]:
    """Retrieve Google OAuth configuration (admins only)."""
    _me_admin(request)
    store = _store()
    base_url = str(request.base_url).rstrip('/')
    if _is_https(request) and base_url.startswith('http://'):
        base_url = 'https://' + base_url[7:]
    client_id = store.users.get_google_client_id()
    secret = store.users.get_google_client_secret()
    return {
        'client_id': client_id,
        'has_secret': bool(secret),
        'redirect_uri': f'{base_url}/api/auth/google/callback',
        'javascript_origin': base_url,
    }


@router.put('/api/auth/google/config')
async def set_google_config(request: Request) -> dict[str, Any]:
    """Update Google OAuth configuration (admins only)."""
    _me_admin(request)
    store = _store()
    payload = await _json(request)
    client_id = str(payload.get('client_id') or '').strip()
    client_secret = str(payload.get('client_secret') or '').strip()

    await asyncio.to_thread(store.users.set_config, 'google_client_id', client_id or None)
    if 'client_secret' in payload:
        await asyncio.to_thread(
            store.users.set_config,
            'google_client_secret',
            client_secret or None,
        )
    return get_google_config(request)


@router.post('/api/auth/logout')
async def logout(request: Request, response: Response) -> dict[str, Any]:
    """End this browser's session (a no-op for one that has none)."""

    token = session_cookie(request.scope)
    store = api.state.auth
    if token and store is not None:
        user = await asyncio.to_thread(store.session_user, token)
        await asyncio.to_thread(store.end_session, token)
        log = api.state.activity
        if user is not None and log is not None:
            await asyncio.to_thread(
                log.record,
                'logout',
                user_id=user['id'],
                username=user['username'],
                client=api.client_label(request, None),
                ip=_ip(request),
            )
    response.delete_cookie(SESSION_COOKIE, path='/')
    return {'signed_in': False}


# ── Paired devices ──────────────────────────────────────────────────────


@router.get('/api/auth/devices')
def list_devices(request: Request) -> list[dict[str, Any]]:
    """The user's paired devices - everyone's for an admin (each with
    ``user_id`` and ``username``)."""

    me = _me(request)
    return _store().list_devices(None if me.is_admin else me.user_id)


@router.patch('/api/auth/devices/{device_id}')
async def rename_device(device_id: str, request: Request) -> dict[str, Any]:
    store = _store()
    _own_device(request, device_id)
    payload = await _json(request)
    if not await asyncio.to_thread(
        store.rename_device, device_id, str(payload.get('name') or '')
    ):
        raise HTTPException(status_code=404, detail='Device not found')
    return store.get_device(device_id) or {}


@router.delete('/api/auth/devices/{device_id}')
async def revoke_device(device_id: str, request: Request) -> dict[str, Any]:
    """Unpair a device: its token and signed URLs stop working and its
    WebSocket is closed."""

    store = _store()
    device = _own_device(request, device_id)
    if not await asyncio.to_thread(store.revoke_device, device_id):
        raise HTTPException(status_code=404, detail='Device not found')
    await api.state.connections.close_device(device_id)
    await api.log_activity(
        request,
        'device_unpaired',
        str(device.get('name') or device_id),
        {'device_id': device_id, 'owner': device.get('username')},
    )
    logger.info('Unpaired device {}', device_id)
    return {'id': device_id, 'revoked': True}


@router.post('/api/auth/revoke-all')
async def revoke_all(response: Response) -> dict[str, Any]:
    """Sign out everything: every user's devices and browsers (this one
    too) and every signed URL. Admins only."""

    await asyncio.to_thread(_store().revoke_everything)
    await api.state.connections.close_device('')
    for user in await asyncio.to_thread(_store().users.list):
        await api.state.connections.close_user(user['id'])
    response.delete_cookie(SESSION_COOKIE, path='/')
    logger.warning('Signed out every device and browser')
    return {'revoked': True}


# ── Pairing ─────────────────────────────────────────────────────────────


def _own_pairing(request: Request, pairing_id: str) -> None:
    me = _me(request)
    owner = api.state.pairing.owner(pairing_id)
    if owner is not None and owner != me.user_id and not me.is_admin:
        raise HTTPException(status_code=404, detail='Pairing not found')


@router.post('/api/auth/pairing')
def start_pairing(request: Request) -> dict[str, Any]:
    """Start pairing an app to the signed-in user's account:
    ``{pairing_id, code, expires_in}``. The page shows the code (and a
    QR code carrying it) and follows the pairing with
    ``GET /api/auth/pairing/{pairing_id}`` or the ``device_paired``
    WebSocket message."""

    _store()
    return api.state.pairing.create(_me(request).user_id)


@router.get('/api/auth/pairing/{pairing_id}')
def pairing_status(pairing_id: str, request: Request) -> dict[str, Any]:
    _own_pairing(request, pairing_id)
    return api.state.pairing.status(pairing_id)


@router.delete('/api/auth/pairing/{pairing_id}')
def cancel_pairing(pairing_id: str, request: Request) -> dict[str, Any]:
    _own_pairing(request, pairing_id)
    api.state.pairing.cancel(pairing_id)
    return {'cancelled': True}


@router.post('/api/auth/pair')
async def pair(request: Request) -> dict[str, Any]:
    """An app trades a pairing code for its device token:
    ``{code, device_name, platform}`` -> ``{token, device, server,
    user}``. The device belongs to the user who showed the code.

    Public and rate-limited per address; a code works once and for five
    minutes. The token is shown here once and never stored.
    """

    store = _store()
    ip = _ip(request)
    wait = api.state.pair_limiter.retry_after(ip)
    if wait:
        raise _too_many(wait)
    payload = await _json(request)
    pairing_id = api.state.pairing.claim(payload.get('code'))
    owner = (
        api.state.pairing.owner(pairing_id) if pairing_id is not None else None
    )
    user = store.users.get(owner) if owner else None
    if pairing_id is None or user is None:
        api.state.pair_limiter.fail(ip)
        logger.warning('Pairing: wrong or expired code from {}', ip)
        raise HTTPException(
            status_code=401, detail='Wrong or expired pairing code'
        )
    device, token = await asyncio.to_thread(
        store.create_device,
        str(payload.get('device_name') or ''),
        str(payload.get('platform') or ''),
        ip,
        user['id'],
    )
    api.state.pairing.complete(pairing_id, device)
    await api.state.connections.send_user(
        user['id'],
        {'type': 'device_paired', 'pairing_id': pairing_id, 'device': device},
    )
    log = api.state.activity
    if log is not None:
        await asyncio.to_thread(
            log.record,
            'device_paired',
            user_id=user['id'],
            username=user['username'],
            summary=str(device.get('name') or ''),
            detail={'device_id': device.get('id')},
            client=str(device.get('name') or ''),
            ip=ip,
        )
    logger.info('Paired device {} ({})', device.get('name'), device.get('id'))
    identity = api.state.identity
    return {
        'token': token,
        'device': {'id': device.get('id'), 'name': device.get('name')},
        'server': {
            'server_id': identity.server_id if identity else '',
            'name': identity.name if identity else '',
        },
        'user': {'username': user['username'], 'role': user['role']},
    }


@router.post('/api/auth/ws-ticket')
def ws_ticket(request: Request) -> dict[str, Any]:
    """A single-use ticket (60 s) for opening the WebSocket as
    ``/api/ws?client_id=…&ticket=…``, for a client that can't send an
    ``Authorization`` header with the handshake."""

    return {'ticket': api.state.ws_tickets.create(_me(request))}
