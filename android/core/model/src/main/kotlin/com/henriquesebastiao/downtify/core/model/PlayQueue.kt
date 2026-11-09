package com.henriquesebastiao.downtify.core.model

/**
 * "Add to queue", the way Spotify does it: a queued song plays right after the
 * current one and after anything queued before it, ahead of the rest of the
 * album or playlist. Pure index arithmetic, so the player can apply it to
 * whatever order it plays in (shuffled or not).
 */
object PlayQueue {
    /**
     * The item a newly queued song goes right after. [playOrder] is the items
     * from the current one on, in the order they will play; [isQueued] tells
     * which of them were queued by the user. That is the current item, or the
     * last of the queued items that follow it without a gap.
     */
    fun anchor(playOrder: List<Int>, isQueued: (Int) -> Boolean): Int? {
        if (playOrder.isEmpty()) return null
        var last = 0
        while (last + 1 < playOrder.size && isQueued(playOrder[last + 1])) last++
        return playOrder[last]
    }

    /**
     * A whole shuffle order after a song was appended at [newIndex] (the
     * end of the list): [order] is the old order (every old index once), and
     * the new song goes right after [anchor] instead of a random spot.
     */
    fun shuffleOrderWith(order: List<Int>, anchor: Int, newIndex: Int): List<Int> {
        val at = order.indexOf(anchor)
        return if (at < 0) order + newIndex else order.subList(0, at + 1) + newIndex + order.subList(at + 1, order.size)
    }

    /** A shuffle order with [item] taken out and put right after [anchor]. */
    fun moveAfter(order: List<Int>, item: Int, anchor: Int): List<Int> {
        if (item == anchor) return order
        val without = order.filter { it != item }
        val at = without.indexOf(anchor)
        return if (at < 0) order else without.subList(0, at + 1) + item + without.subList(at + 1, without.size)
    }

    /**
     * The index to hand `moveMediaItem` so the item at [from] ends up right after the
     * item now at [anchor], in a list that plays in index order.
     */
    fun moveTarget(from: Int, anchor: Int): Int = if (from < anchor) anchor else anchor + 1

    /**
     * Whether a song dragged between two others belongs to "Next in queue". Queued songs
     * stay together at the front: after an unqueued song it can't be queued, between
     * queued songs (or at the top before one) it is, and at the edge it keeps what it was.
     * [previousQueued] and [nextQueued] are null when there's no song on that side.
     */
    fun queuedAfterMove(previousQueued: Boolean?, nextQueued: Boolean?, wasQueued: Boolean): Boolean = when {
        previousQueued == false -> false
        nextQueued == true -> true
        else -> wasQueued
    }
}
