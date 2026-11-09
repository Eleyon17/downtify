package com.henriquesebastiao.downtify.core.data.library

import com.henriquesebastiao.downtify.core.data.db.DowntifyDatabase
import com.henriquesebastiao.downtify.core.data.db.TrackEntity
import io.mockk.every
import io.mockk.mockk
import io.mockk.spyk
import io.mockk.verify
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test

class LibrarySnapshotsTest {
    @Test
    fun `identical rows are not converted again but real changes are published`() = runTest {
        val row = spyk(
            TrackEntity(
                id = "track", file = "track.mp3", title = "Original", artist = "Artist",
                artists = listOf("Artist"), album = "Album", albumArtist = "Artist", albumId = "album",
                artistId = "artist", trackNumber = 1, year = "2026", duration = 120.0, codec = "mp3",
                bitrate = 320000, sampleRate = 44100, channels = 2, size = 1000, added = 1,
                hasCover = true, playlists = emptyList(),
            ),
        )
        val changed = row.copy(title = "Changed")
        val db = mockk<DowntifyDatabase>()
        every { db.tracks().observeAll() } returns flowOf(listOf(row), listOf(row), listOf(changed))
        every { db.playlists().observeAll() } returns flowOf(emptyList())
        every { db.likes().observeIds() } returns flowOf(emptyList())
        val repository = LibraryRepository(db, mockk(), mockk(), mockk(), backgroundScope)

        val latest = repository.library.filterNotNull().first { it.tracks.single().title == "Changed" }

        assertEquals("Changed", latest.tracks.single().title)
        verify(exactly = 1) { row.toModel() }
    }
}
