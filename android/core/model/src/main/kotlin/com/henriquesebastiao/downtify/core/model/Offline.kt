package com.henriquesebastiao.downtify.core.model

/**
 * An album, a playlist or Liked songs the user keeps on the phone. The tracks
 * it stands for follow the library: a song added to a kept album on the server
 * downloads too, a removed one is deleted.
 */
data class OfflineCollection(
    /** [PlaybackContextType.Album], [PlaybackContextType.Playlist] or [PlaybackContextType.Liked]. */
    val type: PlaybackContextType,
    /** Album id or playlist name; blank for Liked songs. */
    val refId: String,
    /** Unix millis. Older collections download first and keep their place when space runs out. */
    val addedAt: Long,
) {
    val key: String get() = keyOf(type, refId)

    companion object {
        val KEEPABLE = setOf(PlaybackContextType.Album, PlaybackContextType.Playlist, PlaybackContextType.Liked)

        fun keyOf(type: PlaybackContextType, refId: String): String = "${type.name}:$refId"
    }
}

/** A complete offline copy of a track on the phone. */
data class OfflineFile(val trackId: String, val fileName: String, val bytes: Long)

/** What should be on the phone, given the kept collections, the files there and the storage limit. */
data class OfflinePlan(
    /** Wanted, not on the phone yet, and within the limit — in download order. */
    val toDownload: List<Track>,
    /** Track ids that stay (on the phone or about to be). */
    val keep: Set<String>,
    /** Files no kept collection wants anymore, or that no longer fit the limit. */
    val toDelete: Set<String>,
    /** Wanted, but beyond the storage limit. */
    val overLimit: Set<String>,
    /** Bytes [keep] takes once everything is downloaded. */
    val plannedBytes: Long,
) {
    companion object {
        val Empty = OfflinePlan(emptyList(), emptySet(), emptySet(), emptySet(), 0)
    }
}

object OfflinePlanner {
    /** No limit on offline storage. */
    const val UNLIMITED = Long.MAX_VALUE

    /**
     * Plans the offline copies for [wanted] (tracks in priority order, possibly
     * repeated across collections) against [files] on the phone.
     *
     * Tracks are taken in order while they fit in [limitBytes]; one that doesn't
     * fit is skipped (a smaller one after it may still fit), so lowering the
     * limit trims the newest collections first. A track on the phone counts its
     * real size, one to download the size the library reports.
     */
    fun plan(wanted: List<Track>, files: Map<String, OfflineFile>, limitBytes: Long): OfflinePlan {
        val keep = LinkedHashSet<String>()
        val toDownload = mutableListOf<Track>()
        val overLimit = mutableSetOf<String>()
        var planned = 0L
        for (track in wanted.distinctBy { it.id }) {
            val size = files[track.id]?.bytes ?: track.size.coerceAtLeast(0)
            if (limitBytes != UNLIMITED && planned + size > limitBytes) {
                overLimit += track.id
            } else {
                planned += size
                keep += track.id
                if (track.id !in files) toDownload += track
            }
        }
        return OfflinePlan(
            toDownload = toDownload,
            keep = keep,
            toDelete = files.keys - keep,
            overLimit = overLimit,
            plannedBytes = planned,
        )
    }
}

/** How much of one kept collection is on the phone. */
data class OfflineProgress(val total: Int, val downloaded: Int, val bytes: Long, val overLimit: Int) {
    val isComplete: Boolean get() = total > 0 && downloaded == total

    companion object {
        fun of(tracks: List<Track>, files: Map<String, OfflineFile>, plan: OfflinePlan): OfflineProgress {
            val ids = tracks.map { it.id }.distinct()
            val onPhone = ids.mapNotNull { files[it] }
            return OfflineProgress(
                total = ids.size,
                downloaded = onPhone.size,
                bytes = onPhone.sumOf { it.bytes },
                overLimit = ids.count { it in plan.overLimit },
            )
        }
    }
}
