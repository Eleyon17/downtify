package com.henriquesebastiao.downtify.core.player

import androidx.media3.common.C
import androidx.media3.common.Player
import com.henriquesebastiao.downtify.core.data.activity.ActivityTrack
import com.henriquesebastiao.downtify.core.data.activity.PlaybackActivityReporter
import com.henriquesebastiao.downtify.core.data.activity.PlaybackActivityState
import com.henriquesebastiao.downtify.core.model.StreamIds
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Reports what's playing to the server's Activity page: when a song starts,
 * on pause/resume and stop, and every 30 seconds while playing.
 */
internal class ActivityTracker(
    private val player: Player,
    private val reporter: PlaybackActivityReporter,
    private val scope: CoroutineScope,
) : Player.Listener {
    private var last: Pair<String?, PlaybackActivityState>? = null
    private var ticker: Job? = null
    private var trackedMediaId: String? = null
    private var trackedTrack: ActivityTrack? = null
    private var accumulatedMs: Long = 0L
    private var playingSinceMs: Long? = null

    fun start() {
        player.addListener(this)
        send()
    }

    fun stop() {
        player.removeListener(this)
        ticker?.cancel()
    }

    override fun onEvents(player: Player, events: Player.Events) {
        if (events.containsAny(
                Player.EVENT_MEDIA_ITEM_TRANSITION,
                Player.EVENT_PLAY_WHEN_READY_CHANGED,
                Player.EVENT_PLAYBACK_STATE_CHANGED,
            )
        ) {
            send()
        }
    }

    private fun currentState(): PlaybackActivityState = when {
        player.currentMediaItem == null || player.playbackState == Player.STATE_IDLE ||
            player.playbackState == Player.STATE_ENDED -> PlaybackActivityState.Stopped

        player.playWhenReady -> PlaybackActivityState.Playing

        else -> PlaybackActivityState.Paused
    }

    private fun updateAccumulated(nowPlaying: Boolean) {
        val now = System.currentTimeMillis()
        playingSinceMs?.let { start ->
            accumulatedMs += (now - start).coerceIn(0L, MAX_CHUNK_MS)
        }
        playingSinceMs = if (nowPlaying) now else null
    }

    /** Reports a change of song or state; nothing when neither changed. */
    private fun send() {
        val state = currentState()
        val mediaId = player.currentMediaItem?.mediaId
        val key = mediaId to state
        if (key == last) return
        // Nothing was reported yet and nothing plays: no need to say "stopped".
        if (last == null && state == PlaybackActivityState.Stopped) return
        // If transitioning away from a previously tracked library track, flush its listened/skipped summary.
        if (trackedMediaId != null && trackedMediaId != mediaId) {
            updateAccumulated(nowPlaying = false)
            val prevTrack = trackedTrack
            val listenedSec = accumulatedMs / 1000.0
            val skipped = listenedSec in 1.0..15.0 && (prevTrack?.durationSeconds ?: 0) > 30
            if (prevTrack != null && (listenedSec >= 1.0 || skipped)) {
                scope.launch {
                    reporter.report(
                        state = PlaybackActivityState.Paused,
                        track = prevTrack,
                        positionSeconds = listenedSec.toInt(),
                        listenedSeconds = listenedSec,
                        skipped = skipped,
                    )
                }
            }
            trackedMediaId = null
            trackedTrack = null
            accumulatedMs = 0L
        }
        // Streams have no library row to report: keep quiet, like the web player does.
        if (StreamIds.isStream(mediaId)) {
            last = key
            ticker?.cancel()
            return
        }
        last = key
        trackedMediaId = mediaId
        updateAccumulated(nowPlaying = state == PlaybackActivityState.Playing)
        post(state)
        ticker?.cancel()
        if (state == PlaybackActivityState.Playing) {
            ticker = scope.launch {
                while (isActive) {
                    delay(TICK_MS)
                    updateAccumulated(nowPlaying = true)
                    post(PlaybackActivityState.Playing)
                }
            }
        }
    }

    private fun post(state: PlaybackActivityState) {
        val item = player.currentMediaItem
        val meta = player.mediaMetadata
        val episode = item?.let(MediaItems::episodeOf)
        val track = item?.let {
            ActivityTrack(
                trackId = it.mediaId.takeIf { id -> episode == null && id.isNotEmpty() },
                file = episode?.file,
                title = meta.title?.toString(),
                artist = meta.artist?.toString(),
                album = meta.albumTitle?.toString(),
                durationSeconds = player.duration.takeIf { d -> d != C.TIME_UNSET }?.let { d -> (d / MS).toInt() },
            )
        }
        if (track != null) trackedTrack = track
        val position = (player.currentPosition / MS).toInt()
        val listenedSec = accumulatedMs / 1000.0
        scope.launch { reporter.report(state, track, position, listenedSeconds = listenedSec) }
    }

    private companion object {
        const val TICK_MS = 30_000L
        const val MAX_CHUNK_MS = 60_000L
        const val MS = 1000L
    }
}
