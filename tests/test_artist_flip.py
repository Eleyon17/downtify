"""Tests for the Now Playing flip tile's artist overview
(downtify/artist_flip.py and ``GET /api/artists/overview``). Offline:
every YouTube Music call is faked."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from downtify import api, artist_flip, artist_profile, providers


@pytest.fixture(autouse=True)
def _fresh_cache():
    artist_flip.clear_cache()
    yield
    artist_flip.clear_cache()


@pytest.fixture
def fake_ytm(monkeypatch):
    calls: dict[str, int] = {'resolve': 0, 'info': 0, 'songs': 0, 'albums': 0}
    data: dict[str, Any] = {
        'channel': 'UCabc',
        'description': 'A band from somewhere.',
        'songs': [{'name': f'Song {i}'} for i in range(15)],
        'albums': [{'name': 'Album A'}, {'name': 'Album B'}],
    }

    def resolve(name: str) -> str | None:
        calls['resolve'] += 1
        return data['channel']

    def info(channel_id: str) -> dict[str, Any]:
        calls['info'] += 1
        return {
            'name': 'The Band',
            'cover_url': 'https://img/x.jpg',
            'description': data['description'],
        }

    def songs(channel_id: str) -> list[dict[str, Any]]:
        calls['songs'] += 1
        return data['songs']

    def albums(channel_id: str) -> list[dict[str, Any]]:
        calls['albums'] += 1
        return data['albums']

    monkeypatch.setattr(providers, 'resolve_artist_id', resolve)
    monkeypatch.setattr(providers, 'artist_info_from_channel_id', info)
    monkeypatch.setattr(providers, 'artist_top_songs_from_channel_id', songs)
    monkeypatch.setattr(providers, 'artist_top_albums_from_channel_id', albums)
    return calls, data


def test_overview_uses_youtube_bio_and_caps_lists(tmp_path: Path, fake_ytm):
    calls, _ = fake_ytm
    result = artist_flip.artist_overview('the band', tmp_path)

    assert result['channel_id'] == 'UCabc'
    assert result['url'] == 'https://music.youtube.com/channel/UCabc'
    assert result['name'] == 'The Band'
    assert result['bio'] == 'A band from somewhere.'
    assert result['bio_source'] == artist_flip.BIO_SOURCE_YOUTUBE
    assert len(result['top_songs']) == artist_flip.TOP_SONGS_LIMIT
    assert [a['name'] for a in result['top_albums']] == ['Album A', 'Album B']
    assert calls == {'resolve': 1, 'info': 1, 'songs': 1, 'albums': 1}


def test_overview_is_cached_by_normalized_name(tmp_path: Path, fake_ytm):
    calls, _ = fake_ytm
    artist_flip.artist_overview('The Band', tmp_path, now=1000.0)
    artist_flip.artist_overview('  the   BAND ', tmp_path, now=1001.0)
    assert calls['info'] == 1

    later = 1000.0 + artist_flip.CACHE_TTL_SECONDS + 1
    artist_flip.artist_overview('The Band', tmp_path, now=later)
    assert calls['info'] == 2


def test_saved_youtube_channel_skips_the_name_lookup(
    tmp_path: Path, fake_ytm, monkeypatch
):
    calls, _ = fake_ytm
    monkeypatch.setattr(
        artist_profile,
        'load_profile',
        lambda d, n: {'bio': '', 'platforms_id': {'youtubemusic': 'UCsaved'}},
    )
    result = artist_flip.artist_overview('The Band', tmp_path)
    assert result['channel_id'] == 'UCsaved'
    assert calls['resolve'] == 0


def test_falls_back_to_saved_profile_bio(tmp_path: Path, fake_ytm, monkeypatch):
    _, data = fake_ytm
    data['description'] = ''
    monkeypatch.setattr(
        artist_profile,
        'load_profile',
        lambda d, n: {'bio': 'From Apple Music.', 'platforms_id': {}},
    )
    result = artist_flip.artist_overview('The Band', tmp_path)
    assert result['bio'] == 'From Apple Music.'
    assert result['bio_source'] == artist_flip.BIO_SOURCE_PROFILE


def test_unknown_artist_is_empty_and_not_cached(tmp_path: Path, fake_ytm):
    calls, data = fake_ytm
    data['channel'] = None
    result = artist_flip.artist_overview('Nobody', tmp_path)
    assert not result['channel_id']
    assert result['top_songs'] == []
    assert result['top_albums'] == []
    assert calls['info'] == 0

    artist_flip.artist_overview('Nobody', tmp_path)
    assert calls['resolve'] == 2


def test_one_failing_shelf_does_not_sink_the_rest(
    tmp_path: Path, fake_ytm, monkeypatch
):
    def boom(channel_id: str) -> list[dict[str, Any]]:
        raise RuntimeError('YouTube Music is down')

    monkeypatch.setattr(providers, 'artist_top_albums_from_channel_id', boom)
    result = artist_flip.artist_overview('The Band', tmp_path)
    assert result['top_albums'] == []
    assert result['bio'] == 'A band from somewhere.'
    assert result['top_songs']


def test_endpoint_passes_the_download_dir(monkeypatch, tmp_path: Path):
    seen: dict[str, Any] = {}

    def fake(name: str, download_dir: Path) -> dict[str, Any]:
        seen['args'] = (name, download_dir)
        return {'name': name}

    monkeypatch.setattr(artist_flip, 'artist_overview', fake)
    monkeypatch.setattr(api, '_artist_profile_download_dir', lambda: tmp_path)
    assert api.artist_overview_endpoint(name='Band') == {'name': 'Band'}
    assert seen['args'] == ('Band', tmp_path)


def test_overview_covers_crossfill_and_fallback(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(providers, 'resolve_artist_id', lambda name: 'UC123')
    monkeypatch.setattr(
        providers,
        'artist_info_from_channel_id',
        lambda cid: {'name': 'Artist', 'cover_url': '', 'description': 'Bio'},
    )
    monkeypatch.setattr(
        providers,
        'artist_top_songs_from_channel_id',
        lambda cid: [
            {'name': 'Song 1', 'album_name': 'Album 1', 'cover_url': ''},
            {'name': 'Song 2', 'album_name': 'Album 2', 'song_id': 'vid123', 'cover_url': ''},
        ],
    )
    monkeypatch.setattr(
        providers,
        'artist_top_albums_from_channel_id',
        lambda cid: [
            {'name': 'Album 1', 'cover_url': 'https://img/album1.jpg'},
            {'name': 'Album 2', 'cover_url': ''},
        ],
    )

    result = artist_flip.artist_overview('Artist', tmp_path)

    # Song 1 got cover from Album 1 matching by name
    assert result['top_songs'][0]['cover_url'] == 'https://img/album1.jpg'
    # Song 2 got cover from YouTube video id fallback
    assert result['top_songs'][1]['cover_url'] == 'https://i.ytimg.com/vi/vid123/hqdefault.jpg'
    # Album 2 got crossfilled cover from Song 2
    assert result['top_albums'][1]['cover_url'] == 'https://i.ytimg.com/vi/vid123/hqdefault.jpg'
    # Overall cover resolved from available album cover
    assert result['cover_url'] == 'https://img/album1.jpg'


def test_artist_top_albums_falls_back_to_singles(monkeypatch):
    class FakeYTM:
        def get_artist(self, channel_id):
            return {
                'name': 'Indie Artist',
                'albums': {'results': []},
                'singles': {
                    'results': [
                        {
                            'title': 'Hit Single',
                            'browseId': 'MPREb_single1',
                            'thumbnails': [{'url': 'https://img/single1.jpg'}],
                            'year': '2024',
                        }
                    ]
                },
            }

    monkeypatch.setattr(providers, '_ytm', lambda: FakeYTM())
    albums = providers.artist_top_albums_from_channel_id('UC_indie')
    assert len(albums) == 1
    assert albums[0]['name'] == 'Hit Single'
    assert albums[0]['cover_url'] == 'https://img/single1.jpg'
    assert albums[0]['release_type'] == 'Single'


