package com.henriquesebastiao.downtify.core.data.activity

import android.util.Log
import com.henriquesebastiao.downtify.core.data.settings.SettingsRepository
import com.henriquesebastiao.downtify.core.network.ApiFactory
import com.henriquesebastiao.downtify.core.network.dto.ActivityTrackDto
import com.henriquesebastiao.downtify.core.network.dto.PlaybackActivityRequest
import com.henriquesebastiao.downtify.core.network.session.SessionStore
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton
import retrofit2.HttpException

/** What the player is doing, as `POST /api/activity/playback` names it. */
enum class PlaybackActivityState(val wireName: String) {
    Playing("playing"),
    Paused("paused"),
    Stopped("stopped"),
}

/** The song [PlaybackActivityReporter] reports; null fields are left out. */
data class ActivityTrack(
    /** A library song's id; null for a podcast episode, which is named by [file]. */
    val trackId: String?,
    val file: String? = null,
    val title: String?,
    val artist: String?,
    val album: String?,
    val durationSeconds: Int?,
)

/**
 * Tells the server what this phone is playing, for the admins' Activity page
 * (server 3.2+). Best effort and online only, as the contract asks: a failed
 * report is dropped, never queued — unlike listens.
 */
@Singleton
class PlaybackActivityReporter @Inject constructor(
    private val sessions: SessionStore,
    private val apis: ApiFactory,
    private val settings: SettingsRepository,
) {
    suspend fun report(
        state: PlaybackActivityState,
        track: ActivityTrack?,
        positionSeconds: Int,
        listenedSeconds: Double = 0.0,
        skipped: Boolean = false,
    ) {
        val session = sessions.current ?: return
        val request = PlaybackActivityRequest(
            player = settings.clientId(),
            state = state.wireName,
            track = if (state == PlaybackActivityState.Stopped || track == null) {
                ActivityTrackDto()
            } else {
                ActivityTrackDto(
                    trackId = track.trackId,
                    file = track.file,
                    title = track.title,
                    artist = track.artist,
                    album = track.album,
                    duration = track.durationSeconds,
                )
            },
            position = positionSeconds.coerceAtLeast(0),
            listened = listenedSeconds.coerceAtLeast(0.0),
            skipped = skipped,
        )
        try {
            val response = apis.create(session.baseUrl).reportPlayback(request)
            // 404: a server before 3.2 has no Activity page. Nothing to do about it.
            if (!response.isSuccessful && response.code() != HTTP_NOT_FOUND) {
                Log.d(TAG, "Activity report refused: ${response.code()}")
            }
        } catch (e: IOException) {
            Log.d(TAG, "Activity report not sent", e)
        } catch (e: HttpException) {
            Log.d(TAG, "Activity report refused", e)
        }
    }

    private companion object {
        const val TAG = "PlaybackActivity"
        const val HTTP_NOT_FOUND = 404
    }
}
