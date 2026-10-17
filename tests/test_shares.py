"""Tests for persistent, zero-login public shares and mobile sharing."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main
from downtify import api
from downtify.shares import ShareStore


@pytest.fixture
def share_store(tmp_path):
    return ShareStore(tmp_path / 'test_shares.db')


@pytest.fixture
def app(tmp_path, monkeypatch):
    web = tmp_path / 'web'
    web.mkdir(parents=True, exist_ok=True)
    (web / 'index.html').write_text('<html>Downtify</html>')
    monkeypatch.setattr(main, 'DOWNLOAD_DIR', tmp_path / 'downloads')
    monkeypatch.setattr(main, 'DATABASE_DIR', tmp_path / 'data')
    monkeypatch.setattr(main, 'WEB_GUI_LOCATION', str(web))
    for name in ('auth', 'activity', 'identity', 'downloader', 'settings', 'shares'):
        if hasattr(api.state, name):
            monkeypatch.setattr(api.state, name, getattr(api.state, name))
    return main.build_app()


def test_share_store_crud(share_store):
    # Create track share
    t_share = share_store.create_share(
        kind='track',
        target='Artist - Song.mp3',
        title='Song',
        user_id=1,
    )
    assert t_share['id']
    assert t_share['kind'] == 'track'
    assert t_share['target'] == 'Artist - Song.mp3'
    assert t_share['title'] == 'Song'
    assert t_share['user_id'] == 1

    # Create playlist share
    p_share = share_store.create_share(
        kind='playlist',
        target='Summer Hits',
        title='Summer Hits',
        user_id=2,
    )
    assert p_share['id']
    assert p_share['kind'] == 'playlist'

    # Get by ID
    fetched = share_store.get_share(t_share['id'])
    assert fetched == t_share

    # Non-existent
    assert share_store.get_share('nonexistent') is None

    # List all and filtered
    all_shares = share_store.list_shares()
    assert len(all_shares) == 2

    user1_shares = share_store.list_shares(user_id=1)
    assert len(user1_shares) == 1
    assert user1_shares[0]['id'] == t_share['id']

    # Delete with wrong user_id
    assert not share_store.delete_share(t_share['id'], user_id=2)
    assert share_store.get_share(t_share['id']) is not None

    # Delete with correct user_id
    assert share_store.delete_share(t_share['id'], user_id=1)
    assert share_store.get_share(t_share['id']) is None


def test_public_share_endpoints(app, tmp_path, monkeypatch):
    client = TestClient(app, base_url='http://testserver')

    # Prepare audio file in mock download dir
    dl_dir = tmp_path / 'downloads'
    dl_dir.mkdir(parents=True, exist_ok=True)
    audio_file = dl_dir / 'Test Artist - Great Track.mp3'
    audio_file.write_bytes(b'ID3\x03\x00\x00\x00\x00\x00\x00' + b'\x00' * 100)

    # Attach store to state
    store = ShareStore(tmp_path / 'shares.db')
    api.state.shares = store

    # Mock library context
    from downtify.library_catalog import LibraryContext
    ctx = LibraryContext(download_dir=dl_dir, slskd_dir=None, extra_dirs=[])
    monkeypatch.setattr(api, 'library_context', lambda: ctx)

    # Create a track share
    share = store.create_share(
        kind='track',
        target='Test Artist - Great Track.mp3',
        title='Great Track',
        user_id=1,
    )

    # 1. Inspect share without login (zero auth headers)
    res = client.get(f'/api/share/{share["id"]}')
    assert res.status_code == 200
    data = res.json()
    assert data['id'] == share['id']
    assert data['kind'] == 'track'
    assert data['title'] == 'Great Track'
    assert len(data['tracks']) == 1
    track = data['tracks'][0]
    assert track['index'] == 0
    assert track['title'] == 'Great Track'
    assert track['stream_url'] == f'/api/share/{share["id"]}/stream/0'
    assert track['cover_url'] == f'/api/share/{share["id"]}/cover/0'

    # 2. Stream audio without login
    stream_res = client.get(f'/api/share/{share["id"]}/stream/0')
    assert stream_res.status_code == 200
    assert stream_res.headers['accept-ranges'] == 'bytes'
    assert len(stream_res.content) == len(audio_file.read_bytes())

    # Range request
    range_res = client.get(
        f'/api/share/{share["id"]}/stream/0', headers={'Range': 'bytes=0-9'}
    )
    assert range_res.status_code in (200, 206)

    # Stream out of bounds
    assert client.get(f'/api/share/{share["id"]}/stream/5').status_code == 404

    # 3. Non-existent share
    assert client.get('/api/share/missing12345').status_code == 404


def test_shares_api_authenticated(app, tmp_path, monkeypatch):
    client = TestClient(app, base_url='http://testserver')
    store = ShareStore(tmp_path / 'shares.db')
    api.state.shares = store

    # Sign in as admin
    login_res = client.post(
        '/api/auth/login', json={'username': 'admin', 'password': 'downtify'}
    )
    assert login_res.status_code == 200

    # Create share via POST /api/shares
    create_res = client.post(
        '/api/shares',
        json={'kind': 'track', 'target': 'MySong.mp3', 'title': 'My Song'},
    )
    assert create_res.status_code == 200
    created = create_res.json()
    assert created['id']
    assert 'http://testserver/share/' in created['url']

    # List shares via GET /api/shares
    list_res = client.get('/api/shares')
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 1
    assert any(i['id'] == created['id'] for i in items)

    # Delete share via DELETE /api/shares/{id}
    del_res = client.delete(f'/api/shares/{created["id"]}')
    assert del_res.status_code == 200
    assert del_res.json()['deleted'] is True

    # Check it's gone
    assert store.get_share(created['id']) is None


def test_mobile_shares_endpoints(app, tmp_path):
    client = TestClient(app, base_url='http://testserver')
    store = ShareStore(tmp_path / 'shares.db')
    api.state.shares = store

    # Sign in
    client.post(
        '/api/auth/login', json={'username': 'admin', 'password': 'downtify'}
    )

    # Create share via POST /api/v1/shares
    res = client.post(
        '/api/v1/shares',
        json={'playlist': 'Rock Classics', 'title': 'Rock Classics'},
    )
    assert res.status_code == 200
    data = res.json()
    assert data['id']
    assert data['kind'] == 'playlist'
    assert data['target'] == 'Rock Classics'
    assert 'http://testserver/share/' in data['url']

    # List via GET /api/v1/shares
    list_res = client.get('/api/v1/shares')
    assert list_res.status_code == 200
    assert any(s['id'] == data['id'] for s in list_res.json())

    # Delete via DELETE /api/v1/shares/{id}
    del_res = client.delete(f'/api/v1/shares/{data["id"]}')
    assert del_res.status_code == 200
    assert del_res.json()['deleted'] is True
