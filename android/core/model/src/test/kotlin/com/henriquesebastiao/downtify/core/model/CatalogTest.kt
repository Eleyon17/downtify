package com.henriquesebastiao.downtify.core.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CatalogTest {
    @Test
    fun recognisesLinksTheServerResolves() {
        listOf(
            "https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC",
            "https://open.spotify.com/intl-pt/album/1DFixLWuPkv3KT3TnV35m3?si=x",
            "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
            "https://open.spotify.com/artist/0p4nmQO2msCgU4IF37Wi3j",
            "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://music.youtube.com/playlist?list=OLAK5uy_abc",
            "https://music.youtube.com/browse/MPREb_abc",
            "https://music.youtube.com/channel/UCabc",
            "https://www.youtube.com/@someone",
            "https://youtu.be/dQw4w9WgXcQ",
            "  https://youtu.be/dQw4w9WgXcQ  ",
        ).forEach { assertTrue(it, CatalogLinks.isLink(it)) }
    }

    @Test
    fun wordsAndOtherLinksAreSearchedInstead() {
        listOf(
            "harbor",
            "portishead roads",
            "open.spotify.com/track/abc",
            "https://example.com/track/abc",
            "https://open.spotify.com/",
            "https://music.youtube.com/",
            "https://open.spotify.com/track/abc and more",
        ).forEach { assertFalse(it, CatalogLinks.isLink(it)) }
    }

    @Test
    fun playlistLinks() {
        assertTrue(CatalogLinks.isPlaylist("https://open.spotify.com/playlist/37i9"))
        assertTrue(CatalogLinks.isPlaylist("https://music.youtube.com/playlist?list=PL1"))
        assertFalse(CatalogLinks.isPlaylist("https://open.spotify.com/album/1DF"))
    }

    private fun job(id: String, album: String, status: ServerJobStatus) =
        ServerJob(id, "Song $id", "A", album, "", status, 0f, "")

    @Test
    fun queueSummaryFollowsTheAlbumBeingDownloaded() {
        val jobs = listOf(
            job("1", "Harbor Nights", ServerJobStatus.Done),
            job("2", "Harbor Nights", ServerJobStatus.Downloading),
            job("3", "Harbor Nights", ServerJobStatus.Queued),
            job("4", "Other", ServerJobStatus.Queued),
            job("5", "Old", ServerJobStatus.Error),
        )
        assertEquals(ServerQueueSummary(3, "Harbor Nights", 1, 3), ServerQueueSummary.of(jobs))
    }

    @Test
    fun anIdleQueueSummarisesToNothing() {
        val summary = ServerQueueSummary.of(listOf(job("1", "A", ServerJobStatus.Done)))
        assertEquals(0, summary.active)
    }

    @Test
    fun progressOfAnAlbumsSongs() {
        val jobs = listOf(
            job("1", "X", ServerJobStatus.Done),
            job("2", "X", ServerJobStatus.Error),
            job("3", "X", ServerJobStatus.Downloading),
        ).associateBy { it.songId }
        val progress = ServerDownloadProgress.of(listOf("1", "2", "3", "4"), jobs)!!
        assertEquals(ServerDownloadProgress(done = 1, total = 4, failed = 1), progress)
        assertTrue(progress.isActive)
        assertNull(ServerDownloadProgress.of(listOf("9"), jobs))
    }

    @Test
    fun sourcesFromTheWire() {
        assertEquals(CatalogSource.Spotify, CatalogSource.of("spotify"))
        assertEquals(CatalogSource.YouTube, CatalogSource.of("youtube"))
        assertEquals(CatalogSource.TextSearch, CatalogSource.of("text_search"))
        assertEquals(CatalogSource.Other, CatalogSource.of("deezer"))
    }
}
