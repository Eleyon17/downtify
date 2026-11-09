package com.henriquesebastiao.downtify.core.model

/**
 * When a play counts as a listen — the web player's rule: once half the track
 * (or four minutes, whichever is less) has actually played. Seeking forward
 * doesn't add played time; going back to the start after it counted is a new
 * play. Tracks under 30 seconds never count.
 */
class ListenCounter {
    private var played = 0.0
    private var last = 0.0
    private var counted = false

    /** Starts over for a new track (or a new play of the same one) at [positionSeconds]. */
    fun reset(positionSeconds: Double = 0.0) {
        played = 0.0
        last = positionSeconds
        counted = false
    }

    /**
     * The playhead moved to [positionSeconds] of a [durationSeconds] track.
     * Returns [Progress.NewPlay] when this is a fresh play after one already
     * counted, [Progress.Counted] exactly once when the play reaches the threshold,
     * and [Progress.None] otherwise.
     */
    fun onPosition(positionSeconds: Double, durationSeconds: Double): Progress {
        var result = Progress.None
        played = addPlayed(played, last, positionSeconds)
        if (counted && positionSeconds < 1 && last > positionSeconds) {
            played = 0.0
            counted = false
            result = Progress.NewPlay
        }
        last = positionSeconds
        if (!counted && played >= threshold(durationSeconds)) {
            counted = true
            return Progress.Counted
        }
        return result
    }

    enum class Progress { None, Counted, NewPlay }

    companion object {
        const val MIN_DURATION_SECONDS = 30.0
        const val MAX_SECONDS = 240.0

        /** Largest step between two position updates still counted as playing (not a seek). */
        const val MAX_TICK_SECONDS = 3.0

        fun threshold(durationSeconds: Double): Double = if (durationSeconds >=
            MIN_DURATION_SECONDS
        ) {
            minOf(durationSeconds / 2, MAX_SECONDS)
        } else {
            Double.POSITIVE_INFINITY
        }

        fun addPlayed(played: Double, last: Double, now: Double): Double {
            val step = now - last
            return if (step > 0 && step <= MAX_TICK_SECONDS) played + step else played
        }
    }
}
