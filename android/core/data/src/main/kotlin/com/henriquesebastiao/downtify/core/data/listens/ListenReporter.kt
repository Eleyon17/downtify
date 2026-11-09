package com.henriquesebastiao.downtify.core.data.listens

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import com.henriquesebastiao.downtify.core.data.db.DowntifyDatabase
import com.henriquesebastiao.downtify.core.data.db.PendingListenEntity
import com.henriquesebastiao.downtify.core.network.ApiFactory
import com.henriquesebastiao.downtify.core.network.dto.ListenRequest
import com.henriquesebastiao.downtify.core.network.session.SessionStore
import dagger.hilt.android.qualifiers.ApplicationContext
import java.time.Instant
import java.time.temporal.ChronoUnit
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Plays to report (`POST /api/discover/listens`): queued in Room first, then
 * sent by [ListenReportWorker] once there's a connection — so plays made
 * offline are reported later, with the time they happened.
 */
@Singleton
class ListenReporter @Inject constructor(
    @ApplicationContext private val context: Context,
    private val db: DowntifyDatabase,
    private val sessions: SessionStore,
    private val apis: ApiFactory,
) {
    suspend fun report(trackId: String, playId: String, playedAt: Instant) {
        db.pendingListens().insert(
            PendingListenEntity(
                playId = playId,
                trackId = trackId,
                playedAt = playedAt.truncatedTo(ChronoUnit.SECONDS).toString(),
                createdAt = System.currentTimeMillis(),
            ),
        )
        schedule()
    }

    /** Queues a run of the worker (after the current one, if it's running). */
    fun schedule() {
        val request = OneTimeWorkRequestBuilder<ListenReportWorker>()
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, BACKOFF_SECONDS, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork(WORK_NAME, ExistingWorkPolicy.APPEND_OR_REPLACE, request)
    }

    internal suspend fun flush(): ListenFlusher.Result {
        val session = sessions.current ?: return ListenFlusher.Result.Stopped
        val api = apis.create(session.baseUrl)
        val dao = db.pendingListens()
        val store = object : PendingListenStore {
            override suspend fun oldest(limit: Int) =
                dao.oldest(limit).map { PendingListen(it.playId, it.trackId, it.playedAt) }

            override suspend fun remove(playId: String) = dao.delete(playId)
        }
        val sender = ListenSender { listen ->
            api.reportListen(ListenRequest(listen.trackId, listen.playId, listen.playedAt)).code()
        }
        return ListenFlusher(store, sender).flush()
    }

    private companion object {
        const val WORK_NAME = "listen-reports"
        const val BACKOFF_SECONDS = 30L
    }
}
