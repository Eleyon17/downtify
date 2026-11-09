package com.henriquesebastiao.downtify.core.data

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Whether the phone is online, and whether its network is metered (mobile data, a hotspot). */
@Singleton
class NetworkMonitor @Inject constructor(@ApplicationContext context: Context) {
    data class Status(val online: Boolean, val metered: Boolean)

    private val connectivity = context.getSystemService(ConnectivityManager::class.java)
    private val state = MutableStateFlow(read())

    val status: StateFlow<Status> = state.asStateFlow()

    /** Read at the moment of use (e.g. when a stream starts), always current. */
    val isMetered: Boolean get() = read().metered

    init {
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) = refresh()
            override fun onLost(network: Network) = refresh()
            override fun onCapabilitiesChanged(network: Network, caps: NetworkCapabilities) = refresh()
        }
        runCatching {
            connectivity?.registerNetworkCallback(
                NetworkRequest.Builder().addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET).build(),
                callback,
            )
        }
    }

    private fun refresh() {
        state.value = read()
    }

    private fun read(): Status {
        val caps = connectivity?.let { it.getNetworkCapabilities(it.activeNetwork) } ?: return Status(false, false)
        return Status(
            online = caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET),
            metered = !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_METERED),
        )
    }
}
