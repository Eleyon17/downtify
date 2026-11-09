package com.henriquesebastiao.downtify.core.data.sync

import com.henriquesebastiao.downtify.core.model.LibraryPage
import com.henriquesebastiao.downtify.core.model.Track
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** Where the synced library lives on the phone. Every write is one transaction. */
interface LibraryLocalStore {
    /** The server the library came from and the cursor to continue from, or null before the first sync. */
    suspend fun syncState(): SyncState?

    /** Replaces the whole library with [tracks] (`full: true`). */
    suspend fun replaceAll(serverId: String, tracks: List<Track>, cursor: Long)

    /** Adds or updates [tracks], removes [deleted] ids, and moves the cursor — atomically. */
    suspend fun applyChanges(serverId: String, tracks: List<Track>, deleted: List<String>, cursor: Long)
}

data class SyncState(val serverId: String, val cursor: Long)

/** The server side of the feed: `GET /api/v1/library?since=&refresh=`. Null means `304 Not Modified`. */
fun interface LibraryRemote {
    suspend fun changes(since: Long, refresh: Boolean): LibraryPage?
}

sealed interface SyncOutcome {
    data object Unchanged : SyncOutcome
    data class Replaced(val trackCount: Int) : SyncOutcome
    data class Applied(val changed: Int, val deleted: Int) : SyncOutcome
}

/**
 * Applies the server's change feed to the local library.
 *
 * - First sync, or a different server than the library came from: `since=0`.
 * - `full: true` (at any time): replace everything local.
 * - Otherwise: upsert the tracks, remove the deleted ids.
 * - The cursor is saved in the same transaction as the changes, never before.
 */
class LibrarySyncer(private val store: LibraryLocalStore, private val remote: LibraryRemote) {
    private val mutex = Mutex()

    suspend fun sync(serverId: String, refresh: Boolean = false): SyncOutcome = mutex.withLock {
        val state = store.syncState()
        val since = if (state != null && state.serverId == serverId) state.cursor else 0L
        val page = remote.changes(since, refresh) ?: return SyncOutcome.Unchanged
        if (page.full || since == 0L) {
            store.replaceAll(serverId, page.tracks, page.cursor)
            SyncOutcome.Replaced(page.tracks.size)
        } else {
            if (page.tracks.isEmpty() && page.deleted.isEmpty() && page.cursor == since) {
                return SyncOutcome.Unchanged
            }
            store.applyChanges(serverId, page.tracks, page.deleted, page.cursor)
            SyncOutcome.Applied(page.tracks.size, page.deleted.size)
        }
    }
}
