package com.henriquesebastiao.downtify.core.data.listens

import java.io.IOException
import kotlinx.coroutines.CancellationException

/** A play waiting to be reported. */
data class PendingListen(val playId: String, val trackId: String, val playedAt: String)

/** Where queued plays are kept until the server has them. */
interface PendingListenStore {
    suspend fun oldest(limit: Int): List<PendingListen>
    suspend fun remove(playId: String)
}

/** Sends one report; returns the HTTP status, or throws [IOException] when the server can't be reached. */
fun interface ListenSender {
    suspend fun send(listen: PendingListen): Int
}

/**
 * Sends queued play reports, oldest first. `play_id` makes a retry safe (the
 * same play counts once), so a report is only dropped once the server has
 * answered for it:
 *
 * - 2xx: sent.
 * - 400/404/422 and other 4xx: the server will never take it (an unknown track): dropped.
 * - 401: the phone was unpaired: stop, keep the rest for the next pairing.
 * - 408/429/5xx or no connection: stop and retry later.
 */
class ListenFlusher(private val store: PendingListenStore, private val sender: ListenSender) {
    enum class Result {
        /** Everything queued was sent (or dropped). */
        Done,

        /** Try again later. */
        Retry,

        /** Not paired: nothing to do until the phone pairs again. */
        Stopped,
    }

    suspend fun flush(): Result {
        while (true) {
            val batch = store.oldest(BATCH)
            if (batch.isEmpty()) return Result.Done
            for (listen in batch) {
                val status = try {
                    sender.send(listen)
                } catch (e: CancellationException) {
                    throw e
                } catch (_: IOException) {
                    return Result.Retry
                }
                when {
                    status in 200..299 -> store.remove(listen.playId)
                    status == 401 -> return Result.Stopped
                    status == 408 || status == 429 || status >= 500 -> return Result.Retry
                    else -> store.remove(listen.playId)
                }
            }
        }
    }

    private companion object {
        const val BATCH = 50
    }
}
