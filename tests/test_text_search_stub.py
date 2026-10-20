import zlib

from downtify import api, providers
from downtify.providers import (
    _parse_text_search_query,
    song_stub_from_text_query,
    spotify_open_url,
)


def test_parse_artist_dash_title():
    artists, title = _parse_text_search_query('Daft Punk - One More Time')
    assert artists == ['Daft Punk']
    assert title == 'One More Time'


def test_song_stub_from_text_query():
    stub = song_stub_from_text_query('Daft Punk - One More Time')
    assert stub is not None
    assert stub['name'] == 'One More Time'
    assert stub['artists'] == ['Daft Punk']
    assert stub['source'] == 'text_search'
    # The id keys the download queue, so it must not change between runs.
    assert stub['song_id'] == 'search-%08x' % zlib.crc32(
        b'Daft Punk - One More Time'
    )
    assert stub['spotify_url'] == (
        'https://open.spotify.com/search/Daft%20Punk%20One%20More%20Time'
    )


def test_spotify_open_url_uses_existing_spotify_link():
    song = {
        'name': 'Track',
        'artists': ['A'],
        'url': 'https://open.spotify.com/track/abc123',
    }
    assert spotify_open_url(song) == 'https://open.spotify.com/track/abc123'


def test_spotify_open_url_builds_search_for_youtube_rows():
    song = {
        'name': 'One More Time',
        'artists': ['Daft Punk'],
        'url': 'https://music.youtube.com/watch?v=xyz',
    }
    assert spotify_open_url(song) == (
        'https://open.spotify.com/search/Daft%20Punk%20One%20More%20Time'
    )


def test_search_endpoint_prioritizes_slskd_when_audio_provider_number_one(monkeypatch):
    monkeypatch.setattr(
        providers,
        'search_songs',
        lambda query, limit=20: [
            {
                'song_id': 'yt_result_1',
                'name': 'One More Time',
                'artists': ['Daft Punk'],
                'source': 'youtube',
            }
        ],
    )
    # Configure slskd as #1 priority
    monkeypatch.setattr(
        api.state,
        'settings',
        {
            'audio_providers': ['slskd', 'youtube-music'],
            'slskd': {'enabled': True, 'base_url': 'http://slskd:5030', 'api_key': 'key'},
        },
    )

    results = api.search_endpoint('Daft Punk - One More Time')
    assert len(results) == 2
    # The first item should be the Soulseek direct stub
    assert results[0]['source'] == 'text_search'
    assert results[0]['name'] == 'One More Time'
    assert results[0]['artists'] == ['Daft Punk']
    # The second item is the YouTube Music search result
    assert results[1]['source'] == 'youtube'
    assert results[1]['song_id'] == 'yt_result_1'


def test_search_endpoint_does_not_prepend_slskd_when_not_priority_one(monkeypatch):
    monkeypatch.setattr(
        providers,
        'search_songs',
        lambda query, limit=20: [
            {
                'song_id': 'yt_result_1',
                'name': 'One More Time',
                'artists': ['Daft Punk'],
                'source': 'youtube',
            }
        ],
    )
    # YouTube Music is #1 priority
    monkeypatch.setattr(
        api.state,
        'settings',
        {
            'audio_providers': ['youtube-music', 'slskd'],
            'slskd': {'enabled': True, 'base_url': 'http://slskd:5030', 'api_key': 'key'},
        },
    )

    results = api.search_endpoint('Daft Punk - One More Time')
    assert len(results) == 1
    assert results[0]['source'] == 'youtube'
    assert results[0]['song_id'] == 'yt_result_1'
