package com.henriquesebastiao.downtify.core.data.offline

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

/**
 * Downloads the tracks the offline plan is missing, one after another, until
 * none are left. Stopped (constraints lost, the 10-minute window over), it's
 * retried and resumes the interrupted file with a Range request.
 */
@HiltWorker
class OfflineSyncWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val offline: OfflineRepository,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val handled = mutableSetOf<String>()
        while (!isStopped) {
            when (val step = offline.downloadNext(handled)) {
                is OfflineRepository.Step.Handled -> handled += step.trackId

                OfflineRepository.Step.Done, OfflineRepository.Step.OutOfSpace -> return Result.success()

                OfflineRepository.Step.Retry ->
                    // After that, the next change or app start schedules it again.
                    return if (runAttemptCount < MAX_ATTEMPTS) Result.retry() else Result.success()
            }
        }
        return Result.retry()
    }

    private companion object {
        const val MAX_ATTEMPTS = 8
    }
}
