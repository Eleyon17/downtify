package com.henriquesebastiao.downtify.core.data.podcasts

import com.henriquesebastiao.downtify.core.data.ServerResult
import com.henriquesebastiao.downtify.core.data.callServer
import com.henriquesebastiao.downtify.core.model.EpisodeProgress
import com.henriquesebastiao.downtify.core.model.PodcastEpisode
import com.henriquesebastiao.downtify.core.model.PodcastShow
import com.henriquesebastiao.downtify.core.network.ApiFactory
import com.henriquesebastiao.downtify.core.network.dto.PodcastPlaybackRequest
import com.henriquesebastiao.downtify.core.network.session.SessionStore
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/** A show with its episodes, newest first. */
data class ShowEpisodes(val show: PodcastShow, val episodes: List<PodcastEpisode>)

/**
 * The server's podcasts: the shows it's subscribed to, their episodes, and this
 * user's place in each. A device can read all of that, download an episode on
 * demand and save progress; subscribing and removing are the web page's (admin).
 */
@Singleton
class PodcastsRepository @Inject constructor(private val sessions: SessionStore, private val apis: ApiFactory) {
    private val latest = MutableStateFlow<Map<Long, PodcastEpisode>>(emptyMap())

    /**
     * The newest state of each episode this phone changed (progress, played, downloaded):
     * lists show it at once, before they fetch again.
     */
    val updated: StateFlow<Map<Long, PodcastEpisode>> = latest.asStateFlow()

    suspend fun shows(): ServerResult<List<PodcastShow>> =
        callServer(sessions, apis) { api -> api.podcastShows().map { it.toModel() } }

    suspend fun episodes(showId: Long): ServerResult<ShowEpisodes> = callServer(sessions, apis) { api ->
        val answer = api.podcastEpisodes(showId)
        // What the server sends is newer than what this phone remembered.
        latest.update { it - answer.episodes.map { e -> e.id }.toSet() }
        ShowEpisodes(answer.show.toModel(), answer.episodes.map { it.toModel() })
    }

    /** Has the server download [episodeId] now (it answers when the file is there). */
    suspend fun download(episodeId: Long): ServerResult<PodcastEpisode> =
        callServer(sessions, apis, patient = true) { api -> api.downloadPodcastEpisode(episodeId).toModel() }
            .remember()

    /** Marks an episode played or unplayed by hand; unplayed also forgets the place in it. */
    suspend fun setPlayed(episodeId: Long, played: Boolean): ServerResult<PodcastEpisode> =
        callServer(sessions, apis) { api ->
            api.setPodcastPlayback(
                episodeId,
                PodcastPlaybackRequest(positionSeconds = if (played) null else 0.0, played = played),
            ).toModel()
        }.remember()

    /** Best effort, called every ~10 s of playback and on pause: a missed one only replays a few seconds. */
    suspend fun saveProgress(episodeId: Long, progress: EpisodeProgress): ServerResult<PodcastEpisode> =
        callServer(sessions, apis) { api ->
            api.setPodcastPlayback(
                episodeId,
                PodcastPlaybackRequest(progress.positionSeconds, progress.played.takeIf { it }),
            ).toModel()
        }.remember()

    private fun ServerResult<PodcastEpisode>.remember(): ServerResult<PodcastEpisode> {
        if (this is ServerResult.Ok) latest.update { it + (value.id to value) }
        return this
    }
}
