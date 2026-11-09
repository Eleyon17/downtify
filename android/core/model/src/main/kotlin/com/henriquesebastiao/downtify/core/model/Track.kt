package com.henriquesebastiao.downtify.core.model

/**
 * One library track, as the server's `/api/v1/library` feed describes it.
 *
 * [id] is stable across moves and renames of the file: key everything local
 * (likes, queue, history, offline copies) by it, never by [file].
 */
data class Track(
    val id: String,
    val file: String,
    val title: String,
    val artist: String,
    val artists: List<String>,
    val album: String,
    val albumArtist: String,
    val albumId: String,
    val artistId: String,
    val trackNumber: Int,
    val year: String,
    /** Length in seconds. */
    val duration: Double,
    val codec: String,
    /** Bits per second. */
    val bitrate: Int,
    val sampleRate: Int,
    val channels: Int,
    /** Bytes. */
    val size: Long,
    /** Unix seconds when the file was added to the library. */
    val added: Long,
    val hasCover: Boolean,
    val playlists: List<String>,
) {
    /** What to show as the title: the tag, else the file name without extension. */
    val displayTitle: String
        get() = title.ifBlank { file.substringAfterLast('/').substringBeforeLast('.') }

    val displayArtist: String
        get() = artist.ifBlank { albumArtist }

    val isLossless: Boolean
        get() = codec in LOSSLESS_CODECS

    companion object {
        val LOSSLESS_CODECS = setOf("flac", "alac", "wav")
    }
}
