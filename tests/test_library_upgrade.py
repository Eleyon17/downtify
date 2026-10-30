"""Scanning a library for tracks to repair, and repairing them safely."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, Optional

import pytest
from mutagen.id3 import APIC, ID3, TALB, TDRC, TIT2, TPE1, TPE2, TRCK

from downtify import cover_sources, library_upgrade
from downtify.library_catalog import LibraryContext
from downtify.library_metadata_cache import LibraryMetadataCache
from downtify.library_upgrade import (
    CATEGORY_ARTWORK,
    CATEGORY_LYRICS,
    CATEGORY_METADATA,
    LibraryUpgradeRunner,
    UpgradeDeps,
    UpgradeOptions,
    song_for_track,
    staging_path,
    track_findings,
    upgrade_track,
)
from downtify.library_upgrade_db import (
    JOB_DONE,
    JOB_QUEUED,
    JOB_SKIPPED,
    STATE_DONE,
    STATE_PAUSED,
    STATE_READY,
    STATE_RUNNING,
    LibraryUpgradeDB,
    check_is_fresh,
)
from downtify.lyrics import Lyrics

# One MPEG-1 Layer III frame at 128 kbit/s, 44.1 kHz. mutagen reads the
# duration from the header plus the file size, so a stream of these is a
# playable-looking file without shipping an audio fixture.
_MP3_FRAME = b'\xff\xfb\x90\x00' + b'\x00' * 413


def _png(size: int) -> bytes:
    return (
        b'\x89PNG\r\n\x1a\n'
        + struct.pack('>I', 13)
        + b'IHDR'
        + struct.pack('>II', size, size)
        + b'\x08\x06\x00\x00\x00'
    )


#: Tags a track downloaded by Downtify normally carries. A test blanks
#: one of these to stand for a track an older version tagged poorly.
_FULL_TAGS = {
    'album': 'Album',
    'album_artist': 'Artist',
    'year': '2020',
    'track_number': '3',
}


def _write_track(
    path: Path, *, cover_px: int = 0, frames: int = 100, **overrides: str
) -> Path:
    fields = {**_FULL_TAGS, **overrides}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_MP3_FRAME * frames)
    tags = ID3()
    tags.add(TIT2(encoding=3, text='Track'))
    tags.add(TPE1(encoding=3, text='Artist'))
    if fields['album']:
        tags.add(TALB(encoding=3, text=fields['album']))
    if fields['album_artist']:
        tags.add(TPE2(encoding=3, text=fields['album_artist']))
    if fields['year']:
        tags.add(TDRC(encoding=3, text=fields['year']))
    if fields['track_number']:
        tags.add(TRCK(encoding=3, text=str(fields['track_number'])))
    if cover_px:
        tags.add(
            APIC(
                encoding=3,
                mime='image/png',
                type=3,
                desc='Cover',
                data=_png(cover_px),
            )
        )
    tags.save(str(path), v2_version=4)
    return path


def _context(tmp_path: Path) -> LibraryContext:
    return LibraryContext(
        download_dir=tmp_path / 'downloads',
        metadata_cache=LibraryMetadataCache(tmp_path / 'lib.db'),
    )


def _deps(
    ctx: LibraryContext,
    *,
    version: str = '3.0.0',
    spotify_id: str = '',
    settings: Optional[dict[str, Any]] = None,
) -> UpgradeDeps:
    return UpgradeDeps(
        context=lambda: ctx,
        settings=lambda: settings or {'lyrics_providers': ['lrclib']},
        version=version,
        spotify_id_for=(lambda _path: spotify_id) if spotify_id else None,
    )


def _entry(ctx: LibraryContext, stored: str) -> dict[str, Any]:
    full = ctx.download_dir / stored
    return ctx.metadata_cache.get_entries_batch([(stored, full)])[0]


# ── What counts as behind ──────────────────────────────────────────
def test_a_small_cover_and_missing_lyrics_are_findings(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'a.mp3', cover_px=300)
    entry = _entry(ctx, 'a.mp3')

    found = track_findings(
        entry, ctx.download_dir / 'a.mp3', artwork_min_px=600
    )

    assert found == [CATEGORY_ARTWORK, CATEGORY_LYRICS]


def test_a_large_cover_is_not_a_finding(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'a.mp3', cover_px=1200)
    entry = _entry(ctx, 'a.mp3')

    found = track_findings(
        entry, ctx.download_dir / 'a.mp3', artwork_min_px=600
    )

    assert CATEGORY_ARTWORK not in found


def test_a_cover_exactly_at_the_target_is_left_alone(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'a.mp3', cover_px=600)

    found = track_findings(
        _entry(ctx, 'a.mp3'), ctx.download_dir / 'a.mp3', artwork_min_px=600
    )

    assert CATEGORY_ARTWORK not in found


def test_missing_tag_fields_are_a_metadata_finding(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'a.mp3', cover_px=1200, album='', year='')

    found = track_findings(
        _entry(ctx, 'a.mp3'), ctx.download_dir / 'a.mp3', artwork_min_px=600
    )

    assert CATEGORY_METADATA in found


def test_an_lrc_sidecar_counts_as_having_lyrics(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'a.mp3', cover_px=1200)
    (ctx.download_dir / 'a.lrc').write_text('[00:01.00] line', 'utf-8')

    found = track_findings(
        _entry(ctx, 'a.mp3'), ctx.download_dir / 'a.mp3', artwork_min_px=600
    )

    assert found == []


# ── Describing the track ───────────────────────────────────────────
def test_song_without_a_spotify_id_is_only_the_files_own_tags(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'a.mp3', cover_px=300)

    song = song_for_track(_entry(ctx, 'a.mp3'))

    assert song['name'] == 'Track'
    assert song['artists'] == ['Artist']
    assert song['album_name'] == 'Album'
    assert 'song_id' not in song


def test_refreshed_metadata_never_blanks_what_the_file_has(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'a.mp3', cover_px=300)
    monkeypatch.setattr(
        library_upgrade.spotify,
        'track_from_id',
        lambda _id, **_kw: {
            'album_name': '',
            'year': '1999',
            'track_number': 7,
        },
    )

    song = song_for_track(
        _entry(ctx, 'a.mp3'),
        spotify_id='1' * 22,
        refresh_metadata=True,
    )

    assert song['album_name'] == 'Album'  # kept, the remote had none
    assert song['year'] == '1999'
    assert song['track_number'] == 7


def test_a_failing_spotify_lookup_falls_back_to_the_tags(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'a.mp3', cover_px=300)

    def _boom(_id: str, **_kw: Any) -> dict[str, Any]:
        raise RuntimeError('no network')

    monkeypatch.setattr(library_upgrade.spotify, 'track_from_id', _boom)

    song = song_for_track(
        _entry(ctx, 'a.mp3'), spotify_id='1' * 22, refresh_metadata=True
    )

    assert song['album_name'] == 'Album'


# ── Upgrading one track ────────────────────────────────────────────
def _stub_cover(monkeypatch: Any, width: Optional[int]) -> None:
    def _best(
        _song: dict[str, Any],
        *,
        current: Any = None,
        preference: str = '',
    ) -> Any:
        if width is None:
            return None
        return cover_sources.CoverCandidate(
            source='itunes', data=_png(width), width=width
        )

    monkeypatch.setattr(cover_sources, 'best_cover', _best)


def test_artwork_upgrade_replaces_the_cover_and_keeps_the_timestamp(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    track = _write_track(ctx.download_dir / 'a.mp3', cover_px=300)
    before = track.stat().st_mtime_ns
    _stub_cover(monkeypatch, 1200)

    outcome = upgrade_track(
        'a.mp3',
        deps=_deps(ctx),
        options=UpgradeOptions(categories=(CATEGORY_ARTWORK,)),
    )

    assert outcome.status == JOB_DONE
    assert outcome.changed == [CATEGORY_ARTWORK]
    assert outcome.artwork_px == 1200
    assert '1200px' in outcome.detail
    # The new cover is in the file, the working copy is gone, and the
    # Library's "recently added" order is undisturbed.
    assert ID3(str(track)).getall('APIC')[0].data == _png(1200)
    assert not staging_path(track).exists()
    assert track.stat().st_mtime_ns == before


def test_artwork_upgrade_is_skipped_when_no_source_has_anything_bigger(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    track = _write_track(ctx.download_dir / 'a.mp3', cover_px=300)
    _stub_cover(monkeypatch, None)

    outcome = upgrade_track(
        'a.mp3',
        deps=_deps(ctx),
        options=UpgradeOptions(categories=(CATEGORY_ARTWORK,)),
    )

    assert outcome.status == JOB_SKIPPED
    assert ID3(str(track)).getall('APIC')[0].data == _png(300)


def test_a_track_already_at_the_target_is_not_looked_up_at_all(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'a.mp3', cover_px=1200)

    def _never(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError('should not ask a cover source')

    monkeypatch.setattr(cover_sources, 'best_cover', _never)

    outcome = upgrade_track(
        'a.mp3',
        deps=_deps(ctx),
        options=UpgradeOptions(categories=(CATEGORY_ARTWORK,)),
    )

    assert outcome.status == JOB_SKIPPED


def test_lyrics_upgrade_embeds_and_writes_a_sidecar(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    track = _write_track(ctx.download_dir / 'a.mp3', cover_px=1200)
    monkeypatch.setattr(
        library_upgrade.lyrics_mod,
        'fetch',
        lambda *_a, **_k: Lyrics(plain='one line', synced='[00:01.00] one'),
    )

    outcome = upgrade_track(
        'a.mp3',
        deps=_deps(ctx),
        options=UpgradeOptions(categories=(CATEGORY_LYRICS,)),
    )

    assert outcome.status == JOB_DONE
    assert outcome.changed == [CATEGORY_LYRICS]
    assert (ctx.download_dir / 'a.lrc').exists()
    assert ID3(str(track)).getall('USLT')
    assert not staging_path(track).exists()
    assert not staging_path(track).with_suffix('.lrc').exists()


def test_a_track_that_has_lyrics_is_not_asked_about_again(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'a.mp3', cover_px=1200)
    (ctx.download_dir / 'a.lrc').write_text('[00:01.00] line', 'utf-8')

    def _never(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError('should not ask a lyrics provider')

    monkeypatch.setattr(library_upgrade.lyrics_mod, 'fetch', _never)

    outcome = upgrade_track(
        'a.mp3',
        deps=_deps(ctx),
        options=UpgradeOptions(categories=(CATEGORY_LYRICS,)),
    )

    assert outcome.status == JOB_SKIPPED


def test_metadata_upgrade_fills_the_gaps_from_spotify(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    track = _write_track(
        ctx.download_dir / 'a.mp3', cover_px=1200, album='', year=''
    )
    monkeypatch.setattr(
        library_upgrade.spotify,
        'track_from_id',
        lambda _id, **_kw: {
            'album_name': 'Real Album',
            'year': '2011',
            'release_date': '2011-05-06',
            'track_number': 4,
            'album_track_total': 12,
        },
    )

    outcome = upgrade_track(
        'a.mp3',
        deps=_deps(ctx, spotify_id='1' * 22),
        options=UpgradeOptions(categories=(CATEGORY_METADATA,)),
    )

    assert outcome.status == JOB_DONE
    tags = ID3(str(track))
    assert str(tags['TALB']) == 'Real Album'
    assert str(tags['TRCK']) == '4/12'
    # Writing tags must not cost the track its artwork.
    assert tags.getall('APIC')[0].data == _png(1200)


def test_metadata_upgrade_needs_a_known_spotify_track(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'a.mp3', cover_px=1200, album='')

    outcome = upgrade_track(
        'a.mp3',
        deps=_deps(ctx),
        options=UpgradeOptions(categories=(CATEGORY_METADATA,)),
    )

    assert outcome.status == JOB_SKIPPED


def test_a_failed_write_leaves_the_original_untouched(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    track = _write_track(ctx.download_dir / 'a.mp3', cover_px=300)
    original = track.read_bytes()
    _stub_cover(monkeypatch, 1200)

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError('tagging blew up')

    monkeypatch.setattr(library_upgrade, 'embed_metadata', _boom)

    outcome = upgrade_track(
        'a.mp3',
        deps=_deps(ctx),
        options=UpgradeOptions(categories=(CATEGORY_ARTWORK,)),
    )

    assert outcome.status == 'failed'
    assert track.read_bytes() == original
    assert not staging_path(track).exists()


def test_a_copy_that_does_not_verify_is_thrown_away(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    track = _write_track(ctx.download_dir / 'a.mp3', cover_px=300)
    original = track.read_bytes()
    _stub_cover(monkeypatch, 1200)

    def _truncate(path: Path, *_args: Any, **_kwargs: Any) -> None:
        path.write_bytes(b'')

    monkeypatch.setattr(library_upgrade, 'embed_metadata', _truncate)

    outcome = upgrade_track(
        'a.mp3',
        deps=_deps(ctx),
        options=UpgradeOptions(categories=(CATEGORY_ARTWORK,)),
    )

    assert outcome.status == 'failed'
    assert 'kept the original' in outcome.detail
    assert track.read_bytes() == original
    assert not staging_path(track).exists()


def test_a_missing_file_is_skipped(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    ctx.download_dir.mkdir(parents=True, exist_ok=True)

    outcome = upgrade_track(
        'gone.mp3', deps=_deps(ctx), options=UpgradeOptions()
    )

    assert outcome.status == JOB_SKIPPED
    assert 'no longer' in outcome.detail


# ── The queue ──────────────────────────────────────────────────────
def test_jobs_are_claimed_once_and_counted(tmp_path: Path) -> None:
    db = LibraryUpgradeDB(tmp_path / 'lib.db')
    run_id = db.create_run(['artwork'], {})
    db.add_jobs(
        run_id,
        [
            {'file': 'a.mp3', 'categories': ['artwork'], 'size': 10},
            {'file': 'b.mp3', 'categories': ['lyrics'], 'size': 20},
        ],
    )

    first = db.take_next(run_id)
    assert first is not None
    assert first['file'] == 'a.mp3'
    assert db.counts(run_id)['running'] == 1

    db.finish_job(run_id, 'a.mp3', JOB_DONE, detail='artwork 1200px')
    second = db.take_next(run_id)
    assert second is not None
    assert second['file'] == 'b.mp3'
    assert db.take_next(run_id) is None

    db.finish_job(run_id, 'b.mp3', JOB_SKIPPED)
    counts = db.counts(run_id)
    assert counts['completed'] == 1
    assert counts['skipped'] == 1
    assert counts['finished'] == 2
    assert counts['processed_bytes'] == 30


def test_adding_the_same_track_twice_does_not_duplicate_it(
    tmp_path: Path,
) -> None:
    db = LibraryUpgradeDB(tmp_path / 'lib.db')
    run_id = db.create_run(['artwork'], {})
    job = {'file': 'a.mp3', 'categories': ['artwork'], 'size': 1}
    db.add_jobs(run_id, [job])
    db.add_jobs(run_id, [job])

    assert db.counts(run_id)['total'] == 1


def test_a_job_interrupted_by_a_restart_goes_back_in_the_queue(
    tmp_path: Path,
) -> None:
    db = LibraryUpgradeDB(tmp_path / 'lib.db')
    run_id = db.create_run(['artwork'], {})
    db.add_jobs(run_id, [{'file': 'a.mp3', 'categories': ['artwork']}])
    db.take_next(run_id)

    assert db.requeue_running(run_id) == 1
    assert db.counts(run_id)['queued'] == 1
    assert db.jobs(run_id, status=JOB_QUEUED)[0]['file'] == 'a.mp3'


def test_a_check_is_only_fresh_for_the_version_that_made_it(
    tmp_path: Path,
) -> None:
    db = LibraryUpgradeDB(tmp_path / 'lib.db')
    db.record_check(
        'a.mp3', [CATEGORY_ARTWORK], app_version='3.0.0', artwork_px=1200
    )
    check = db.checks_for(['a.mp3'])['a.mp3'][CATEGORY_ARTWORK]

    assert check['artwork_px'] == 1200
    assert check_is_fresh(check, app_version='3.0.0', max_age_days=30)
    # A newer Downtify may do better, so its checks start over.
    assert not check_is_fresh(check, app_version='3.1.0', max_age_days=30)
    assert not check_is_fresh(check, app_version='3.0.0', max_age_days=0)
    assert not check_is_fresh(None, app_version='3.0.0', max_age_days=30)


def test_checks_are_kept_per_category(tmp_path: Path) -> None:
    db = LibraryUpgradeDB(tmp_path / 'lib.db')
    db.record_check('a.mp3', [CATEGORY_ARTWORK], app_version='3.0.0')

    checks = db.checks_for(['a.mp3'])['a.mp3']

    # Looking at a track's artwork says nothing about its lyrics.
    assert set(checks) == {CATEGORY_ARTWORK}
    assert check_is_fresh(
        checks.get(CATEGORY_ARTWORK), app_version='3.0.0', max_age_days=30
    )
    assert not check_is_fresh(
        checks.get(CATEGORY_LYRICS), app_version='3.0.0', max_age_days=30
    )


def test_a_check_expires(tmp_path: Path) -> None:
    db = LibraryUpgradeDB(tmp_path / 'lib.db')
    db.record_check('a.mp3', [CATEGORY_LYRICS], app_version='3.0.0')
    check = dict(db.checks_for(['a.mp3'])['a.mp3'][CATEGORY_LYRICS])
    check['checked_at'] = '2020-01-01T00:00:00+00:00'

    assert not check_is_fresh(check, app_version='3.0.0', max_age_days=30)


def test_a_recorded_artwork_size_is_never_lowered(tmp_path: Path) -> None:
    db = LibraryUpgradeDB(tmp_path / 'lib.db')
    db.record_check(
        'a.mp3', [CATEGORY_ARTWORK], app_version='3.0.0', artwork_px=1200
    )
    db.record_check(
        'a.mp3', [CATEGORY_ARTWORK], app_version='3.0.0', artwork_px=0
    )

    checks = db.checks_for(['a.mp3'])['a.mp3']
    assert checks[CATEGORY_ARTWORK]['artwork_px'] == 1200


# ── The runner ─────────────────────────────────────────────────────
def _runner(tmp_path: Path, ctx: LibraryContext) -> LibraryUpgradeRunner:
    return LibraryUpgradeRunner(
        LibraryUpgradeDB(tmp_path / 'lib.db'), _deps(ctx)
    )


def _wait(runner: LibraryUpgradeRunner) -> None:
    worker = runner._worker
    if worker is not None:
        worker.join(timeout=30)


def test_a_scan_queues_only_the_tracks_that_are_behind(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'small.mp3', cover_px=300)
    _write_track(ctx.download_dir / 'fine.mp3', cover_px=1200)
    (ctx.download_dir / 'fine.lrc').write_text('[00:01.00] x', 'utf-8')
    runner = _runner(tmp_path, ctx)

    runner.start_scan(UpgradeOptions(artwork_min_px=600))
    _wait(runner)

    status = runner.status()
    assert status['state'] == STATE_READY
    assert status['counts']['total'] == 1
    summary = runner.scan_summary()
    assert summary['categories'][CATEGORY_ARTWORK] == 1
    assert summary['library_tracks'] == 2
    assert summary['library_bytes'] > 0


def test_every_progress_message_carries_what_the_scan_found(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'small.mp3', cover_px=300)
    _stub_cover(monkeypatch, 1200)
    sent: list[dict[str, Any]] = []
    deps = _deps(ctx)
    deps.publish = sent.append
    runner = LibraryUpgradeRunner(LibraryUpgradeDB(tmp_path / 'lib.db'), deps)
    runner.start_scan(UpgradeOptions(artwork_min_px=600))
    _wait(runner)

    runner.start((CATEGORY_ARTWORK,))
    _wait(runner)

    # A client that only ever sees these messages has to be able to
    # render the scan result, not just the counters.
    assert sent
    last = sent[-1]
    assert last['summary']['categories'][CATEGORY_ARTWORK] == 1
    assert last['summary']['library_tracks'] == 1
    assert all('summary' in message for message in sent)


def test_a_run_processes_only_the_chosen_categories(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'small.mp3', cover_px=300)
    _stub_cover(monkeypatch, 1200)

    def _never(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError('lyrics were not selected')

    monkeypatch.setattr(library_upgrade.lyrics_mod, 'fetch', _never)
    runner = _runner(tmp_path, ctx)
    runner.start_scan(UpgradeOptions(artwork_min_px=600))
    _wait(runner)

    runner.start((CATEGORY_ARTWORK,))
    _wait(runner)

    status = runner.status()
    assert status['state'] == STATE_DONE
    assert status['counts']['completed'] == 1
    assert ID3(str(ctx.download_dir / 'small.mp3')).getall('APIC')[
        0
    ].data == _png(1200)


def test_a_finished_track_is_remembered_so_the_next_scan_skips_it(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'small.mp3', cover_px=300)
    _stub_cover(monkeypatch, None)
    monkeypatch.setattr(
        library_upgrade.lyrics_mod, 'fetch', lambda *_a, **_k: None
    )
    runner = _runner(tmp_path, ctx)
    runner.start_scan(UpgradeOptions(artwork_min_px=600))
    _wait(runner)
    runner.start(library_upgrade.CATEGORIES)
    _wait(runner)

    runner.start_scan(UpgradeOptions(artwork_min_px=600))
    _wait(runner)

    assert runner.status()['counts']['total'] == 0


def test_repairing_one_category_leaves_the_others_due(
    tmp_path: Path, monkeypatch: Any
) -> None:
    # Fixing a track's artwork must not make the next scan believe its
    # missing lyrics were ever looked for.
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'small.mp3', cover_px=300)
    _stub_cover(monkeypatch, 1200)
    runner = _runner(tmp_path, ctx)
    runner.start_scan(UpgradeOptions(artwork_min_px=600))
    _wait(runner)

    runner.start((CATEGORY_ARTWORK,))
    _wait(runner)
    assert runner.status()['counts']['completed'] == 1

    runner.start_scan(UpgradeOptions(artwork_min_px=600))
    _wait(runner)

    summary = runner.scan_summary()
    assert summary['categories'][CATEGORY_LYRICS] == 1
    # The artwork is both done and remembered, so it isn't queued again.
    assert summary['categories'][CATEGORY_ARTWORK] == 0
    assert runner.status()['counts']['total'] == 1


def test_a_scan_reports_the_tracks_it_skipped_from_memory(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'small.mp3', cover_px=300)
    _stub_cover(monkeypatch, None)
    monkeypatch.setattr(
        library_upgrade.lyrics_mod, 'fetch', lambda *_a, **_k: None
    )
    runner = _runner(tmp_path, ctx)
    runner.start_scan(UpgradeOptions(artwork_min_px=600))
    _wait(runner)
    runner.start(library_upgrade.CATEGORIES)
    _wait(runner)

    runner.start_scan(UpgradeOptions(artwork_min_px=600))
    _wait(runner)

    summary = runner.scan_summary()
    assert summary['tracks'] == 0
    # Reported rather than silently missing, so "nothing to upgrade"
    # is distinguishable from "everything was checked recently".
    assert summary['recently_checked'] == 1


def test_a_rescan_looks_again_once_the_memory_is_disabled(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'small.mp3', cover_px=300)
    _stub_cover(monkeypatch, None)
    monkeypatch.setattr(
        library_upgrade.lyrics_mod, 'fetch', lambda *_a, **_k: None
    )
    runner = _runner(tmp_path, ctx)
    runner.start_scan(UpgradeOptions(artwork_min_px=600))
    _wait(runner)
    runner.start(library_upgrade.CATEGORIES)
    _wait(runner)

    runner.start_scan(UpgradeOptions(artwork_min_px=600, recheck_days=0))
    _wait(runner)

    assert runner.status()['counts']['total'] == 1


def test_a_paused_run_keeps_its_queue_and_resumes(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    for name in ('a.mp3', 'b.mp3', 'c.mp3'):
        _write_track(ctx.download_dir / name, cover_px=300)
    _stub_cover(monkeypatch, 1200)
    runner = _runner(tmp_path, ctx)
    runner.start_scan(UpgradeOptions(artwork_min_px=600))
    _wait(runner)

    seen: list[str] = []
    real = library_upgrade.upgrade_track

    def _one_then_pause(stored: str, **kwargs: Any) -> Any:
        seen.append(stored)
        runner.pause()
        return real(stored, **kwargs)

    monkeypatch.setattr(library_upgrade, 'upgrade_track', _one_then_pause)
    runner.start((CATEGORY_ARTWORK,))
    _wait(runner)

    paused = runner.status()
    assert paused['state'] == STATE_PAUSED
    assert paused['counts']['queued'] == 2
    assert len(seen) == 1

    monkeypatch.setattr(library_upgrade, 'upgrade_track', real)
    runner.resume()
    _wait(runner)
    assert runner.status()['state'] == STATE_DONE
    assert runner.status()['counts']['completed'] == 3


def test_a_cancelled_run_drops_the_rest_of_the_queue(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    for name in ('a.mp3', 'b.mp3'):
        _write_track(ctx.download_dir / name, cover_px=300)
    _stub_cover(monkeypatch, 1200)
    runner = _runner(tmp_path, ctx)
    runner.start_scan(UpgradeOptions(artwork_min_px=600))
    _wait(runner)

    real = library_upgrade.upgrade_track

    def _cancel_after_first(stored: str, **kwargs: Any) -> Any:
        runner.cancel()
        return real(stored, **kwargs)

    monkeypatch.setattr(library_upgrade, 'upgrade_track', _cancel_after_first)
    runner.start((CATEGORY_ARTWORK,))
    _wait(runner)

    status = runner.status()
    assert status['state'] == 'cancelled'
    assert status['counts']['queued'] == 1


def test_a_restart_in_the_middle_picks_the_queue_back_up(
    tmp_path: Path, monkeypatch: Any
) -> None:
    ctx = _context(tmp_path)
    _write_track(ctx.download_dir / 'a.mp3', cover_px=300)
    _stub_cover(monkeypatch, 1200)
    db = LibraryUpgradeDB(tmp_path / 'lib.db')
    run_id = db.create_run([CATEGORY_ARTWORK], {'artwork_min_px': 600})
    db.add_jobs(run_id, [{'file': 'a.mp3', 'categories': [CATEGORY_ARTWORK]}])
    db.set_state(run_id, STATE_RUNNING)
    db.take_next(run_id)  # as if the process died here

    runner = LibraryUpgradeRunner(db, _deps(ctx))
    runner.resume_after_restart()
    _wait(runner)

    assert runner.status()['state'] == STATE_DONE
    assert runner.status()['counts']['completed'] == 1


def test_a_scan_cut_short_by_a_restart_is_discarded(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    ctx.download_dir.mkdir(parents=True, exist_ok=True)
    db = LibraryUpgradeDB(tmp_path / 'lib.db')
    run_id = db.create_run([CATEGORY_ARTWORK], {})
    db.add_jobs(run_id, [{'file': 'a.mp3', 'categories': [CATEGORY_ARTWORK]}])

    runner = LibraryUpgradeRunner(db, _deps(ctx))
    runner.resume_after_restart()

    assert runner.status()['state'] == 'cancelled'
    assert db.counts(run_id)['total'] == 0


def test_starting_without_a_scan_is_refused(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    runner = _runner(tmp_path, ctx)

    with pytest.raises(RuntimeError):
        runner.start((CATEGORY_ARTWORK,))


def test_categories_from_a_request_are_filtered_and_ordered() -> None:
    assert library_upgrade.normalize_categories(['lyrics', 'artwork']) == (
        CATEGORY_ARTWORK,
        CATEGORY_LYRICS,
    )
    assert library_upgrade.normalize_categories(['nonsense']) == (
        library_upgrade.CATEGORIES
    )
    assert library_upgrade.normalize_categories(None) == (
        library_upgrade.CATEGORIES
    )


def test_options_are_clamped() -> None:
    options = library_upgrade.options_from({
        'artwork_min_px': 99999,
        'artwork_source': 'not-a-source',
        'recheck_days': -5,
    })

    assert options.artwork_min_px == 3000
    assert options.artwork_source == cover_sources.PREFERENCE_HIGHEST
    assert options.recheck_days == 0


def test_track_format_improper(tmp_path: Path) -> None:
    from downtify.library_upgrade import CATEGORY_FORMAT, track_format_improper

    # An MP3 at 128 kbps
    mp3_file = _write_track(tmp_path / 'song.mp3')
    entry = {'file': 'song.mp3', 'bitrate': 128000}

    # Format mismatch: target is FLAC
    assert track_format_improper(
        entry, mp3_file, target_format='flac', target_bitrate_kbps=320
    )

    # Quality mismatch: target is MP3 at 320k, file is 128k
    assert track_format_improper(
        entry, mp3_file, target_format='mp3', target_bitrate_kbps=320
    )

    # Quality match: target is MP3 at 128k
    assert not track_format_improper(
        entry, mp3_file, target_format='mp3', target_bitrate_kbps=128
    )

    # FLAC file matches FLAC target (lossless, no bitrate check)
    flac_file = tmp_path / 'song.flac'
    flac_file.write_bytes(b'dummy-flac')
    flac_entry = {'file': 'song.flac', 'bitrate': 0}
    assert not track_format_improper(
        flac_entry, flac_file, target_format='flac', target_bitrate_kbps=320
    )


def test_track_findings_checks_format_only_when_requested(
    tmp_path: Path,
) -> None:
    from downtify.library_upgrade import CATEGORY_FORMAT

    mp3_file = _write_track(tmp_path / 'song.mp3', cover_px=800)
    entry = {
        'file': 'song.mp3',
        'cover_px': 800,
        'album': 'Album',
        'album_artist': 'Artist',
        'year': '2020',
        'track_number': 1,
        'bitrate': 128000,
    }

    # With check_format=False (default/off)
    findings = track_findings(
        entry,
        mp3_file,
        artwork_min_px=600,
        check_format=False,
        target_format='mp3',
        target_bitrate_kbps=320,
    )
    assert CATEGORY_FORMAT not in findings

    # With check_format=True
    findings_on = track_findings(
        entry,
        mp3_file,
        artwork_min_px=600,
        check_format=True,
        target_format='mp3',
        target_bitrate_kbps=320,
    )
    assert CATEGORY_FORMAT in findings_on


def test_format_upgrade_requires_verified_match(
    tmp_path: Path, monkeypatch: Any
) -> None:
    from downtify.library_upgrade import CATEGORY_FORMAT, JOB_FAILED

    ctx = _context(tmp_path)
    track = _write_track(ctx.download_dir / 'track.mp3')
    orig_content = track.read_bytes()

    # Monkeypatch find_match to simulate no match found
    monkeypatch.setattr(
        'downtify.providers.find_match', lambda _s: (None, None)
    )

    deps = UpgradeDeps(
        context=lambda: ctx,
        settings=lambda: {
            'redownload_improper_format': True,
            'format': 'flac',
            'bitrate': '320',
        },
    )
    options = UpgradeOptions(
        categories=(CATEGORY_FORMAT,),
        check_format=True,
        target_format='flac',
        target_bitrate=320,
    )

    outcome = upgrade_track('track.mp3', deps=deps, options=options)
    assert outcome.status == JOB_FAILED
    assert 'No verified audio match' in outcome.detail
    # Original file must remain untouched!
    assert track.read_bytes() == orig_content


def test_format_upgrade_downloads_and_replaces_safely(
    tmp_path: Path, monkeypatch: Any
) -> None:
    from downtify.library_upgrade import CATEGORY_FORMAT, JOB_DONE

    ctx = _context(tmp_path)
    track = _write_track(ctx.download_dir / 'track.mp3')

    # Mock verified match
    monkeypatch.setattr(
        'downtify.providers.find_match', lambda _s: ('video_match_123', None)
    )

    class FakeDownloader:
        def fetch_audio(self, video_id, target_dir, basename, **kwargs):
            fmt = kwargs.get('audio_format') or 'mp3'
            staged = target_dir / f'{basename}.{fmt}'
            # Write a valid audio stream
            staged.write_bytes(_MP3_FRAME * 100)
            return staged

    deps = UpgradeDeps(
        context=lambda: ctx,
        settings=lambda: {
            'redownload_improper_format': True,
            'format': 'mp3',
            'bitrate': '320',
        },
        downloader=lambda: FakeDownloader(),
    )
    options = UpgradeOptions(
        categories=(CATEGORY_FORMAT,),
        check_format=True,
        target_format='mp3',
        target_bitrate=320,
    )

    outcome = upgrade_track('track.mp3', deps=deps, options=options)
    assert outcome.status == JOB_DONE
    assert 'format' in outcome.detail
    assert track.is_file()


def test_format_upgrade_extension_change_and_hooks(
    tmp_path: Path, monkeypatch: Any
) -> None:
    from downtify.library_upgrade import CATEGORY_FORMAT, JOB_DONE

    ctx = _context(tmp_path)
    old_track = _write_track(ctx.download_dir / 'track.mp3')

    monkeypatch.setattr(
        'downtify.providers.find_match', lambda _s: ('video_match_flac', None)
    )
    monkeypatch.setattr(
        'downtify.library_upgrade._audio_length', lambda _p: 180.0
    )
    monkeypatch.setattr(
        'downtify.library_upgrade.embed_metadata', lambda *a, **k: None
    )

    class FakeDownloader:
        def fetch_audio(self, video_id, target_dir, basename, **kwargs):
            fmt = kwargs.get('audio_format') or 'flac'
            staged = target_dir / f'{basename}.{fmt}'
            staged.write_bytes(b'FLAC_MOCK_DATA_12345')
            return staged

    path_changed_calls = []

    def on_path_changed(old, new, full):
        path_changed_calls.append((old, new, full))

    deps = UpgradeDeps(
        context=lambda: ctx,
        settings=lambda: {
            'redownload_improper_format': True,
            'format': 'flac',
            'bitrate': '320',
        },
        downloader=lambda: FakeDownloader(),
        on_track_path_changed=on_path_changed,
    )
    options = UpgradeOptions(
        categories=(CATEGORY_FORMAT,),
        check_format=True,
        target_format='flac',
        target_bitrate=320,
    )

    outcome = upgrade_track('track.mp3', deps=deps, options=options)
    assert outcome.status == JOB_DONE
    assert outcome.new_path == 'track.flac'
    assert not old_track.exists()
    new_track = ctx.download_dir / 'track.flac'
    assert new_track.is_file()
    assert len(path_changed_calls) == 1
    assert path_changed_calls[0] == ('track.mp3', 'track.flac', new_track)


def test_track_format_improper_with_source_targets(tmp_path: Path) -> None:
    from downtify.library_upgrade import track_format_improper

    mp3_file = _write_track(tmp_path / 'song.mp3')
    entry = {'file': 'song.mp3', 'bitrate': 320000}

    # If source_targets specifies FLAC for top provider, MP3 is improper
    assert track_format_improper(
        entry,
        mp3_file,
        source_targets={'slskd': [{'format': 'flac', 'bitrate': 'lossless'}]},
        audio_providers=['slskd'],
    )

    # If source_targets specifies MP3 320, MP3 at 320 is proper
    assert not track_format_improper(
        entry,
        mp3_file,
        source_targets={'slskd': [{'format': 'mp3', 'bitrate': '320'}]},
        audio_providers=['slskd'],
    )


def test_format_upgrade_with_slskd_source(
    tmp_path: Path, monkeypatch: Any
) -> None:
    from downtify.library_upgrade import CATEGORY_FORMAT, JOB_DONE

    ctx = _context(tmp_path)
    old_track = _write_track(ctx.download_dir / 'track.mp3')

    slskd_staged = tmp_path / 'slskd_download.flac'
    slskd_staged.write_bytes(b'FLAC_SLSKD_MOCK_123')

    monkeypatch.setattr(
        'downtify.library_upgrade.download_from_slskd',
        lambda song, settings, **kwargs: slskd_staged,
    )
    monkeypatch.setattr(
        'downtify.library_upgrade._audio_length', lambda _p: 180.0
    )
    monkeypatch.setattr(
        'downtify.library_upgrade.embed_metadata', lambda *a, **k: None
    )

    deps = UpgradeDeps(
        context=lambda: ctx,
        settings=lambda: {
            'redownload_improper_format': True,
            'audio_providers': ['slskd'],
            'slskd': {'enabled': True},
        },
        downloader=lambda: None,
    )
    options = UpgradeOptions(
        categories=(CATEGORY_FORMAT,),
        check_format=True,
        source_targets={'slskd': [{'format': 'flac', 'bitrate': 'lossless'}]},
        audio_providers=['slskd'],
    )

    outcome = upgrade_track('track.mp3', deps=deps, options=options)
    assert outcome.status == JOB_DONE
    assert outcome.new_path == 'track.flac'
    assert not old_track.exists()
    assert (ctx.download_dir / 'track.flac').is_file()


def test_format_upgrade_slskd_fails_falls_back_to_ytm(
    tmp_path: Path, monkeypatch: Any
) -> None:
    from downtify.library_upgrade import CATEGORY_FORMAT, JOB_DONE

    ctx = _context(tmp_path)
    old_track = _write_track(ctx.download_dir / 'track.mp3')

    monkeypatch.setattr(
        'downtify.library_upgrade.download_from_slskd',
        lambda song, settings, **kwargs: None,
    )
    monkeypatch.setattr(
        'downtify.library_upgrade.find_match_youtube_music_only',
        lambda song: ('video_match_123', None),
    )
    monkeypatch.setattr(
        'downtify.library_upgrade._audio_length', lambda _p: 180.0
    )
    monkeypatch.setattr(
        'downtify.library_upgrade.embed_metadata', lambda *a, **k: None
    )

    class FakeDownloader:
        def fetch_audio(self, video_id, target_dir, basename, **kwargs):
            staged = target_dir / f'{basename}.mp3'
            staged.write_bytes(b'MP3_YTM_DATA')
            return staged

    deps = UpgradeDeps(
        context=lambda: ctx,
        settings=lambda: {
            'redownload_improper_format': True,
            'audio_providers': ['slskd', 'youtube-music'],
            'slskd': {'enabled': True},
        },
        downloader=lambda: FakeDownloader(),
    )
    options = UpgradeOptions(
        categories=(CATEGORY_FORMAT,),
        check_format=True,
        source_targets={
            'slskd': [{'format': 'flac', 'bitrate': 'lossless'}],
            'youtube-music': [{'format': 'mp3', 'bitrate': '320'}],
        },
        audio_providers=['slskd', 'youtube-music'],
    )

    outcome = upgrade_track('track.mp3', deps=deps, options=options)
    assert outcome.status == JOB_DONE
    assert (ctx.download_dir / 'track.mp3').is_file()


def test_format_upgrade_with_existing_lyrics(
    tmp_path: Path, monkeypatch: Any
) -> None:
    from downtify.library_upgrade import CATEGORY_FORMAT, JOB_DONE

    ctx = _context(tmp_path)
    old_track = _write_track(ctx.download_dir / 'track.mp3')
    # Existing LRC sidecar
    lrc_file = old_track.with_suffix('.lrc')
    lrc_file.write_text('[00:01.00] Existing line\n[00:05.00] Another line')

    monkeypatch.setattr(
        'downtify.library_upgrade.download_from_slskd',
        lambda song, settings, **kwargs: None,
    )
    monkeypatch.setattr(
        'downtify.library_upgrade.find_match_youtube_music_only',
        lambda song: ('video_match_lyrics', None),
    )
    monkeypatch.setattr(
        'downtify.library_upgrade._audio_length', lambda _p: 180.0
    )
    monkeypatch.setattr(
        'downtify.library_upgrade.embed_metadata', lambda *a, **k: None
    )

    embedded_lyrics: list[Any] = []
    monkeypatch.setattr(
        'downtify.library_upgrade.embed_lyrics',
        lambda path, lyrics, **kwargs: embedded_lyrics.append(lyrics),
    )

    class FakeDownloader:
        def fetch_audio(self, video_id, target_dir, basename, **kwargs):
            staged = target_dir / f'{basename}.mp3'
            staged.write_bytes(b'MP3_YTM_DATA')
            return staged

    deps = UpgradeDeps(
        context=lambda: ctx,
        settings=lambda: {
            'redownload_improper_format': True,
            'audio_providers': ['youtube-music'],
        },
        downloader=lambda: FakeDownloader(),
    )
    options = UpgradeOptions(
        categories=(CATEGORY_FORMAT,),
        check_format=True,
        source_targets={
            'youtube-music': [{'format': 'mp3', 'bitrate': '320'}],
        },
        audio_providers=['youtube-music'],
    )

    outcome = upgrade_track('track.mp3', deps=deps, options=options)
    assert outcome.status == JOB_DONE
    assert len(embedded_lyrics) == 1
    assert (
        embedded_lyrics[0].synced
        == '[00:01.00] Existing line\n[00:05.00] Another line'
    )


def test_format_upgrade_flac_to_opus_with_ytm(
    tmp_path: Path, monkeypatch: Any
) -> None:
    from downtify.library_upgrade import CATEGORY_FORMAT, JOB_DONE

    ctx = _context(tmp_path)
    ctx.download_dir.mkdir(parents=True, exist_ok=True)
    # Existing track on disk is FLAC
    flac_file = ctx.download_dir / 'track.flac'
    flac_file.write_bytes(b'FLAC_MOCK_EXISTING_CONTENT')

    monkeypatch.setattr(
        'downtify.library_upgrade.find_match_youtube_music_only',
        lambda song: ('video_match_ytm', None),
    )
    monkeypatch.setattr(
        'downtify.library_upgrade._audio_length', lambda _p: 200.0
    )
    monkeypatch.setattr(
        'downtify.library_upgrade.embed_metadata', lambda *a, **k: None
    )

    class FakeDownloader:
        def fetch_audio(self, video_id, target_dir, basename, **kwargs):
            fmt = kwargs.get('audio_format') or 'opus'
            staged = target_dir / f'{basename}.{fmt}'
            staged.write_bytes(b'OPUS_NEW_AUDIO_CONTENT')
            return staged

    deps = UpgradeDeps(
        context=lambda: ctx,
        settings=lambda: {
            'redownload_improper_format': True,
            'audio_providers': ['youtube-music'],
        },
        downloader=lambda: FakeDownloader(),
    )
    options = UpgradeOptions(
        categories=(CATEGORY_FORMAT,),
        check_format=True,
        source_targets={
            'youtube-music': [{'format': 'opus', 'bitrate': '256'}],
        },
        audio_providers=['youtube-music'],
    )

    outcome = upgrade_track('track.flac', deps=deps, options=options)
    assert outcome.status == JOB_DONE
    assert outcome.new_path == 'track.opus'
    assert not flac_file.exists()
    assert (ctx.download_dir / 'track.opus').is_file()


def test_runner_start_auto_upgrade(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    runner = _runner(tmp_path, ctx)
    opts = UpgradeOptions(categories=('artwork', 'lyrics'), artwork_min_px=600)
    runner.start_auto_upgrade(['artwork', 'lyrics'], opts)
    _wait(runner)
    status = runner.status()
    assert status['state'] in {STATE_DONE, STATE_READY}


def test_format_already_satisfied_on_fallback_proceeds_to_artwork(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """When primary provider (slskd FLAC) is unavailable and fallback (ytm MP3 128)
    is already satisfied by the existing file, upgrade_track must not raise
    ValueError/UnboundLocalError and must proceed to upgrade artwork."""
    from downtify.library_upgrade import CATEGORY_FORMAT, JOB_DONE

    ctx = _context(tmp_path)
    track = _write_track(ctx.download_dir / 'track.mp3', cover_px=300)
    _stub_cover(monkeypatch, 1200)
    monkeypatch.setattr(
        'downtify.library_upgrade.download_from_slskd',
        lambda song, settings, **kwargs: None,
    )

    deps = UpgradeDeps(
        context=lambda: ctx,
        settings=lambda: {
            'redownload_improper_format': True,
            'audio_providers': ['slskd', 'youtube-music'],
            'slskd': {'enabled': True},
        },
    )
    options = UpgradeOptions(
        categories=(CATEGORY_ARTWORK, CATEGORY_FORMAT),
        artwork_min_px=600,
        check_format=True,
        source_targets={
            'slskd': [{'format': 'flac', 'bitrate': 'lossless'}],
            'youtube-music': [{'format': 'mp3', 'bitrate': '128'}],
        },
        audio_providers=['slskd', 'youtube-music'],
    )

    outcome = upgrade_track('track.mp3', deps=deps, options=options)
    assert outcome.status == JOB_DONE
    assert outcome.changed == [CATEGORY_ARTWORK]
    assert ID3(str(track)).getall('APIC')[0].data == _png(1200)


def test_artwork_locked_preserved_after_metadata_cache_refresh(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    track = _write_track(ctx.download_dir / 'locked.mp3', cover_px=300)
    entry = _entry(ctx, 'locked.mp3')
    ctx.metadata_cache.set_track_artwork(
        entry.get('content_key') or '',
        cover_px=300,
        locked=True,
        track_path='locked.mp3',
    )
    refreshed = ctx.metadata_cache.refresh('locked.mp3', track)
    assert refreshed is not None
    assert refreshed.get('artwork_locked') is True
    found = track_findings(refreshed, track, artwork_min_px=600)
    assert CATEGORY_ARTWORK not in found


