package com.henriquesebastiao.downtify.core.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PlayQueueTest {
    @Test
    fun nothingQueuedGoesRightAfterTheCurrentItem() {
        assertEquals(3, PlayQueue.anchor(listOf(3, 4, 5)) { false })
    }

    @Test
    fun queuedSongsKeepTheirOrder() {
        val queued = setOf(4, 5)
        assertEquals(5, PlayQueue.anchor(listOf(3, 4, 5, 6)) { it in queued })
    }

    @Test
    fun onlyQueuedSongsRightAfterTheCurrentOneCount() {
        // 6 was queued, but the album's 4 plays before it: the new song goes after the current one.
        val queued = setOf(6)
        assertEquals(3, PlayQueue.anchor(listOf(3, 4, 5, 6)) { it in queued })
    }

    @Test
    fun theLastItemIsItsOwnAnchor() {
        assertEquals(7, PlayQueue.anchor(listOf(7)) { false })
    }

    @Test
    fun anEmptyQueueHasNoAnchor() {
        assertNull(PlayQueue.anchor(emptyList()) { false })
    }

    @Test
    fun aShuffledSongGoesRightAfterTheAnchor() {
        assertEquals(listOf(2, 0, 4, 3, 1), PlayQueue.shuffleOrderWith(listOf(2, 0, 3, 1), anchor = 0, newIndex = 4))
    }

    @Test
    fun anUnknownAnchorAppends() {
        assertEquals(listOf(1, 0, 2), PlayQueue.shuffleOrderWith(listOf(1, 0), anchor = 9, newIndex = 2))
    }

    @Test
    fun movingInAShuffleOrderPutsTheSongAfterItsAnchor() {
        assertEquals(listOf(2, 3, 0, 1), PlayQueue.moveAfter(listOf(2, 0, 3, 1), item = 0, anchor = 3))
        assertEquals(listOf(2, 1, 0, 3), PlayQueue.moveAfter(listOf(2, 0, 3, 1), item = 1, anchor = 2))
    }

    @Test
    fun movingASongAfterItselfChangesNothing() {
        assertEquals(listOf(0, 1, 2), PlayQueue.moveAfter(listOf(0, 1, 2), item = 1, anchor = 1))
    }

    @Test
    fun moveTargetsInIndexOrder() {
        // [0 1 2 3 4]: 1 after 3 -> [0 2 3 1 4] (index 3); 4 after 1 -> [0 1 4 2 3] (index 2).
        assertEquals(3, PlayQueue.moveTarget(from = 1, anchor = 3))
        assertEquals(2, PlayQueue.moveTarget(from = 4, anchor = 1))
    }

    @Test
    fun aDraggedSongJoinsTheQueueOnlyAmongQueuedSongs() {
        assertEquals(true, PlayQueue.queuedAfterMove(previousQueued = true, nextQueued = true, wasQueued = false))
        assertEquals(true, PlayQueue.queuedAfterMove(previousQueued = null, nextQueued = true, wasQueued = false))
        assertEquals(false, PlayQueue.queuedAfterMove(previousQueued = false, nextQueued = true, wasQueued = true))
        assertEquals(false, PlayQueue.queuedAfterMove(previousQueued = false, nextQueued = null, wasQueued = true))
        // At the edge of the queue it keeps what it was.
        assertEquals(true, PlayQueue.queuedAfterMove(previousQueued = true, nextQueued = false, wasQueued = true))
        assertEquals(false, PlayQueue.queuedAfterMove(previousQueued = true, nextQueued = false, wasQueued = false))
        assertEquals(true, PlayQueue.queuedAfterMove(previousQueued = null, nextQueued = false, wasQueued = true))
    }
}
