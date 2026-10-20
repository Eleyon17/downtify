"""Lyrics language detection, translation, and offline storage.

Allows Downtify to display a secondary translated row of lyrics in the
player matching the user's account language when lyrics are in another
language. Works fully offline for downloaded music by caching translations
both in a dedicated SQLite database and alongside files as .<lang>.lrc /
.translation.json sidecars.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

import httpx
from loguru import logger

from .sqlite_utils import connect_sqlite

_LRC_STAMP = re.compile(r'\[(\d{1,3}):(\d{1,2}(?:\.\d{1,3})?)\]')
_USER_AGENT = 'Downtify/4.0 (https://github.com/Eleyon17/downtify)'
_TIMEOUT = 8

# Common stop words used for offline language detection
_STOP_WORDS: dict[str, set[str]] = {
    'en': {
        'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
        'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
        'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her',
        'she', 'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there',
        'their', 'what', 'so', 'up', 'out', 'if', 'about', 'who', 'get',
        'which', 'go', 'me', 'when', 'make', 'can', 'like', 'time', 'no',
        'just', 'him', 'know', 'take', 'people', 'into', 'year', 'your',
        'good', 'some', 'could', 'them', 'see', 'other', 'than', 'then',
        'now', 'look', 'only', 'come', 'its', 'over', 'think', 'also',
        'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first',
        'well', 'way', 'even', 'new', 'want', 'because', 'any', 'these',
        'give', 'day', 'most', 'us', 'love', 'baby', 'yeah', 'wanna', 'gonna',
    },
    'es': {
        'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se',
        'las', 'por', 'un', 'para', 'con', 'no', 'una', 'su', 'al', 'lo',
        'como', 'más', 'pero', 'sus', 'le', 'ya', 'o', 'este', 'sí',
        'porque', 'esta', 'entre', 'cuando', 'muy', 'sin', 'sobre', 'también',
        'me', 'hasta', 'hay', 'donde', 'quien', 'desde', 'todo', 'nos',
        'durante', 'todos', 'uno', 'les', 'ni', 'contra', 'otros', 'ese',
        'eso', 'ante', 'ellos', 'e', 'esto', 'mí', 'antes', 'algunos', 'qué',
        'unos', 'yo', 'otro', 'otras', 'otra', 'él', 'tanto', 'esa', 'estos',
        'mucho', 'quienes', 'nada', 'muchos', 'cual', 'poco', 'ella', 'estar',
        'estas', 'algunas', 'algo', 'nosotros', 'mi', 'mis', 'tu', 'tus',
        'te', 'ti', 'amor', 'vida', 'corazón', 'quiero', 'siento', 'noche',
    },
    'fr': {
        'le', 'la', 'les', 'de', 'des', 'du', 'un', 'une', 'et', 'à',
        'en', 'que', 'qui', 'dans', 'pour', 'pas', 'sur', 'ce', 'par',
        'il', 'est', 'sont', 'avec', 'tout', 'faire', 'mais', 'mon', 'ton',
        'son', 'nous', 'vous', 'ils', 'elle', 'ne', 'plus', 'comme', 'je',
        'tu', 'on', 'moi', 'toi', 'lui', 'leur', 'bien', 'si', 'sans', 'dans',
        'au', 'aux', 'cette', 'ces', 'été', 'être', 'avoir', 'amour', 'coeur',
    },
    'pt': {
        'de', 'a', 'o', 'que', 'e', 'do', 'da', 'em', 'um', 'para',
        'com', 'não', 'uma', 'os', 'no', 'se', 'na', 'por', 'mais', 'as',
        'dos', 'como', 'mas', 'foi', 'ao', 'ele', 'das', 'tem', 'à', 'seu',
        'sua', 'ou', 'ser', 'quando', 'muito', 'há', 'nos', 'já', 'está',
        'eu', 'você', 'meu', 'minha', 'teu', 'tua', 'amor', 'vida', 'coração',
    },
    'de': {
        'der', 'die', 'das', 'und', 'in', 'zu', 'den', 'das', 'nicht',
        'von', 'sie', 'ist', 'des', 'sich', 'mit', 'dem', 'dass', 'er',
        'es', 'ein', 'ich', 'auf', 'so', 'eine', 'auch', 'als', 'an',
        'nach', 'wie', 'im', 'für', 'man', 'aber', 'aus', 'durch', 'wenn',
        'nur', 'war', 'noch', 'wir', 'du', 'dich', 'mich', 'liebe', 'herz',
    },
    'it': {
        'di', 'e', 'il', 'la', 'che', 'in', 'un', 'a', 'per', 'una',
        'non', 'si', 'è', 'da', 'sono', 'le', 'con', 'del', 'della', 'dei',
        'delle', 'nel', 'nella', 'io', 'tu', 'lui', 'lei', 'noi', 'voi',
        'loro', 'mi', 'ti', 'ci', 'vi', 'mio', 'mia', 'tuo', 'tua', 'amore',
    },
    'tr': {
        'bir', 've', 'bu', 'da', 'de', 'için', 'ben', 'sen', 'o', 'biz',
        'siz', 'onlar', 'ne', 'kadar', 'var', 'yok', 'gibi', 'daha', 'çok',
        'ama', 'ile', 'bana', 'sana', 'aşk', 'sevgi', 'kalp', 'gözlerin',
    },
    'hu': {
        'a', 'az', 'és', 'hogy', 'nem', 'egy', 'van', 'is', 'meg', 'de',
        'ha', 'mint', 'csak', 'te', 'én', 'ő', 'mi', 'ti', 'ők', 'itt',
        'ott', 'már', 'még', 'volt', 'lesz', 'szerelem', 'szív',
    },
}

# Offline phrase translations for basic fallback
_OFFLINE_DICTIONARY: dict[tuple[str, str], dict[str, str]] = {
    ('es', 'en'): {
        'te amo': 'I love you',
        'te quiero': 'I love you',
        'mi amor': 'my love',
        'corazón': 'heart',
        'vida mía': 'my life',
        'hola': 'hello',
        'adiós': 'goodbye',
        'amigo': 'friend',
        'amiga': 'friend',
        'noche': 'night',
        'día': 'day',
        'siempre': 'always',
        'nunca': 'never',
        'loco': 'crazy',
        'loca': 'crazy',
        'bailar': 'dance',
        'cantar': 'sing',
        'bésame': 'kiss me',
        'dime': 'tell me',
        'sola': 'alone',
        'solo': 'alone',
        'contigo': 'with you',
        'sin ti': 'without you',
    },
    ('en', 'es'): {
        'i love you': 'te amo',
        'my love': 'mi amor',
        'heart': 'corazón',
        'my life': 'mi vida',
        'hello': 'hola',
        'goodbye': 'adiós',
        'friend': 'amigo',
        'night': 'noche',
        'day': 'día',
        'always': 'siempre',
        'never': 'nunca',
        'dance': 'bailar',
        'with you': 'contigo',
        'without you': 'sin ti',
    },
}


def normalize_lang_code(code: Optional[str]) -> str:
    """Normalize language tags like 'en-US' or 'pt-BR' to 'en' or 'pt'."""
    raw = str(code or '').strip().lower()
    if not raw:
        return 'en'
    if '-' in raw:
        prefix, suffix = raw.split('-', 1)
        if prefix == 'pt' and suffix == 'br':
            return 'pt-BR'
        return prefix
    if '_' in raw:
        prefix, suffix = raw.split('_', 1)
        if prefix == 'pt' and suffix == 'br':
            return 'pt-BR'
        return prefix
    return raw


def detect_lyrics_language(text: str) -> str:
    """Detect the language of lyrics text offline using character sets & word frequencies."""
    clean = _LRC_STAMP.sub('', text)
    if not clean.strip():
        return 'en'

    # Check for non-Latin script ranges first
    cjk_count = 0
    cyrillic_count = 0
    greek_count = 0
    total_chars = 0

    for ch in clean:
        code = ord(ch)
        if 0x4E00 <= code <= 0x9FFF or 0x3040 <= code <= 0x30FF:
            cjk_count += 1
        elif 0x0400 <= code <= 0x04FF:
            cyrillic_count += 1
        elif 0x0370 <= code <= 0x03FF:
            greek_count += 1
        if ch.isalnum():
            total_chars += 1

    if total_chars > 10:
        if cjk_count / total_chars > 0.15:
            return 'zh'
        if cyrillic_count / total_chars > 0.20:
            return 'bg'
        if greek_count / total_chars > 0.20:
            return 'el'

    # Tokenize words for Latin stop-word comparison
    words = [w.lower() for w in re.findall(r'\b[^\W\d_]+\b', clean, re.UNICODE)]
    if not words:
        return 'en'

    scores: dict[str, int] = {lang: 0 for lang in _STOP_WORDS}
    for word in words:
        for lang, stop_set in _STOP_WORDS.items():
            if word in stop_set:
                scores[lang] += 1

    best_lang = 'en'
    best_score = 0
    for lang, score in scores.items():
        if score > best_score:
            best_score = score
            best_lang = lang

    return best_lang


@dataclass
class TranslatedLyrics:
    synced: Optional[str] = None
    plain: Optional[str] = None
    source_lang: str = 'en'
    target_lang: str = 'en'

    def has_any(self) -> bool:
        return bool(self.synced) or bool(self.plain)

    def as_dict(self) -> dict[str, Any]:
        return {
            'synced': self.synced,
            'plain': self.plain,
            'source_lang': self.source_lang,
            'target_lang': self.target_lang,
        }


class LyricsTranslationStore:
    """Persistent SQLite store for offline lyrics translations."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, connect_sqlite(self.db_path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS lyrics_translations (
                    file_key TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    source_lang TEXT NOT NULL,
                    synced TEXT,
                    plain TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(file_key, target_lang)
                )"""
            )
            conn.commit()

    def get(self, file_key: str, target_lang: str) -> Optional[TranslatedLyrics]:
        with self._lock, connect_sqlite(self.db_path, row_factory=True) as conn:
            row = conn.execute(
                """SELECT synced, plain, source_lang, target_lang
                   FROM lyrics_translations
                   WHERE file_key = ? AND target_lang = ?""",
                (file_key, target_lang),
            ).fetchone()
            if not row:
                return None
            return TranslatedLyrics(
                synced=row['synced'],
                plain=row['plain'],
                source_lang=row['source_lang'],
                target_lang=row['target_lang'],
            )

    def put(
        self,
        file_key: str,
        target_lang: str,
        source_lang: str,
        synced: Optional[str],
        plain: Optional[str],
    ) -> None:
        with self._lock, connect_sqlite(self.db_path) as conn:
            conn.execute(
                """INSERT INTO lyrics_translations (file_key, target_lang, source_lang, synced, plain, updated_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(file_key, target_lang) DO UPDATE SET
                       synced = excluded.synced,
                       plain = excluded.plain,
                       source_lang = excluded.source_lang,
                       updated_at = CURRENT_TIMESTAMP""",
                (file_key, target_lang, source_lang, synced, plain),
            )
            conn.commit()


_global_translation_store: Optional[LyricsTranslationStore] = None


def get_translation_store(db_dir: Optional[Path] = None) -> LyricsTranslationStore:
    global _global_translation_store
    if _global_translation_store is None:
        target_dir = db_dir or Path('/data')
        if not target_dir.exists():
            target_dir = Path.home() / '.gemini' / 'antigravity' / 'scratch' / 'downtify' / 'data'
        _global_translation_store = LyricsTranslationStore(
            target_dir / 'lyrics_translations.db'
        )
    return _global_translation_store


def _sidecar_translation_path(audio_path: Path, target_lang: str) -> Path:
    """Where a per-language translation sidecar lives."""
    return audio_path.with_name(f'{audio_path.stem}.{target_lang}.lrc')


def _sidecar_json_path(audio_path: Path) -> Path:
    """Where a multi-language translation metadata JSON sidecar lives."""
    return audio_path.with_name(f'{audio_path.stem}.translation.json')


def read_cached_translation(
    audio_path: Path, target_lang: str
) -> Optional[TranslatedLyrics]:
    """Check local files and database for an existing translation (100% offline)."""
    norm_target = normalize_lang_code(target_lang)
    store = get_translation_store()
    file_key = str(audio_path.resolve())

    # 1. SQLite database
    hit = store.get(file_key, norm_target)
    if hit and hit.has_any():
        return hit

    # 2. Sidecar .<lang>.lrc
    sidecar_lrc = _sidecar_translation_path(audio_path, norm_target)
    if sidecar_lrc.is_file():
        try:
            content = sidecar_lrc.read_text(encoding='utf-8').strip()
            if content:
                # Store in SQLite so future lookups are fast
                store.put(file_key, norm_target, 'auto', content, None)
                return TranslatedLyrics(synced=content, target_lang=norm_target)
        except OSError:
            pass

    # 3. Sidecar .translation.json
    sidecar_json = _sidecar_json_path(audio_path)
    if sidecar_json.is_file():
        try:
            data = json.loads(sidecar_json.read_text(encoding='utf-8'))
            translations = data.get('translations', {})
            entry = translations.get(norm_target)
            if entry and isinstance(entry, dict):
                synced = entry.get('synced')
                plain = entry.get('plain')
                src = data.get('source_lang', 'auto')
                store.put(file_key, norm_target, src, synced, plain)
                return TranslatedLyrics(
                    synced=synced,
                    plain=plain,
                    source_lang=src,
                    target_lang=norm_target,
                )
        except (OSError, ValueError):
            pass

    return None


def write_cached_translation(
    audio_path: Path,
    target_lang: str,
    source_lang: str,
    synced: Optional[str],
    plain: Optional[str],
) -> None:
    """Persist translation to SQLite and write local sidecar if directory is writable."""
    norm_target = normalize_lang_code(target_lang)
    store = get_translation_store()
    file_key = str(audio_path.resolve())

    # 1. Store in SQLite
    try:
        store.put(file_key, norm_target, source_lang, synced, plain)
    except Exception:
        logger.opt(exception=True).warning('Failed to save translation to SQLite')

    # 2. Write sidecars if writable
    try:
        if synced:
            sidecar_lrc = _sidecar_translation_path(audio_path, norm_target)
            sidecar_lrc.write_text(synced, encoding='utf-8')

        sidecar_json = _sidecar_json_path(audio_path)
        existing_data: dict[str, Any] = {'source_lang': source_lang, 'translations': {}}
        if sidecar_json.is_file():
            try:
                existing_data = json.loads(sidecar_json.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                pass
        translations = existing_data.setdefault('translations', {})
        translations[norm_target] = {'synced': synced, 'plain': plain}
        existing_data['source_lang'] = source_lang
        sidecar_json.write_text(json.dumps(existing_data, indent=2, ensure_ascii=False), encoding='utf-8')
    except OSError:
        # Ignore write permissions issues on read-only library trees
        pass


def _translate_line_offline(text: str, source_lang: str, target_lang: str) -> Optional[str]:
    """Attempt basic phrase / word substitution offline."""
    pair = (source_lang, target_lang)
    dictionary = _OFFLINE_DICTIONARY.get(pair)
    if not dictionary:
        return None
    lower = text.strip().lower()
    if lower in dictionary:
        return dictionary[lower]
    # Check partial phrase matches
    result = lower
    matched = False
    for phrase, trans in dictionary.items():
        if phrase in result:
            result = result.replace(phrase, trans)
            matched = True
    return result if matched else None


def _translate_text_api(text: str, source_lang: str, target_lang: str) -> str:
    """Translate text using free keyless translation APIs with graceful fallbacks."""
    if not text.strip():
        return ''

    # Clean text to translate
    query = text.strip()

    # 1. MyMemory free keyless API
    try:
        url = 'https://api.mymemory.translated.net/get'
        params = {'q': query, 'langpair': f'{source_lang}|{target_lang}'}
        resp = httpx.get(
            url,
            params=params,
            headers={'User-Agent': _USER_AGENT},
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            translated = (data.get('responseData') or {}).get('translatedText')
            if translated and not translated.startswith('MYMEMORY WARNING'):
                return str(translated).strip()
    except Exception:
        logger.debug('MyMemory translation request failed')

    # 2. Google Translate client gtx fallback
    try:
        url = f'https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_lang}&tl={target_lang}&dt=t&q={urllib.parse.quote(query)}'
        resp = httpx.get(url, headers={'User-Agent': _USER_AGENT}, timeout=_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and data[0]:
                chunks = [chunk[0] for chunk in data[0] if chunk and chunk[0]]
                return ''.join(chunks).strip()
    except Exception:
        logger.debug('Google translate gtx request failed')

    # 3. Offline dictionary fallback
    offline = _translate_line_offline(text, source_lang, target_lang)
    if offline:
        return offline

    return ''


def translate_lines(
    lines: Sequence[str], source_lang: str, target_lang: str
) -> list[str]:
    """Translate a list of lines, preserving line order and blank lines."""
    norm_source = normalize_lang_code(source_lang)
    norm_target = normalize_lang_code(target_lang)
    if norm_source == norm_target:
        return list(lines)
    results: list[str] = []
    # Batch chunks of up to 10 lines separated by newline to preserve rate limits
    chunk_size = 10
    for i in range(0, len(lines), chunk_size):
        chunk = lines[i : i + chunk_size]
        non_empty = [l for l in chunk if l.strip()]
        if not non_empty:
            results.extend(['' for _ in chunk])
            continue

        joined = '\n'.join(chunk)
        translated_joined = _translate_text_api(joined, source_lang, target_lang)
        if translated_joined:
            t_lines = translated_joined.split('\n')
            if len(t_lines) == len(chunk):
                results.extend(t_lines)
                continue

        # Fallback line by line if chunk split count mismatched
        for line in chunk:
            if not line.strip():
                results.append('')
            else:
                t = _translate_text_api(line, source_lang, target_lang)
                results.append(t or '')

    return results


def translate_lyrics(
    synced: Optional[str],
    plain: Optional[str],
    target_lang: str,
    source_lang: Optional[str] = None,
) -> TranslatedLyrics:
    """Translate synced LRC and/or plain lyrics into target_lang."""
    norm_target = normalize_lang_code(target_lang)

    # Detect source language if not provided
    sample_text = plain or _LRC_STAMP.sub('', synced or '')
    detected_src = source_lang or detect_lyrics_language(sample_text)
    norm_src = normalize_lang_code(detected_src)

    # If same language, no translation needed
    if norm_src == norm_target:
        return TranslatedLyrics(
            synced=None,
            plain=None,
            source_lang=norm_src,
            target_lang=norm_target,
        )

    translated_synced: Optional[str] = None
    translated_plain: Optional[str] = None

    if synced:
        lrc_lines: list[tuple[str, str]] = []
        raw_texts: list[str] = []
        for line in synced.splitlines():
            tags = _LRC_STAMP.findall(line)
            if not tags:
                continue
            stamp_part = ''.join(f'[{m}:{s}]' for m, s in tags)
            words = _LRC_STAMP.sub('', line).strip()
            lrc_lines.append((stamp_part, words))
            raw_texts.append(words)

        translated_texts = translate_lines(raw_texts, norm_src, norm_target)
        out_synced_lines: list[str] = []
        for (stamp_part, orig), trans in zip(lrc_lines, translated_texts):
            clean_trans = trans.strip()
            if clean_trans:
                out_synced_lines.append(f'{stamp_part}{clean_trans}')
            else:
                out_synced_lines.append(f'{stamp_part}{orig}')
        translated_synced = '\n'.join(out_synced_lines).strip() or None

    if plain:
        plain_lines = plain.splitlines()
        translated_plain_lines = translate_lines(plain_lines, norm_src, norm_target)
        translated_plain = '\n'.join(translated_plain_lines).strip() or None
    elif translated_synced:
        translated_plain = _LRC_STAMP.sub('', translated_synced).strip() or None

    return TranslatedLyrics(
        synced=translated_synced,
        plain=translated_plain,
        source_lang=norm_src,
        target_lang=norm_target,
    )


def get_or_translate_lyrics(
    audio_path: Path,
    original_synced: Optional[str],
    original_plain: Optional[str],
    target_lang: str,
) -> dict[str, Any]:
    """Retrieve translation from offline cache or translate and cache it."""
    norm_target = normalize_lang_code(target_lang)

    # 1. Check local offline cache
    cached = read_cached_translation(audio_path, norm_target)
    if cached and cached.has_any():
        return {
            'synced': original_synced or '',
            'plain': original_plain or '',
            'source_lang': cached.source_lang,
            'target_lang': norm_target,
            'translated_synced': cached.synced,
            'translated_plain': cached.plain,
            'same_language': cached.source_lang == norm_target,
        }

    # 2. Detect source language
    sample_text = original_plain or _LRC_STAMP.sub('', original_synced or '')
    detected_src = detect_lyrics_language(sample_text)
    norm_src = normalize_lang_code(detected_src)

    if norm_src == norm_target:
        # Same language: remember in cache so we don't re-detect every time
        write_cached_translation(audio_path, norm_target, norm_src, None, None)
        return {
            'synced': original_synced or '',
            'plain': original_plain or '',
            'source_lang': norm_src,
            'target_lang': norm_target,
            'translated_synced': None,
            'translated_plain': None,
            'same_language': True,
        }

    # 3. Perform translation
    result = translate_lyrics(
        original_synced, original_plain, norm_target, source_lang=norm_src
    )

    # 4. Save to disk & database cache
    write_cached_translation(
        audio_path,
        norm_target,
        norm_src,
        result.synced,
        result.plain,
    )

    return {
        'synced': original_synced or '',
        'plain': original_plain or '',
        'source_lang': norm_src,
        'target_lang': norm_target,
        'translated_synced': result.synced,
        'translated_plain': result.plain,
        'same_language': False,
    }
