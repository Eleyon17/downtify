package com.henriquesebastiao.downtify.feature.podcasts

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.henriquesebastiao.downtify.core.data.ServerResult
import com.henriquesebastiao.downtify.core.data.podcasts.PodcastsRepository
import com.henriquesebastiao.downtify.core.model.PodcastShow
import com.henriquesebastiao.downtify.ui.common.LoadError
import com.henriquesebastiao.downtify.ui.common.loadError
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class PodcastsUiState(
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val shows: List<PodcastShow> = emptyList(),
    val error: LoadError? = null,
)

/** The shows the server is subscribed to. Subscribing is done on the web page (it needs an admin). */
@HiltViewModel
class PodcastsViewModel @Inject constructor(private val podcasts: PodcastsRepository) : ViewModel() {
    private val state = MutableStateFlow(PodcastsUiState())
    val uiState: StateFlow<PodcastsUiState> = state.asStateFlow()

    init {
        load(initial = true)
    }

    fun refresh() = load(initial = false)

    private fun load(initial: Boolean) {
        state.update { if (initial) it.copy(loading = true) else it.copy(refreshing = true) }
        viewModelScope.launch {
            val result = podcasts.shows()
            state.update {
                PodcastsUiState(
                    loading = false,
                    // Keep what was on screen when a refresh fails.
                    shows = (result as? ServerResult.Ok)?.value ?: it.shows,
                    error = result.loadError(),
                )
            }
        }
    }
}
