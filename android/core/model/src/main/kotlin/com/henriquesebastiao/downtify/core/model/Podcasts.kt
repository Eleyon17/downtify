package com.henriquesebastiao.downtify.core.model

/** A podcast the server is subscribed to (`GET /api/podcasts/shows`). */
data class PodcastShow(
    val id: Long,
    val name: String,
    val author: String,
    val description: String,
    /** The publisher's artwork: an address on their site, not on the server. */
    val artworkUrl: String,
    val episodeCount: Int,
    val downloadedCount: Int,
)

/** One episode of a show, with what the server knows of this user's progress in it. */
data class PodcastEpisode(
    val id: Long,
    val showId: Long,
    val title: String,
    val description: String,
    /** ISO 8601, or blank. */
    val publishedAt: String,
    val durationSeconds: Int,
    val seasonNumber: Int?,
    val episodeNumber: Int?,
    /** The library path of the downloaded file (`Podcasts/Show/…mp3`), or null until the server has it. */
    val filename: String?,
    val positionSeconds: Double,
    val played: Boolean,
) {
    val isDownloaded: Boolean get() = !filename.isNullOrBlank()

    /** Where to pick up, or null when it wasn't started, is finished, or the resume point is negligible. */
    val resumeAtSeconds: Int?
        get() = positionSeconds.toInt().takeIf {
            !played && it >= MIN_RESUME_SECONDS && !PodcastProgress.isNearlyDone(positionSeconds, durationSeconds)
        }

    /** 0–1 of the episode already heard, for the bar under a partly played one. */
    val heard: Float
        get() = if (played) {
            1f
        } else if (durationSeconds > 0) {
            (positionSeconds / durationSeconds).toFloat().coerceIn(0f, 1f)
        } else {
            0f
        }

    private companion object {
        /** Below this a "resume" is just the start. */
        const val MIN_RESUME_SECONDS = 10
    }
}

/** The rules the web player uses to save an episode's place. */
object PodcastProgress {
    /** An episode this close to its end counts as played, even if the player never said "ended". */
    private const val NEARLY_DONE_SECONDS = 3

    /** How often the position is saved while an episode plays. */
    const val SAVE_EVERY_SECONDS = 10

    fun isNearlyDone(positionSeconds: Double, durationSeconds: Int): Boolean =
        durationSeconds > 0 && positionSeconds >= durationSeconds - NEARLY_DONE_SECONDS

    /** What to save when playback is at [positionSeconds]: the position, and `played` once it's nearly done. */
    fun toSave(positionSeconds: Double, durationSeconds: Int): EpisodeProgress =
        EpisodeProgress(positionSeconds.coerceAtLeast(0.0), isNearlyDone(positionSeconds, durationSeconds))
}

/** What [PodcastProgress] says to save with `PUT /api/podcasts/episodes/{id}/playback`. */
data class EpisodeProgress(val positionSeconds: Double, val played: Boolean)

/** How the player names and finds an episode among its media items. */
object EpisodeIds {
    private const val PREFIX = "episode:"

    fun mediaId(episodeId: Long): String = PREFIX + episodeId

    fun isEpisode(mediaId: String?): Boolean = mediaId != null && mediaId.startsWith(PREFIX)

    fun episodeIdOf(mediaId: String?): Long? =
        if (isEpisode(mediaId)) mediaId!!.removePrefix(PREFIX).toLongOrNull() else null

    /**
     * The address of a downloaded episode: `{base}/downloads/{filename}`, each
     * segment percent-encoded (file names hold spaces, `#`, `&` and accents).
     */
    fun fileUrl(baseUrl: String, filename: String): String =
        baseUrl.trimEnd('/') + "/downloads/" + filename.split('/').joinToString("/") { encodeSegment(it) }

    private fun encodeSegment(value: String): String = java.net.URLEncoder.encode(value, "UTF-8").replace("+", "%20")
}

/** The speeds an episode can play at, and the step from one to the next. */
object PlaybackSpeeds {
    val ALL = listOf(0.75f, 1f, 1.25f, 1.5f, 2f)

    /** The next speed up, wrapping from the fastest back to the slowest. */
    fun next(current: Float): Float = ALL.firstOrNull { it > current + EPSILON } ?: ALL.first()

    private const val EPSILON = 0.001f
}
