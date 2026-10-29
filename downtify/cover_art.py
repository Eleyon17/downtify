"""Extract embedded cover art from audio files."""

from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path

from loguru import logger
from mutagen import File as MutagenFile
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, APIC, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis


def _embedded_cover_from_id3(path: Path) -> tuple[bytes | None, str | None]:
    try:
        tag = ID3(str(path))
        for frame in tag.getall('APIC'):
            if frame.data:
                return frame.data, frame.mime or 'image/jpeg'
    except Exception:
        pass
    return None, None


def _embedded_cover_from_flac(path: Path) -> tuple[bytes | None, str | None]:
    try:
        f = FLAC(str(path))
        if f.pictures:
            pic = f.pictures[0]
            return pic.data, pic.mime or 'image/jpeg'
    except Exception:
        pass
    return None, None


def _embedded_cover_from_mp4(path: Path) -> tuple[bytes | None, str | None]:
    try:
        m = MP4(str(path))
        covr = m.tags.get('covr') if m.tags else None
        if not covr:
            return None, None
        pic = covr[0]
        fmt = getattr(pic, 'imageformat', None)
        mime = 'image/png' if fmt == 14 else 'image/jpeg'
        return bytes(pic), mime
    except Exception:
        return None, None


def _embedded_cover_from_ogg(path: Path) -> tuple[bytes | None, str | None]:
    try:
        ogg = (
            OggOpus(str(path))
            if path.suffix.lower() == '.opus'
            else OggVorbis(str(path))
        )
        blocks = ogg.get('metadata_block_picture') or []
        for raw in blocks:
            try:
                pic = Picture(base64.b64decode(raw))
                if pic.data:
                    return pic.data, pic.mime or 'image/jpeg'
            except Exception:
                continue
    except Exception:
        pass
    return None, None


def _embedded_cover_from_mutagen(
    path: Path,
) -> tuple[bytes | None, str | None]:
    try:
        f = MutagenFile(str(path))
        if f is not None and getattr(f, 'pictures', None):
            pic = f.pictures[0]
            return pic.data, pic.mime or 'image/jpeg'
    except Exception:
        pass
    return None, None


def extract_embedded_cover(path: Path) -> tuple[bytes | None, str | None]:
    """Return ``(image_bytes, mime)`` for the embedded cover, or ``(None, None)``."""

    suffix = path.suffix.lower()
    data, mime = _embedded_cover_from_id3(path)
    if data:
        return data, mime
    if suffix == '.flac':
        data, mime = _embedded_cover_from_flac(path)
        if data:
            return data, mime
    if suffix in {'.m4a', '.mp4', '.aac'}:
        data, mime = _embedded_cover_from_mp4(path)
        if data:
            return data, mime
    if suffix in {'.ogg', '.opus'}:
        data, mime = _embedded_cover_from_ogg(path)
        if data:
            return data, mime
    return _embedded_cover_from_mutagen(path)


_FOLDER_COVER_STEMS = frozenset({
    'cover',
    'folder',
    'front',
    'album',
    'artwork',
    'albumart',
})


def _mime_for_image(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or 'image/jpeg'


def extract_folder_cover(path: Path) -> tuple[bytes | None, str | None]:
    """Return cover image bytes from common filenames next to *path*."""

    parent = path.parent
    if not parent.is_dir():
        return None, None
    candidates: list[Path] = []
    try:
        with os.scandir(parent) as entries:
            for entry in entries:
                suffix = Path(entry.name).suffix.lower()
                if suffix not in {'.jpg', '.jpeg', '.png', '.webp'}:
                    continue
                stem = Path(entry.name).stem.casefold()
                if stem not in _FOLDER_COVER_STEMS:
                    continue
                if not entry.is_file(follow_symlinks=True):
                    continue
                candidates.append(Path(entry.path))
    except OSError:
        return None, None
    for entry in sorted(candidates, key=lambda item: item.name.casefold()):
        try:
            data = entry.read_bytes()
        except OSError:
            continue
        if data:
            return data, _mime_for_image(entry)
    return None, None


def extract_cover_art(path: Path) -> tuple[bytes | None, str | None]:
    """Embedded tags first, then ``cover.jpg`` / ``folder.jpg`` in the same folder."""

    data, mime = extract_embedded_cover(path)
    if data:
        return data, mime
    return extract_folder_cover(path)


def file_has_cover_art(path: Path) -> bool:
    """True when embedded or folder art exists (used by ``/list``)."""

    if not path.is_file():
        return False
    if extract_folder_cover(path)[0]:
        return True
    return extract_embedded_cover(path)[0] is not None


def embed_cover_art(
    path: Path, cover_bytes: bytes, mime: str = 'image/jpeg'
) -> bool:
    """Embed *cover_bytes* into *path*, supporting MP3, FLAC, M4A, OGG, and Opus."""

    if not path.is_file() or not cover_bytes:
        return False

    suffix = path.suffix.lower()
    try:
        if suffix == '.mp3':
            try:
                tag = ID3(str(path))
            except Exception:
                tag = ID3()
            tag.delall('APIC')
            tag.add(
                APIC(
                    encoding=3,
                    mime=mime,
                    type=3,
                    desc='Cover',
                    data=cover_bytes,
                )
            )
            tag.save(str(path), v2_version=3)
            return True

        if suffix == '.flac':
            f = FLAC(str(path))
            pic = Picture()
            pic.type = 3
            pic.mime = mime
            pic.desc = 'Cover'
            pic.data = cover_bytes
            f.clear_pictures()
            f.add_picture(pic)
            f.save()
            return True

        if suffix in {'.m4a', '.mp4', '.aac'}:
            m = MP4(str(path))
            image_format = (
                MP4Cover.FORMAT_PNG
                if 'png' in mime.lower()
                else MP4Cover.FORMAT_JPEG
            )
            m['covr'] = [MP4Cover(cover_bytes, imageformat=image_format)]
            m.save()
            return True

        if suffix in {'.ogg', '.opus', '.oga'}:
            ogg = (
                OggOpus(str(path))
                if suffix == '.opus'
                else OggVorbis(str(path))
            )
            pic = Picture()
            pic.type = 3
            pic.mime = mime
            pic.desc = 'Cover'
            pic.data = cover_bytes
            encoded_data = base64.b64encode(pic.write()).decode('ascii')
            ogg['metadata_block_picture'] = [encoded_data]
            ogg.save()
            return True

        f = MutagenFile(str(path))
        if f is not None:
            pic = Picture()
            pic.type = 3
            pic.mime = mime
            pic.desc = 'Cover'
            pic.data = cover_bytes
            if hasattr(f, 'add_picture'):
                if hasattr(f, 'clear_pictures'):
                    f.clear_pictures()
                f.add_picture(pic)
                f.save()
                return True
    except Exception as exc:
        logger.opt(exception=True).warning(
            'Failed to embed cover art into {}: {}', path, exc
        )
        return False
    return False
