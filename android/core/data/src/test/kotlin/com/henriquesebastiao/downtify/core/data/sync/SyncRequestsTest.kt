package com.henriquesebastiao.downtify.core.data.sync

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test

class SyncRequestsTest {
    @Test
    fun `ordinary requests cannot replace a pending rescan`() = runTest {
        val requests = SyncRequests()
        requests.request(true)
        repeat(100) { requests.request() }
        val calls = mutableListOf<Boolean>()
        backgroundScope.launch { requests.collect { calls += it } }
        runCurrent()
        assertEquals(listOf(true), calls)
    }

    @Test
    fun `requests during a sync run once afterwards and retain the rescan`() = runTest {
        val requests = SyncRequests()
        val finishFirst = CompletableDeferred<Unit>()
        val calls = mutableListOf<Boolean>()
        backgroundScope.launch {
            requests.collect {
                calls += it
                if (calls.size == 1) finishFirst.await()
            }
        }
        requests.request()
        runCurrent()
        requests.request(true)
        repeat(100) { requests.request() }
        runCurrent()
        assertEquals(listOf(false), calls)
        finishFirst.complete(Unit)
        runCurrent()
        assertEquals(listOf(false, true), calls)
        requests.request()
        runCurrent()
        assertEquals(listOf(false, true, false), calls)
    }

    @Test
    fun `cancelling a session cancels its active sync`() = runTest {
        val requests = SyncRequests()
        val started = CompletableDeferred<Unit>()
        val cancelled = CompletableDeferred<Unit>()
        val session = backgroundScope.launch {
            requests.collect {
                started.complete(Unit)
                try {
                    CompletableDeferred<Unit>().await()
                } finally {
                    cancelled.complete(Unit)
                }
            }
        }
        requests.request()
        runCurrent()
        check(started.isCompleted)
        session.cancel()
        runCurrent()
        check(cancelled.isCompleted)
        val calls = mutableListOf<Boolean>()
        backgroundScope.launch { requests.collect { calls += it } }
        requests.request(true)
        runCurrent()
        assertEquals(listOf(true), calls)
    }
}
