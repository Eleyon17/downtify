package com.henriquesebastiao.downtify.core.data.sync

import kotlinx.coroutines.channels.Channel

/** Coalesces pending syncs without losing a request to rescan the server. */
internal class SyncRequests {
    private val lock = Any()
    private val signals = Channel<Unit>(Channel.CONFLATED)
    private var refreshPending = false

    fun request(refresh: Boolean = false) {
        synchronized(lock) {
            refreshPending = refreshPending || refresh
            signals.trySend(Unit)
        }
    }

    suspend fun collect(sync: suspend (Boolean) -> Unit) {
        while (true) {
            signals.receive()
            val refresh = synchronized(lock) {
                // A request between receive and this lock belongs to this sync too.
                signals.tryReceive()
                refreshPending.also { refreshPending = false }
            }
            sync(refresh)
        }
    }
}
