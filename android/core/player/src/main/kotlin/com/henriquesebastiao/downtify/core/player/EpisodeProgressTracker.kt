package com.henriquesebastiao.downtify.core.player

import androidx.annotation.OptIn
import androidx.media3.common.C
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import com.henriquesebastiao.downtify.core.data.podcasts.PodcastsRepository
import com.henriquesebastiao.downtify.core.model.EpisodeIds
import com.henriquesebastiao.downtify.core.model.EpisodeProgress
import com.henriquesebastiao.downtify.core.model.PodcastProgress
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Saves where the user is in a podcast episode, on the server: every 10 seconds
 * of playback and again at every pause, change of episode or end — the web
 * player's rule, so another device picks up close to where this one stopped.
 * The saves are idempotent: a missed one only replays a few seconds.
 */
@OptIn(UnstableApi::class)
internal class EpisodeProgressTracker(
    private val player: Player,
    private val podcasts: PodcastsRepository,
    private val scope: CoroutineScope,
) : Player.Listener {
    private var ticker: Job? = null

    /** The episode last saved for, so a change of item saves the one being left. */
    private var episodeId: Long? = null
    private var durationSeconds = 0
    private var positionSeconds = 0.0

    fun start() {
        player.addListener(this)
        follow()
    }

    fun stop() {
        player.removeListener(this)
        ticker?.cancel()
        save(ended = false)
    }

    override fun onEvents(player: Player, events: Player.Events) {
        if (events.containsAny(
                Player.EVENT_MEDIA_ITEM_TRANSITION,
                Player.EVENT_PLAY_WHEN_READY_CHANGED,
                Player.EVENT_PLAYBACK_STATE_CHANGED,
            )
        ) {
            follow()
        }
    }

    override fun onPositionDiscontinuity(
        oldPosition: Player.PositionInfo,
        newPosition: Player.PositionInfo,
        reason: Int,
    ) {
        // A change of item: the old position is the one to save, for the old episode.
        if (reason == Player.DISCONTINUITY_REASON_AUTO_TRANSITION || reason == Player.DISCONTINUITY_REASON_REMOVE) {
            EpisodeIds.episodeIdOf(oldPosition.mediaItem?.mediaId)?.let { id ->
                val duration = oldPosition.mediaItem?.mediaMetadata?.durationMs?.let { it / MS }?.toInt() ?: 0
                send(id, PodcastProgress.toSave(oldPosition.positionMs / MS_D, duration))
            }
        }
    }

    /** Called on every change that matters: what's playing, and whether. */
    private fun follow() {
        val current = EpisodeIds.episodeIdOf(player.currentMediaItem?.mediaId)
        if (current != episodeId) {
            ticker?.cancel()
            episodeId = current
        }
        if (current == null) return
        val state = player.playbackState
        // Starting or seeking: the position isn't settled yet, and saving it could overwrite the resume point.
        if (player.playWhenReady && (state == Player.STATE_BUFFERING || state == Player.STATE_IDLE)) return
        remember()
        val playing = player.playWhenReady && state == Player.STATE_READY
        val ended = state == Player.STATE_ENDED
        if (playing) {
            if (ticker?.isActive != true) {
                ticker = scope.launch {
                    while (isActive) {
                        delay(PodcastProgress.SAVE_EVERY_SECONDS * MS)
                        remember()
                        save(ended = false)
                    }
                }
            }
        } else {
            ticker?.cancel()
            save(ended)
        }
    }

    private fun remember() {
        positionSeconds = player.currentPosition.coerceAtLeast(0) / MS_D
        durationSeconds = player.duration.takeIf { it != C.TIME_UNSET }?.let { (it / MS).toInt() }
            ?: player.currentMediaItem?.mediaMetadata?.durationMs?.let { (it / MS).toInt() }
            ?: 0
    }

    private fun save(ended: Boolean) {
        val id = episodeId ?: return
        remember()
        send(
            id,
            if (ended) {
                EpisodeProgress(
                    durationSeconds.toDouble(),
                    played = true,
                )
            } else {
                PodcastProgress.toSave(positionSeconds, durationSeconds)
            },
        )
    }

    private fun send(id: Long, progress: EpisodeProgress) {
        scope.launch { podcasts.saveProgress(id, progress) }
    }

    private companion object {
        const val MS = 1000L
        const val MS_D = 1000.0
    }
}
