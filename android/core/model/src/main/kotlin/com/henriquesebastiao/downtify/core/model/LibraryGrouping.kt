package com.henriquesebastiao.downtify.core.model

/**
 * Albums and artists from a flat track list, grouped exactly like the web app:
 * by the server's `album_id` and `artist_id` (a blank key means "no album" or
 * "no artist", and such tracks are left out of that grouping).
 */
object LibraryGrouping {

    /** Track order inside an album: track number, then title. Tracks without a number go last. */
    val albumTrackOrder: Comparator<Track> = compareBy<Track> {
        if (it.trackNumber >
            0
        ) {
            it.trackNumber
        } else {
            Int.MAX_VALUE
        }
    }
        .thenBy(String.CASE_INSENSITIVE_ORDER) { it.displayTitle }

    fun albums(tracks: Iterable<Track>): List<Album> = tracks
        .filter { it.albumId.isNotEmpty() }
        .groupBy { it.albumId }
        .map { (id, group) -> albumOf(id, group) }

    fun artists(tracks: Iterable<Track>): List<Artist> {
        val all = tracks.filter { it.artistId.isNotEmpty() }
        val albumsByArtist = albums(all).groupBy { it.artistId }
        return all.groupBy { it.artistId }.map { (id, group) ->
            Artist(
                id = id,
                name = mostCommon(group.map { it.albumArtist }),
                albums = albumsByArtist[id].orEmpty().sortedWith(albumsNewestFirst),
                tracks = group.sortedWith(compareBy(String.CASE_INSENSITIVE_ORDER) { it.displayTitle }),
            )
        }
    }

    fun albumOf(id: String, group: List<Track>): Album {
        val sorted = group.sortedWith(albumTrackOrder)
        return Album(
            id = id,
            title = mostCommon(sorted.map { it.album }),
            artist = mostCommon(sorted.map { it.albumArtist }),
            artistId = sorted.first().artistId,
            year = mostCommon(sorted.map { it.year }),
            tracks = sorted,
            added = sorted.maxOf { it.added },
        )
    }

    private val albumsNewestFirst = compareByDescending<Album> { it.year }
        .thenBy(String.CASE_INSENSITIVE_ORDER) { it.title }

    /** The most frequent non-blank value (first seen wins a tie), or blank. */
    private fun mostCommon(values: List<String>): String = values
        .filter { it.isNotBlank() }
        .groupingBy { it }
        .eachCount()
        .maxByOrNull { it.value }
        ?.key
        .orEmpty()
}
