package com.henriquesebastiao.downtify.core.model

import org.junit.Assert.assertEquals
import org.junit.Test

class DiscoverTest {
    private val library = LibraryGrouping.artists(
        listOf(
            track("a1", albumArtist = "Portishead", album = "Dummy"),
            track("a2", albumArtist = "Portishead", album = "Dummy"),
            track("a3", albumArtist = "Portishead", album = "Third"),
            track("b1", albumArtist = "Massive Attack", album = "Mezzanine"),
        ),
    )

    @Test
    fun seedsCountSongsAndLikedSongsPerArtist() {
        val seeds = DiscoverInput.seeds(library, likedTrackIds = setOf("a1", "a3", "zzz"))
        assertEquals(
            setOf(DiscoverSeed("Portishead", 3, 2), DiscoverSeed("Massive Attack", 1, 0)),
            seeds.toSet(),
        )
    }

    @Test
    fun anArtistWithoutANameIsLeftOut() {
        val unnamed = LibraryGrouping.artists(listOf(track("x", albumArtist = "", artistId = "")))
        assertEquals(emptyList<DiscoverSeed>(), DiscoverInput.seeds(unnamed, emptySet()))
    }

    @Test
    fun linksFromTheCollectionsAnswerAreMatchedByExactName() {
        val artists = listOf(
            DiscoverArtist("Hooverphonic", "", listOf("Portishead"), ""),
            DiscoverArtist("Archive", "", emptyList(), ""),
        )
        val linked = DiscoverInput.withLinks(artists, mapOf("Hooverphonic" to "https://open.spotify.com/artist/1"))
        assertEquals("https://open.spotify.com/artist/1", DiscoverInput.searchFor(linked[0]))
        assertEquals("Archive", DiscoverInput.searchFor(linked[1]))
    }

    @Test
    fun albumKeysAreArtistAndTitle() {
        val albums = LibraryGrouping.albums(listOf(track("a1", albumArtist = "Portishead", album = "Dummy")))
        assertEquals(listOf("Portishead" to "Dummy"), DiscoverInput.albumKeys(albums))
    }
}
