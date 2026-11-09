package com.henriquesebastiao.downtify.core.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class LibraryGroupingTest {

    @Test
    fun `albums group by album_id, not by title`() {
        val tracks = listOf(
            track("1", album = "Dummy", albumId = "a1", trackNumber = 2),
            track("2", album = "dummy", albumId = "a1", trackNumber = 1),
            // Same title, different album artist: a different album id.
            track("3", album = "Dummy", albumArtist = "Other", albumId = "a2"),
        )

        val albums = LibraryGrouping.albums(tracks).associateBy { it.id }

        assertEquals(2, albums.size)
        assertEquals(listOf("2", "1"), albums.getValue("a1").tracks.map { it.id })
        assertEquals(1, albums.getValue("a2").trackCount)
    }

    @Test
    fun `tracks without an album are left out of albums`() {
        val albums = LibraryGrouping.albums(listOf(track("1", album = "", albumId = ""), track("2", albumId = "a")))
        assertEquals(listOf("a"), albums.map { it.id })
    }

    @Test
    fun `album tracks sort by number, unnumbered last by title`() {
        val album = LibraryGrouping.albumOf(
            "a",
            listOf(
                track("x", title = "Zed", trackNumber = 0),
                track("y", title = "Alpha", trackNumber = 0),
                track("z", trackNumber = 1),
            ),
        )
        assertEquals(listOf("z", "y", "x"), album.tracks.map { it.id })
    }

    @Test
    fun `album takes the newest added time and the most common title`() {
        val album = LibraryGrouping.albumOf(
            "a",
            listOf(
                track("1", album = "Roads", added = 10),
                track("2", album = "Roads", added = 30),
                track("3", album = "roads", added = 20),
            ),
        )
        assertEquals(30, album.added)
        assertEquals("Roads", album.title)
    }

    @Test
    fun `cover comes from the first track that has one`() {
        val album = LibraryGrouping.albumOf(
            "a",
            listOf(track("1", trackNumber = 1, hasCover = false), track("2", trackNumber = 2, hasCover = true)),
        )
        assertEquals("2", album.coverTrackId)
        assertNull(LibraryGrouping.albumOf("b", listOf(track("3", hasCover = false))).coverTrackId)
    }

    @Test
    fun `artists group by artist_id with their albums`() {
        val tracks = listOf(
            track("1", albumArtist = "Portishead", album = "Dummy", artistId = "p", albumId = "d", year = "1994"),
            track("2", albumArtist = "Portishead", album = "Third", artistId = "p", albumId = "t", year = "2008"),
            track("3", albumArtist = "Massive Attack", album = "Mezzanine", artistId = "m", albumId = "z"),
            track("4", albumArtist = "", artistId = ""),
        )

        val artists = LibraryGrouping.artists(tracks).associateBy { it.id }

        assertEquals(setOf("p", "m"), artists.keys)
        val portishead = artists.getValue("p")
        assertEquals("Portishead", portishead.name)
        assertEquals(listOf("Third", "Dummy"), portishead.albums.map { it.title })
        assertEquals(2, portishead.tracks.size)
        assertTrue(artists.getValue("m").albums.single().id == "z")
    }
}
