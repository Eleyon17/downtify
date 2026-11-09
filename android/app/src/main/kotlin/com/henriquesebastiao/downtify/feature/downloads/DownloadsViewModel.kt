package com.henriquesebastiao.downtify.feature.downloads

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.henriquesebastiao.downtify.core.data.catalog.ServerQueueRepository
import com.henriquesebastiao.downtify.core.data.offline.DownloadActivity
import com.henriquesebastiao.downtify.core.data.offline.OfflineRepository
import com.henriquesebastiao.downtify.core.model.OfflineProgress
import com.henriquesebastiao.downtify.core.model.PlaybackContextType
import com.henriquesebastiao.downtify.core.model.ServerJob
import com.henriquesebastiao.downtify.core.model.ServerJobStatus
import com.henriquesebastiao.downtify.core.model.ServerQueueSummary
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.flow.onStart
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/** A kept collection as the Downloads list shows it. */
data class DownloadItem(
    val type: PlaybackContextType,
    val refId: String,
    /** Blank for Liked songs: the screen names it. */
    val title: String,
    val coverTrackId: String?,
    val progress: OfflineProgress,
)

enum class DownloadsTab { Phone, Server }

data class DownloadsUiState(
    val loading: Boolean = true,
    val tab: DownloadsTab = DownloadsTab.Phone,
    val usedBytes: Long = 0,
    val limitBytes: Long = 0,
    val freeBytes: Long = 0,
    val songCount: Int = 0,
    val keepLiked: Boolean = false,
    val wifiOnly: Boolean = true,
    val activity: DownloadActivity = DownloadActivity.Idle,
    val items: List<DownloadItem> = emptyList(),
    /** The server's download queue: what's downloading first, then waiting, failed and done. */
    val serverJobs: List<ServerJob> = emptyList(),
    val serverSummary: ServerQueueSummary = ServerQueueSummary(0, "", 0, 0),
)

@HiltViewModel
class DownloadsViewModel @Inject constructor(
    private val savedState: SavedStateHandle,
    private val offline: OfflineRepository,
    private val queue: ServerQueueRepository,
) : ViewModel() {
    private val tab = savedState.getStateFlow(KEY_TAB, DownloadsTab.Phone.name)

    val uiState: StateFlow<DownloadsUiState> = combine(
        offline.state.filterNotNull(),
        offline.activity.onStart { emit(DownloadActivity.Idle) },
        queue.jobs,
        tab,
    ) { state, activity, jobs, tab ->
        DownloadsUiState(
            loading = false,
            tab = DownloadsTab.entries.firstOrNull { it.name == tab } ?: DownloadsTab.Phone,
            serverJobs = jobs.values.sortedBy { STATUS_ORDER.indexOf(it.status) },
            serverSummary = ServerQueueSummary.of(jobs.values.toList()),
            usedBytes = state.usedBytes + offline.partialBytes(),
            limitBytes = state.limitBytes,
            freeBytes = offline.freeBytes(),
            songCount = state.files.size,
            keepLiked = state.isKept(PlaybackContextType.Liked, ""),
            wifiOnly = state.wifiOnly,
            activity = activity,
            // Newest first, like the design; downloads still go oldest first.
            items = state.collections.asReversed().map {
                DownloadItem(it.collection.type, it.collection.refId, it.title, it.coverTrackId, it.progress)
            },
        )
    }
        .flowOn(Dispatchers.IO)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(STOP_TIMEOUT_MS), DownloadsUiState())

    init {
        viewModelScope.launch { queue.refresh() }
    }

    fun selectTab(value: DownloadsTab) {
        savedState[KEY_TAB] = value.name
    }

    fun setKeepLiked(keep: Boolean) {
        viewModelScope.launch { offline.setKept(PlaybackContextType.Liked, "", keep) }
    }

    fun remove(item: DownloadItem) {
        viewModelScope.launch { offline.setKept(item.type, item.refId, keep = false) }
    }

    private companion object {
        const val STOP_TIMEOUT_MS = 5_000L
        const val KEY_TAB = "tab"
        val STATUS_ORDER = listOf(
            ServerJobStatus.Downloading,
            ServerJobStatus.Queued,
            ServerJobStatus.Error,
            ServerJobStatus.Done,
        )
    }
}
