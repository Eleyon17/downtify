package com.henriquesebastiao.downtify.core.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PodcastsTest {
    private fun episode(
        position: Double = 0.0,
        played: Boolean = false,
        duration: Int = 1_800,
        filename: String? = "Podcasts/Show/e.mp3",
    ) = PodcastEpisode(1, 1, "T", "", "2026-09-18T14:00:00+00:00", duration, null, 712, filename, position, played)

    @Test
    fun anEpisodeNearItsEndCountsAsPlayed() {
        assertTrue(PodcastProgress.isNearlyDone(1_797.0, 1_800))
        assertFalse(PodcastProgress.isNearlyDone(1_796.9, 1_800))
        assertFalse(PodcastProgress.isNearlyDone(500.0, 0))
        assertEquals(EpisodeProgress(42.5, false), PodcastProgress.toSave(42.5, 1_800))
        assertEquals(EpisodeProgress(1_799.0, true), PodcastProgress.toSave(1_799.0, 1_800))
        assertEquals(EpisodeProgress(0.0, false), PodcastProgress.toSave(-3.0, 1_800))
    }

    @Test
    fun resumesOnlyWhenThereIsSomethingToResume() {
        assertEquals(754, episode(position = 754.4).resumeAtSeconds)
        assertNull(episode(position = 4.0).resumeAtSeconds)
        assertNull(episode(position = 900.0, played = true).resumeAtSeconds)
        assertNull(episode(position = 1_799.0).resumeAtSeconds)
    }

    @Test
    fun howMuchWasHeard() {
        assertEquals(0.5f, episode(position = 900.0).heard, 0.001f)
        assertEquals(1f, episode(played = true).heard, 0f)
        assertEquals(0f, episode(position = 30.0, duration = 0).heard, 0f)
    }

    @Test
    fun downloadedWhenTheServerHasTheFile() {
        assertTrue(episode().isDownloaded)
        assertFalse(episode(filename = null).isDownloaded)
        assertFalse(episode(filename = "").isDownloaded)
    }

    @Test
    fun mediaIdsAreRecognised() {
        assertEquals("episode:42", EpisodeIds.mediaId(42))
        assertTrue(EpisodeIds.isEpisode("episode:42"))
        assertFalse(EpisodeIds.isEpisode("t7b255c87668ba03b"))
        assertFalse(EpisodeIds.isEpisode(null))
        assertEquals(42L, EpisodeIds.episodeIdOf("episode:42"))
        assertNull(EpisodeIds.episodeIdOf("t7b2"))
        assertNull(EpisodeIds.episodeIdOf("episode:x"))
    }

    @Test
    fun theFileUrlEncodesEachSegment() {
        assertEquals(
            "http://nas:8000/downloads/Podcasts/Radiolab/2026-09-18%20-%20The%20Sweetest%20Thing.mp3",
            EpisodeIds.fileUrl("http://nas:8000/", "Podcasts/Radiolab/2026-09-18 - The Sweetest Thing.mp3"),
        )
        assertEquals(
            "https://x.example/dtfy/downloads/Podcasts/A%26B%20%23%201/caf%C3%A9.mp3",
            EpisodeIds.fileUrl("https://x.example/dtfy", "Podcasts/A&B # 1/café.mp3"),
        )
    }

    @Test
    fun speedsCycleThroughTheList() {
        assertEquals(1.25f, PlaybackSpeeds.next(1f), 0f)
        assertEquals(2f, PlaybackSpeeds.next(1.5f), 0f)
        assertEquals(0.75f, PlaybackSpeeds.next(2f), 0f)
        assertEquals(1f, PlaybackSpeeds.next(0.75f), 0f)
        assertEquals(1.25f, PlaybackSpeeds.next(1.1f), 0f)
    }
}
