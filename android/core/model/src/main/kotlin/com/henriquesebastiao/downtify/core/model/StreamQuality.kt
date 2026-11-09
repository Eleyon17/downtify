package com.henriquesebastiao.downtify.core.model

/** A format the server can stream in: the file as it is, or a transcoded copy. */
enum class StreamFormat(val wireName: String) {
    Original("original"),
    Opus("opus"),
    Aac("aac"),
    Mp3("mp3"),
    ;

    companion object {
        fun fromWire(value: String): StreamFormat? =
            entries.firstOrNull { it.wireName.equals(value, ignoreCase = true) }
    }
}

/** What to ask the server for: [StreamFormat.Original], or a format at [bitrate] kbps. */
data class StreamQuality(val format: StreamFormat, val bitrate: Int = 0) {
    val isOriginal: Boolean get() = format == StreamFormat.Original

    /** A compact form for storing in settings: `original` or `opus/160`. */
    fun encode(): String = if (isOriginal) format.wireName else "${format.wireName}/$bitrate"

    companion object {
        val Original = StreamQuality(StreamFormat.Original)

        /** The default for metered networks (the contract's suggestion). */
        val MobileDefault = StreamQuality(StreamFormat.Opus, 160)

        /** Bitrates the server offers (kbps), for when it doesn't list them. */
        val KNOWN_BITRATES = listOf(96, 128, 160, 192, 256, 320)

        fun decode(value: String?): StreamQuality? {
            if (value.isNullOrBlank()) return null
            val format = StreamFormat.fromWire(value.substringBefore('/')) ?: return null
            if (format == StreamFormat.Original) return Original
            val bitrate = value.substringAfter('/', "").toIntOrNull() ?: return null
            return StreamQuality(format, bitrate)
        }
    }
}

/** Picks the quality for a stream and builds the path for it. */
object StreamPolicy {

    /**
     * The quality to stream in: [wifi] on an unmetered network, [mobile] on a
     * metered one — falling back to the original file when the server can't
     * transcode, or doesn't offer the chosen format.
     */
    fun select(
        wifi: StreamQuality,
        mobile: StreamQuality,
        isMetered: Boolean,
        transcoding: Transcoding,
    ): StreamQuality {
        val wanted = if (isMetered) mobile else wifi
        if (wanted.isOriginal) return StreamQuality.Original
        if (!transcoding.available) return StreamQuality.Original
        if (transcoding.formats.isNotEmpty() && wanted.format.wireName !in transcoding.formats) {
            return StreamQuality.Original
        }
        return wanted.copy(bitrate = supportedBitrate(wanted.bitrate, transcoding.bitrates))
    }

    /** [kbps] rounded up to one the server offers (the server does the same), or the highest one. */
    fun supportedBitrate(kbps: Int, offered: List<Int>): Int {
        val list = offered.ifEmpty { StreamQuality.KNOWN_BITRATES }.sorted()
        return list.firstOrNull { it >= kbps } ?: list.last()
    }

    /** `/api/v1/tracks/{id}/stream`, with `format` and `bitrate` for a transcoded copy. */
    fun streamPath(trackId: String, quality: StreamQuality, download: Boolean = false): String {
        val params = buildList {
            if (!quality.isOriginal) {
                add("format=${quality.format.wireName}")
                add("bitrate=${quality.bitrate}")
            }
            if (download) add("download=true")
        }
        val path = "/api/v1/tracks/${encodeSegment(trackId)}/stream"
        return if (params.isEmpty()) path else path + "?" + params.joinToString("&")
    }

    /** `/api/v1/tracks/{id}/cover`, with `size` (150, 300 or 600) or full size when null. */
    fun coverPath(trackId: String, size: Int?): String {
        val path = "/api/v1/tracks/${encodeSegment(trackId)}/cover"
        return if (size == null) path else "$path?size=$size"
    }

    private fun encodeSegment(value: String): String = java.net.URLEncoder.encode(value, "UTF-8").replace("+", "%20")
}
