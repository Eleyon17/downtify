"""Tests for playlist suggestions and adding tracks to playlists."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from downtify.playlist_suggestions import (
    _normalize,
    _sample_seed_tracks,
    resolve_playlist_tracks,
    get_playlist_suggestions,
)
from downtify.library_catalog import LibraryContext


def test_normalize():
    assert _normalize('In The End (Feat. Chester)') == 'in the end'
    assert _normalize('Hotel California - 2013 Remaster') == 'hotel california'
    assert _normalize('Song Name (Deluxe Edition)') == 'song name'
    assert _normalize('Clean Title') == 'clean title'
    assert _normalize('') == ''


def test_sample_seed_tracks():
    tracks = [
        ('Artist A', 'Song 1'),
        ('Artist B', 'Song 2'),
        ('Artist C', 'Song 3'),
        ('Artist D', 'Song 4'),
        ('Artist E', 'Song 5'),
        ('Artist F', 'Song 6'),
    ]
    seeds = _sample_seed_tracks(tracks, max_seeds=4)
    assert len(seeds) == 4
    # Check that seeds span the list
    assert seeds[0] == ('Artist A', 'Song 1')
    assert ('Artist F', 'Song 6') in seeds or ('Artist E', 'Song 5') in seeds

    # If <= max_seeds, returns all
    assert _sample_seed_tracks(tracks[:2], max_seeds=4) == tracks[:2]
    assert _sample_seed_tracks([], max_seeds=4) == []


def test_resolve_playlist_tracks_liked(tmp_path):
    likes_store = MagicMock()
    likes_store.paths.return_value = ['Song1.mp3']
    dl_dir = tmp_path / 'downloads'
    dl_dir.mkdir()
    song1 = dl_dir / 'Song1.mp3'
    song1.write_text('dummy')

    with patch('downtify.playlist_suggestions.read_audio_metadata', return_value={'title': 'Loved Song', 'artist': 'Loved Artist'}):
        tracks = resolve_playlist_tracks(
            'Downtify Liked Songs',
            dl_dir,
            likes_store=likes_store,
        )
    assert tracks == [('Loved Artist', 'Loved Song')]


def test_resolve_playlist_tracks_m3u(tmp_path):
    dl_dir = tmp_path / 'downloads'
    dl_dir.mkdir()
    pl_dir = dl_dir / 'Playlists'
    pl_dir.mkdir()
    m3u_file = pl_dir / 'Rock.m3u'
    m3u_file.write_text('#EXTM3U\n../Song1.mp3\n')
    song1 = dl_dir / 'Song1.mp3'
    song1.write_text('dummy')

    with patch('downtify.playlist_suggestions.read_audio_metadata', return_value={'title': 'Rock Anthem', 'artist': 'Rockers'}):
        tracks = resolve_playlist_tracks(
            'Rock',
            dl_dir,
        )
    assert tracks == [('Rockers', 'Rock Anthem')]


def test_get_playlist_suggestions_filtering(tmp_path):
    dl_dir = tmp_path / 'downloads'
    dl_dir.mkdir()

    # Seed tracks in playlist
    seed_tracks = [{'artist': 'Seed Artist', 'title': 'Seed Track'}]

    # Mock provider response
    mock_tracks = [
        {
            'song_id': 'vid-1',
            'name': 'Seed Track',  # Already in playlist: should be excluded!
            'artist': 'Seed Artist',
            'artists': ['Seed Artist'],
            'duration': 200,
            'cover_url': 'http://cover1.jpg',
        },
        {
            'song_id': 'vid-2',
            'name': 'Dismissed Song',  # Will be dismissed: should be excluded!
            'artist': 'Other Artist',
            'artists': ['Other Artist'],
            'duration': 180,
            'cover_url': 'http://cover2.jpg',
        },
        {
            'song_id': 'vid-3',
            'name': 'Great Similar Track',
            'artist': 'Awesome Artist',
            'artists': ['Awesome Artist'],
            'duration': 210,
            'cover_url': 'http://cover3.jpg',
        },
        {
            'song_id': 'vid-4',
            'name': 'Local Library Track',
            'artist': 'Awesome Artist',
            'artists': ['Awesome Artist'],
            'duration': 220,
            'cover_url': 'http://cover4.jpg',
        },
    ]

    mock_track_index = MagicMock()
    mock_track_index.lookup.side_effect = lambda sid: 'Local.mp3' if sid == 'vid-4' else None
    mock_track_index.lookup_song.side_effect = lambda cand: 'Local.mp3' if cand.get('song_id') == 'vid-4' else None

    with patch('downtify.providers.youtube_similar_tracks', return_value={'tracks': mock_tracks}):
        res = get_playlist_suggestions(
            'My Playlist',
            dl_dir,
            seed_tracks=seed_tracks,
            dismissed=['vid-2'],
            track_index=mock_track_index,
            limit=10,
        )

    suggestions = res['suggestions']
    assert len(suggestions) == 2

    s0 = suggestions[0]
    assert s0['song_id'] == 'vid-3'
    assert s0['name'] == 'Great Similar Track'
    assert s0['in_library'] is False

    s1 = suggestions[1]
    assert s1['song_id'] == 'vid-4'
    assert s1['name'] == 'Local Library Track'
    assert s1['in_library'] is True
    assert s1['file'] == 'Local.mp3'


def test_add_track_to_playlist_internal_sync(tmp_path):
    from downtify import api
    from downtify.library_catalog import LibraryContext

    dl_dir = tmp_path / 'downloads'
    dl_dir.mkdir()
    pl_dir = dl_dir / 'Playlists'
    pl_dir.mkdir()

    song_file = dl_dir / 'Artist' / 'Album' / 'Song.mp3'
    song_file.parent.mkdir(parents=True)
    song_file.write_text('dummy audio')

    ctx = LibraryContext(download_dir=dl_dir)

    # 1. Test liked songs
    with patch.object(api, 'library_context', return_value=ctx):
        mock_likes = MagicMock()
        with patch.object(api.state, 'likes', mock_likes):
            res = api.add_track_to_playlist_internal_sync(
                'Downtify Liked Songs',
                'Artist/Album/Song.mp3',
                user_id=1,
            )
            assert res['liked'] is True
            mock_likes.like.assert_called_once_with('Artist/Album/Song.mp3', user_id=1)

    # 2. Test manual playlist
    manual_m3u = pl_dir / 'MyMix.m3u'
    manual_m3u.write_text('#EXTM3U\n#EXTDOWNTIFY:manual\n')

    with patch.object(api, 'library_context', return_value=ctx):
        res = api.add_track_to_playlist_internal_sync(
            'MyMix',
            'Artist/Album/Song.mp3',
            user_id=1,
        )
        assert res['manual'] is True
        assert 'Artist/Album/Song.mp3' in res['files']
