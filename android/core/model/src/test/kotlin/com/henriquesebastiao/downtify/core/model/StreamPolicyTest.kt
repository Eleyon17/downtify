package com.henriquesebastiao.downtify.core.model

import org.junit.Assert.assertEquals
import org.junit.Test

class StreamPolicyTest {
    private val transcoding =
        Transcoding(
            available = true,
            formats = listOf("aac", "mp3", "opus"),
            bitrates = listOf(96, 128, 160, 192, 256, 320),
        )
    private val opus160 = StreamQuality(StreamFormat.Opus, 160)

    @Test
    fun `wifi streams the wifi quality, metered the mobile one`() {
        assertEquals(
            StreamQuality.Original,
            StreamPolicy.select(StreamQuality.Original, opus160, isMetered = false, transcoding),
        )
        assertEquals(opus160, StreamPolicy.select(StreamQuality.Original, opus160, isMetered = true, transcoding))
    }

    @Test
    fun `falls back to the original without transcoding or an unknown format`() {
        assertEquals(
            StreamQuality.Original,
            StreamPolicy.select(StreamQuality.Original, opus160, true, Transcoding(available = false)),
        )
        val onlyMp3 = transcoding.copy(formats = listOf("mp3"))
        assertEquals(StreamQuality.Original, StreamPolicy.select(StreamQuality.Original, opus160, true, onlyMp3))
    }

    @Test
    fun `rounds the bitrate up to one the server offers`() {
        val odd = StreamQuality(StreamFormat.Aac, 150)
        assertEquals(StreamQuality(StreamFormat.Aac, 160), StreamPolicy.select(odd, odd, false, transcoding))
        assertEquals(320, StreamPolicy.supportedBitrate(999, transcoding.bitrates))
        assertEquals(96, StreamPolicy.supportedBitrate(10, emptyList()))
    }

    @Test
    fun `builds stream and cover paths`() {
        assertEquals("/api/v1/tracks/t7b2/stream", StreamPolicy.streamPath("t7b2", StreamQuality.Original))
        assertEquals("/api/v1/tracks/t7b2/stream?format=opus&bitrate=160", StreamPolicy.streamPath("t7b2", opus160))
        assertEquals(
            "/api/v1/tracks/t7b2/stream?format=mp3&bitrate=320&download=true",
            StreamPolicy.streamPath("t7b2", StreamQuality(StreamFormat.Mp3, 320), download = true),
        )
        assertEquals("/api/v1/tracks/t7b2/cover?size=300", StreamPolicy.coverPath("t7b2", 300))
        assertEquals("/api/v1/tracks/t7b2/cover", StreamPolicy.coverPath("t7b2", null))
    }

    @Test
    fun `quality survives encoding for settings`() {
        listOf(StreamQuality.Original, opus160, StreamQuality(StreamFormat.Mp3, 320)).forEach {
            assertEquals(it, StreamQuality.decode(it.encode()))
        }
        assertEquals(null, StreamQuality.decode("flac/100"))
    }
}
