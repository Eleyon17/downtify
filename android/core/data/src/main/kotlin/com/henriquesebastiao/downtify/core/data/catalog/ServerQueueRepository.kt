package com.henriquesebastiao.downtify.core.data.catalog

import android.util.Log
import com.henriquesebastiao.downtify.core.model.ServerJob
import com.henriquesebastiao.downtify.core.model.ServerQueueSummary
import com.henriquesebastiao.downtify.core.network.ApiFactory
import com.henriquesebastiao.downtify.core.network.CatalogJson
import com.henriquesebastiao.downtify.core.network.live.LiveEvent
import com.henriquesebastiao.downtify.core.network.session.SessionStore
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import retrofit2.HttpException

/**
 * The server's download queue (`GET /api/queue`), kept fresh by the
 * WebSocket's progress messages while the app is open. Read-only: a device
 * may queue downloads but not clear or cancel them.
 */
@Singleton
class ServerQueueRepository @Inject constructor(private val sessions: SessionStore, private val apis: ApiFactory) {
    private val state = MutableStateFlow<Map<String, ServerJob>>(emptyMap())

    /** By song id, in the server's order. */
    val jobs: StateFlow<Map<String, ServerJob>> = state.asStateFlow()

    fun summary(): ServerQueueSummary = ServerQueueSummary.of(state.value.values.toList())

    suspend fun refresh() {
        val session = sessions.current ?: return
        try {
            val rows = CatalogJson.jobs(apis.createWeb(session.baseUrl).queue())
            state.value = rows.associateBy { it.songId }
        } catch (e: IOException) {
            Log.d(TAG, "Queue not refreshed", e)
        } catch (e: HttpException) {
            Log.d(TAG, "Queue refused: ${e.code()}")
        }
    }

    /** Applies a WebSocket message; true when the whole queue should be fetched again. */
    fun onEvent(event: LiveEvent): Boolean = when (event) {
        is LiveEvent.DownloadProgress -> {
            var known = false
            state.update { jobs ->
                known = event.job.songId in jobs
                // Keep the queue row's details; the message carries status and progress.
                val merged = jobs[event.job.songId]?.copy(
                    status = event.job.status,
                    progress = event.job.progress,
                    message = event.job.message,
                ) ?: event.job
                jobs + (event.job.songId to merged)
            }
            !known
        }

        LiveEvent.QueueReload -> true

        else -> false
    }

    /** Forgets the queue (unpaired, another server). */
    fun clear() {
        state.value = emptyMap()
    }

    private companion object {
        const val TAG = "ServerQueue"
    }
}
