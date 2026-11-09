package com.henriquesebastiao.downtify.core.data.listens

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

/** Sends the queued play reports; retried with a backoff while the server can't take them. */
@HiltWorker
class ListenReportWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val reporter: ListenReporter,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result = when (reporter.flush()) {
        ListenFlusher.Result.Done, ListenFlusher.Result.Stopped -> Result.success()
        ListenFlusher.Result.Retry -> if (runAttemptCount < MAX_ATTEMPTS) Result.retry() else Result.success()
    }

    private companion object {
        /** After this many, wait for the next play (or launch) to try again. */
        const val MAX_ATTEMPTS = 10
    }
}
