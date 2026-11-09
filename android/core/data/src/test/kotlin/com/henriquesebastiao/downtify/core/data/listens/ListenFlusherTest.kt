package com.henriquesebastiao.downtify.core.data.listens

import java.io.IOException
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test

class ListenFlusherTest {

    private class FakeStore(vararg ids: String) : PendingListenStore {
        val pending = ids.map { PendingListen(it, "track-$it", "2026-09-27T10:00:00Z") }.toMutableList()

        override suspend fun oldest(limit: Int) = pending.take(limit)
        override suspend fun remove(playId: String) {
            pending.removeAll { it.playId == playId }
        }
    }

    private fun sender(vararg answers: Any): Pair<ListenSender, MutableList<String>> {
        val sent = mutableListOf<String>()
        val queue = ArrayDeque(answers.toList())
        return ListenSender { listen ->
            sent += listen.playId
            when (val next = queue.removeFirst()) {
                is Int -> next
                else -> throw IOException("offline")
            }
        } to sent
    }

    @Test
    fun `sends everything oldest first and empties the queue`() = runTest {
        val store = FakeStore("1", "2", "3")
        val (sender, sent) = sender(200, 200, 200)

        assertEquals(ListenFlusher.Result.Done, ListenFlusher(store, sender).flush())
        assertEquals(listOf("1", "2", "3"), sent)
        assertEquals(emptyList<PendingListen>(), store.pending)
    }

    @Test
    fun `offline keeps the report and asks for a retry`() = runTest {
        val store = FakeStore("1", "2")
        val (sender, _) = sender(200, "offline")

        assertEquals(ListenFlusher.Result.Retry, ListenFlusher(store, sender).flush())
        assertEquals(listOf("2"), store.pending.map { it.playId })
    }

    @Test
    fun `server errors and rate limits retry, rejected reports are dropped`() = runTest {
        val store = FakeStore("bad", "busy", "later")
        val (sender, _) = sender(400, 503)

        assertEquals(ListenFlusher.Result.Retry, ListenFlusher(store, sender).flush())
        assertEquals(listOf("busy", "later"), store.pending.map { it.playId })

        val (limited, _) = sender(429)
        assertEquals(ListenFlusher.Result.Retry, ListenFlusher(store, limited).flush())
        assertEquals(2, store.pending.size)
    }

    @Test
    fun `unpaired stops and keeps the queue`() = runTest {
        val store = FakeStore("1", "2")
        val (sender, sent) = sender(401)

        assertEquals(ListenFlusher.Result.Stopped, ListenFlusher(store, sender).flush())
        assertEquals(listOf("1"), sent)
        assertEquals(2, store.pending.size)
    }
}
