package com.henriquesebastiao.downtify.core.model

import com.henriquesebastiao.downtify.core.model.ListenCounter.Progress
import org.junit.Assert.assertEquals
import org.junit.Test

class ListenCounterTest {

    private fun ListenCounter.playTo(from: Int, to: Int, duration: Double): List<Progress> =
        (from + 1..to).map { onPosition(it.toDouble(), duration) }

    @Test
    fun `counts once after half the track`() {
        val counter = ListenCounter()
        val events = counter.playTo(0, 200, duration = 200.0)
        assertEquals(1, events.count { it == Progress.Counted })
        assertEquals(Progress.Counted, events[99])
    }

    @Test
    fun `caps the threshold at four minutes`() {
        assertEquals(240.0, ListenCounter.threshold(3_600.0), 0.0)
        assertEquals(Double.POSITIVE_INFINITY, ListenCounter.threshold(29.0), 0.0)
    }

    @Test
    fun `seeking forward does not count as playing`() {
        val counter = ListenCounter()
        counter.playTo(0, 10, 200.0)
        assertEquals(Progress.None, counter.onPosition(150.0, 200.0))
        val events = counter.playTo(150, 199, 200.0)
        assertEquals(0, events.count { it == Progress.Counted })
    }

    @Test
    fun `going back to the start after counting is a new play`() {
        val counter = ListenCounter()
        counter.playTo(0, 120, 200.0)
        assertEquals(Progress.NewPlay, counter.onPosition(0.2, 200.0))
        val events = counter.playTo(0, 101, 200.0)
        assertEquals(1, events.count { it == Progress.Counted })
    }
}
