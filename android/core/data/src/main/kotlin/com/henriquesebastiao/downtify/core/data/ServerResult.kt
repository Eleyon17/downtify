package com.henriquesebastiao.downtify.core.data

import android.util.Log
import com.henriquesebastiao.downtify.core.network.ApiFactory
import com.henriquesebastiao.downtify.core.network.WebApi
import com.henriquesebastiao.downtify.core.network.session.SessionStore
import java.io.IOException
import kotlinx.serialization.SerializationException
import retrofit2.HttpException

/** What asking the server for something came to. */
sealed interface ServerResult<out T> {
    data class Ok<T>(val value: T) : ServerResult<T>

    /** The server can't be reached (offline, another network), or there's no server paired. */
    data object Unreachable : ServerResult<Nothing>

    /** It answered with an error, or something the app couldn't read. */
    data class Failed(val status: Int?) : ServerResult<Nothing>
}

/**
 * Runs [block] against the paired server's web API. [patient] is for calls that answer only
 * when the server is done (it downloads an episode, or asks Deezer first).
 */
internal suspend fun <T> callServer(
    sessions: SessionStore,
    apis: ApiFactory,
    patient: Boolean = false,
    block: suspend (WebApi) -> T,
): ServerResult<T> {
    val session = sessions.current ?: return ServerResult.Unreachable
    val api = if (patient) apis.createWebPatient(session.baseUrl) else apis.createWeb(session.baseUrl)
    return try {
        ServerResult.Ok(block(api))
    } catch (e: HttpException) {
        Log.w(TAG, "Server answered ${e.code()}")
        ServerResult.Failed(e.code())
    } catch (e: SerializationException) {
        Log.w(TAG, "Unexpected answer", e)
        ServerResult.Failed(null)
    } catch (e: IOException) {
        Log.d(TAG, "Server unreachable", e)
        ServerResult.Unreachable
    }
}

private const val TAG = "ServerCall"
