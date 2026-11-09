package com.henriquesebastiao.downtify.ui.common

import com.henriquesebastiao.downtify.core.model.LibraryGrouping
import com.henriquesebastiao.downtify.core.model.Playlist
import com.henriquesebastiao.downtify.core.model.Track

/** Sample library for previews and UI tests. */
object PreviewData {
    private fun track(
        id: String,
        title: String,
        artist: String,
        album: String,
        number: Int,
        year: String,
        seconds: Double,
    ) = Track(
        id = id, file = "$artist - $title.flac", title = title, artist = artist,
        artists = listOf(
            artist,
        ),
        album = album,
        albumArtist = artist, albumId = "alb-$album", artistId = "art-$artist", trackNumber = number, year = year,
        duration = seconds, codec = "flac", bitrate = 912_000, sampleRate = 44_100, channels = 2, size = 30_000_000,
        added = 1_789_600_000L + number, hasCover = true, playlists = emptyList(),
    )

    val tracks = listOf(
        track("t1", "Low Tide", "Kenji Aoki", "Glass Harbor", 1, "2023", 221.0),
        track("t2", "Undertow", "Kenji Aoki", "Glass Harbor", 2, "2023", 239.0),
        track("t3", "Salt & Glass", "Kenji Aoki", "Glass Harbor", 3, "2023", 252.0),
        track("t4", "Harbor Lights", "Kenji Aoki", "Glass Harbor", 4, "2023", 208.0),
        track("t5", "Paper Lanterns", "Kenji Aoki", "Glass Harbor", 5, "2023", 306.0),
        track("t6", "Afterglow", "Dani Rivera", "Afterglow Season", 1, "2024", 198.0),
        track("t7", "Cassette Weather", "Nora Vale", "Cassette Weather", 1, "2022", 244.0),
        track("t8", "Midnight Atlas", "Orsa", "Midnight Atlas", 1, "2025", 275.0),
    )
    val albums = LibraryGrouping.albums(tracks)
    val artists = LibraryGrouping.artists(tracks)
    val playlists = listOf(
        Playlist("Deep Focus", liked = false, cover = "", trackIds = listOf("t1", "t5", "t8")),
        Playlist("Late Night Drive", liked = false, cover = "", trackIds = listOf("t2", "t7")),
    )
}
