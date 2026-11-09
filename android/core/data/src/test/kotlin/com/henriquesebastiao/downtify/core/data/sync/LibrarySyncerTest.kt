package com.henriquesebastiao.downtify.core.data.sync

import com.henriquesebastiao.downtify.core.model.LibraryPage
import com.henriquesebastiao.downtify.core.model.Track
import java.io.IOException
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LibrarySyncerTest {

    private class FakeStore : LibraryLocalStore {
        val tracks = linkedMapOf<String, Track>()
        var state: SyncState? = null

        override suspend fun syncState() = state

        override suspend fun replaceAll(serverId: String, tracks: List<Track>, cursor: Long) {
            this.tracks.clear()
            tracks.forEach { this.tracks[it.id] = it }
            state = SyncState(serverId, cursor)
        }

        override suspend fun applyChanges(serverId: String, tracks: List<Track>, deleted: List<String>, cursor: Long) {
            tracks.forEach { this.tracks[it.id] = it }
            deleted.forEach { this.tracks.remove(it) }
            state = SyncState(serverId, cursor)
        }
    }

    private class FakeRemote(vararg pages: LibraryPage?) : LibraryRemote {
        val queue = ArrayDeque(pages.toList())
        val calls = mutableListOf<Pair<Long, Boolean>>()
        var fail = false

        override suspend fun changes(since: Long, refresh: Boolean): LibraryPage? {
            calls += since to refresh
            if (fail) throw IOException("offline")
            return queue.removeFirst()
        }
    }

    @Test
    fun `first sync asks for everything and replaces`() = runTest {
        val store = FakeStore().apply { tracks["stale"] = track("stale") }
        val remote =
            FakeRemote(LibraryPage(10, full = true, tracks = listOf(track("a"), track("b")), deleted = emptyList()))

        val outcome = LibrarySyncer(store, remote).sync("srv")

        assertEquals(listOf(0L to false), remote.calls)
        assertEquals(SyncOutcome.Replaced(2), outcome)
        assertEquals(setOf("a", "b"), store.tracks.keys)
        assertEquals(SyncState("srv", 10), store.state)
    }

    @Test
    fun `incremental sync upserts changes and removes deletions`() = runTest {
        val store = FakeStore().apply {
            tracks["a"] = track("a", title = "Old")
            tracks["b"] = track("b")
            state = SyncState("srv", 10)
        }
        val remote = FakeRemote(
            LibraryPage(
                14,
                full = false,
                tracks = listOf(track("a", title = "New"), track("c")),
                deleted = listOf("b", "unknown"),
            ),
        )

        val outcome = LibrarySyncer(store, remote).sync("srv", refresh = true)

        assertEquals(listOf(10L to true), remote.calls)
        assertEquals(SyncOutcome.Applied(changed = 2, deleted = 2), outcome)
        assertEquals(setOf("a", "c"), store.tracks.keys)
        assertEquals("New", store.tracks.getValue("a").title)
        assertEquals(14L, store.state?.cursor)
    }

    @Test
    fun `full answer to an incremental request replaces everything`() = runTest {
        val store = FakeStore().apply {
            tracks["a"] = track("a")
            tracks["gone"] = track("gone")
            state = SyncState("srv", 3)
        }
        val remote =
            FakeRemote(LibraryPage(50, full = true, tracks = listOf(track("a"), track("z")), deleted = emptyList()))

        LibrarySyncer(store, remote).sync("srv")

        assertEquals(setOf("a", "z"), store.tracks.keys)
        assertEquals(50L, store.state?.cursor)
    }

    @Test
    fun `a different server starts from zero`() = runTest {
        val store = FakeStore().apply { state = SyncState("old-server", 99) }
        val remote = FakeRemote(LibraryPage(1, full = true, tracks = emptyList(), deleted = emptyList()))

        LibrarySyncer(store, remote).sync("new-server")

        assertEquals(0L, remote.calls.single().first)
        assertEquals(SyncState("new-server", 1), store.state)
    }

    @Test
    fun `not modified and failures leave the cursor alone`() = runTest {
        val store = FakeStore().apply { state = SyncState("srv", 7) }

        assertEquals(SyncOutcome.Unchanged, LibrarySyncer(store, FakeRemote(null)).sync("srv"))
        assertEquals(7L, store.state?.cursor)

        val failing = FakeRemote().apply { fail = true }
        val error = runCatching { LibrarySyncer(store, failing).sync("srv") }.exceptionOrNull()
        assertTrue(error is IOException)
        assertEquals(7L, store.state?.cursor)
    }

    private fun track(id: String, title: String = id) = Track(
        id = id, file = "$id.flac", title = title, artist = "A", artists = listOf("A"), album = "B", albumArtist = "A",
        albumId = "b", artistId = "a", trackNumber = 1, year = "", duration = 100.0, codec = "flac", bitrate = 0,
        sampleRate = 0, channels = 2, size = 1, added = 0, hasCover = false, playlists = emptyList(),
    )
}
