"""Tests for lyrics translation, offline caching, and language detection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from downtify.lyrics import read_track_lyrics
from downtify.lyrics_translation import (
    LyricsTranslationStore,
    detect_lyrics_language,
    get_or_translate_lyrics,
    normalize_lang_code,
    read_cached_translation,
    translate_lines,
    write_cached_translation,
)


def test_normalize_lang_code():
    assert normalize_lang_code('en') == 'en'
    assert normalize_lang_code('EN_US') == 'en'
    assert normalize_lang_code('es-ES') == 'es'
    assert normalize_lang_code('pt-br') == 'pt-BR'
    assert normalize_lang_code('pt_BR') == 'pt-BR'
    assert normalize_lang_code('zh-CN') == 'zh'
    assert normalize_lang_code('') == 'en'


def test_detect_lyrics_language():
    spanish = 'Hola mi amor, te quiero con todo mi corazón. Por la noche...'
    english = 'The harbor lights are blinking out one by one into the night'
    french = 'Bonjour mon ami, je suis dans la rue avec vous'
    german = 'Guten Tag und auf Wiedersehen, wir sind zusammen'
    cjk = '君の笑顔をずっと見ていたい'
    cyrillic = 'Привет, как дела, это прекрасный день'

    assert detect_lyrics_language(spanish) == 'es'
    assert detect_lyrics_language(english) == 'en'
    assert detect_lyrics_language(french) == 'fr'
    assert detect_lyrics_language(german) == 'de'
    assert detect_lyrics_language(cjk) in {'ja', 'zh'}
    assert detect_lyrics_language(cyrillic) in {'ru', 'bg', 'uk'}


def test_translate_same_language_returns_same():
    lines = ['Hello world', 'Good morning']
    out = translate_lines(lines, 'en', 'en')
    assert out == lines


def test_translate_offline_dictionary():
    # Spanish words in dictionary
    lines = ['hola amigo', 'gracias mi amor']
    out = translate_lines(lines, 'es', 'en')
    assert len(out) == 2
    assert 'hello' in out[0].lower() or 'friend' in out[0].lower()
    assert 'thanks' in out[1].lower() or 'love' in out[1].lower()


def test_lyrics_translation_store(tmp_path):
    db_path = tmp_path / 'lyrics_translations.sqlite'
    store = LyricsTranslationStore(db_path)

    store.put('hash123', 'en', 'es', '[00:01.00] translated synced', 'translated plain')
    res = store.get('hash123', 'en')
    assert res is not None
    assert res.plain == 'translated plain'
    assert res.synced == '[00:01.00] translated synced'
    assert res.source_lang == 'es'

    assert store.get('hash123', 'fr') is None


def test_sidecar_translation_cache(tmp_path):
    audio_file = tmp_path / 'song.mp3'
    audio_file.write_bytes(b'fake audio')

    write_cached_translation(
        audio_file,
        target_lang='en',
        source_lang='es',
        synced='[00:01.00] Hello world',
        plain='Hello world',
    )

    cached = read_cached_translation(audio_file, 'en')
    assert cached is not None
    assert cached.plain == 'Hello world'
    assert cached.synced == '[00:01.00] Hello world'
    assert cached.source_lang == 'es'

    # Sidecar .en.lrc must exist
    sidecar_lrc = tmp_path / 'song.en.lrc'
    assert sidecar_lrc.is_file()
    assert '[00:01.00] Hello world' in sidecar_lrc.read_text(encoding='utf-8')


def test_read_track_lyrics_with_target_lang(tmp_path, monkeypatch):
    track = tmp_path / 'despacito.mp3'
    track.write_bytes(b'dummy')
    lrc_file = tmp_path / 'despacito.lrc'
    lrc_content = '[00:10.00] Despacito\n[00:15.00] Quiero respirar tu cuello despacito'
    lrc_file.write_text(lrc_content, encoding='utf-8')

    # Pre-populate offline cache
    write_cached_translation(
        track,
        target_lang='en',
        source_lang='es',
        synced='[00:10.00] Slowly\n[00:15.00] I want to breathe your neck slowly',
        plain='Slowly\nI want to breathe your neck slowly',
    )

    result = read_track_lyrics(track, target_lang='en')
    assert result['synced'] == lrc_content
    assert result['source_lang'] == 'es'
    assert result['target_lang'] == 'en'
    assert '[00:10.00] Slowly' in result['translated_synced']
    assert 'Slowly' in result['translated_plain']
