package com.henriquesebastiao.downtify.core.data.offline

import com.henriquesebastiao.downtify.core.data.library.LibrarySnapshot
import com.henriquesebastiao.downtify.core.model.OfflineCollection
import com.henriquesebastiao.downtify.core.model.OfflineFile
import com.henriquesebastiao.downtify.core.model.OfflinePlanner
import com.henriquesebastiao.downtify.core.model.PlaybackContextType
import com.henriquesebastiao.downtify.core.model.Playlist
import com.henriquesebastiao.downtify.core.model.Track
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class OfflineStateTest {
    private fun track(id: String, albumId: String) = Track(
        id = id, file = "$id.flac", title = id, artist = "A", artists = listOf("A"), album = albumId,
        albumArtist = "A", albumId = albumId, artistId = "a", trackNumber = 0, year = "", duration = 1.0,
        codec = "flac", bitrate = 0, sampleRate = 0, channels = 2, size = 100, added = 0, hasCover = false,
        playlists = emptyList(),
    )

    private val snapshot = LibrarySnapshot(
        listOf(track("a1", "alb1"), track("a2", "alb1"), track("b1", "alb2"), track("c1", "alb3")),
    )

    private fun state(
        collections: List<OfflineCollection>,
        files: Map<String, OfflineFile> = emptyMap(),
        liked: List<String> = emptyList(),
        playlists: List<Playlist> = emptyList(),
    ) = OfflineRepository.buildState(snapshot, playlists, liked, collections, files, OfflinePlanner.UNLIMITED, true)

    @Test
    fun keptCollectionsResolveToTheirTracksInOrder() {
        val s = state(
            collections = listOf(
                OfflineCollection(PlaybackContextType.Album, "alb2", addedAt = 1),
                OfflineCollection(PlaybackContextType.Playlist, "Mix", addedAt = 2),
                OfflineCollection(PlaybackContextType.Liked, "", addedAt = 3),
            ),
            liked = listOf("c1"),
            playlists = listOf(Playlist("Mix", false, "", listOf("a2", "b1"))),
        )
        assertEquals(listOf("b1", "a2", "c1"), s.plan.toDownload.map { it.id })
        assertEquals(listOf("alb2", "Mix", ""), s.collections.map { it.title })
        assertTrue(s.isKept(PlaybackContextType.Playlist, "Mix"))
    }

    @Test
    fun aDeletedTrackOfAKeptAlbumIsDeletedFromThePhone() {
        val s = state(
            collections = listOf(OfflineCollection(PlaybackContextType.Album, "alb1", 1)),
            files = mapOf("a1" to OfflineFile("a1", "a1.flac", 100), "old" to OfflineFile("old", "old.flac", 100)),
        )
        assertEquals(setOf("old"), s.plan.toDelete)
        assertEquals(listOf("a2"), s.plan.toDownload.map { it.id })
        assertEquals(1, s.collections.single().progress.downloaded)
        assertEquals(2, s.collections.single().progress.total)
    }

    @Test
    fun anAlbumNoLongerInTheLibraryIsEmpty() {
        val s = state(listOf(OfflineCollection(PlaybackContextType.Album, "gone", 1)))
        assertTrue(s.collections.single().tracks.isEmpty())
        assertTrue(s.plan.toDownload.isEmpty())
    }
}
