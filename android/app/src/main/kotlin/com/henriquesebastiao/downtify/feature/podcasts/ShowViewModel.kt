package com.henriquesebastiao.downtify.feature.podcasts

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.henriquesebastiao.downtify.core.data.ServerResult
import com.henriquesebastiao.downtify.core.data.podcasts.PodcastsRepository
import com.henriquesebastiao.downtify.core.model.PodcastEpisode
import com.henriquesebastiao.downtify.core.model.PodcastShow
import com.henriquesebastiao.downtify.core.player.PlayerController
import com.henriquesebastiao.downtify.ui.common.LoadError
import com.henriquesebastiao.downtify.ui.common.loadError
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ShowUiState(
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val show: PodcastShow? = null,
    val episodes: List<PodcastEpisode> = emptyList(),
    val error: LoadError? = null,
    /** Episodes the server is downloading for this phone right now. */
    val busy: Set<Long> = emptySet(),
    val currentEpisodeId: Long? = null,
    val isPlaying: Boolean = false,
)

sealed interface ShowMessage {
    data class DownloadFailed(val title: String) : ShowMessage
    data object Unreachable : ShowMessage
}

/** A show's episodes: what's played, where to resume, and playing or downloading one. */
@HiltViewModel
class ShowViewModel @Inject constructor(
    savedState: SavedStateHandle,
    private val podcasts: PodcastsRepository,
    private val player: PlayerController,
) : ViewModel() {
    private val showId: Long = savedState["showId"] ?: 0L

    private class Fetched(
        val loading: Boolean = true,
        val refreshing: Boolean = false,
        val show: PodcastShow? = null,
        val episodes: List<PodcastEpisode> = emptyList(),
        val error: LoadError? = null,
    )

    private val fetched = MutableStateFlow(Fetched())
    private val busy = MutableStateFlow<Set<Long>>(emptySet())
    private val messageChannel = Channel<ShowMessage>(Channel.BUFFERED)

    val messages: Flow<ShowMessage> = messageChannel.receiveAsFlow()

    val uiState: StateFlow<ShowUiState> = combine(
        fetched,
        podcasts.updated,
        busy,
        player.nowPlaying,
    ) { fetched, updated, busy, playing ->
        ShowUiState(
            loading = fetched.loading,
            refreshing = fetched.refreshing,
            show = fetched.show,
            // What this phone changed since the list was fetched wins: progress, played, downloaded.
            episodes = fetched.episodes.map { updated[it.id]?.takeIf { u -> u.showId == showId } ?: it },
            error = fetched.error,
            busy = busy,
            currentEpisodeId = playing.episodeId,
            isPlaying = playing.isPlaying,
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(STOP_TIMEOUT_MS), ShowUiState())

    init {
        load(initial = true)
    }

    fun refresh() = load(initial = false)

    /** Plays [episode]: from the server's file, downloading it first when it hasn't got it yet. */
    fun play(episode: PodcastEpisode) {
        val state = uiState.value
        val show = state.show ?: return
        if (state.currentEpisodeId == episode.id) {
            player.togglePlayPause()
            return
        }
        viewModelScope.launch {
            val ready = if (episode.isDownloaded) episode else fetchFile(episode) ?: return@launch
            player.playEpisode(ready, show)
        }
    }

    /** Has the server download [episode] without playing it. */
    fun download(episode: PodcastEpisode) {
        viewModelScope.launch { fetchFile(episode) }
    }

    fun setPlayed(episode: PodcastEpisode, played: Boolean) {
        viewModelScope.launch {
            if (podcasts.setPlayed(episode.id, played) is ServerResult.Unreachable) {
                messageChannel.send(ShowMessage.Unreachable)
            }
        }
    }

    private suspend fun fetchFile(episode: PodcastEpisode): PodcastEpisode? {
        busy.update { it + episode.id }
        val result = podcasts.download(episode.id)
        busy.update { it - episode.id }
        return when (result) {
            is ServerResult.Ok -> result.value

            ServerResult.Unreachable -> {
                messageChannel.send(ShowMessage.Unreachable)
                null
            }

            is ServerResult.Failed -> {
                messageChannel.send(ShowMessage.DownloadFailed(episode.title))
                null
            }
        }
    }

    private fun load(initial: Boolean) {
        fetched.update { if (initial) Fetched() else Fetched(false, true, it.show, it.episodes, it.error) }
        viewModelScope.launch {
            val result = podcasts.episodes(showId)
            fetched.update {
                val ok = (result as? ServerResult.Ok)?.value
                Fetched(
                    loading = false,
                    show = ok?.show ?: it.show,
                    episodes = ok?.episodes ?: it.episodes,
                    error = result.loadError(),
                )
            }
        }
    }

    private companion object {
        const val STOP_TIMEOUT_MS = 5_000L
    }
}
