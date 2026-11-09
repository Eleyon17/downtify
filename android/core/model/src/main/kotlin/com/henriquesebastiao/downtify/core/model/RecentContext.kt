package com.henriquesebastiao.downtify.core.model

/** Something the user played from, for Home's "Jump back in". */
data class RecentContext(
    val type: PlaybackContextType,
    /** Album id, artist id or playlist name; blank for Liked songs and the whole library. */
    val refId: String,
    val title: String,
    val coverTrackId: String?,
    val playedAt: Long,
) {
    val key: String get() = "${type.name}:$refId"
}

enum class PlaybackContextType { Album, Artist, Playlist, Liked, Songs }

/** Where the queue came from: shown in Now Playing ("Playing from album") and recorded for Home. */
data class PlaybackContext(val type: PlaybackContextType, val refId: String, val title: String)
