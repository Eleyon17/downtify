package com.henriquesebastiao.downtify.core.network.discovery

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Build
import android.util.Log
import androidx.annotation.RequiresApi
import dagger.hilt.android.qualifiers.ApplicationContext
import java.net.Inet4Address
import java.net.InetAddress
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.coroutines.resume
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.conflate
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine

/** A Downtify server announcing itself on the LAN as `_downtify._tcp`. */
data class DiscoveredServer(
    val serviceName: String,
    val serverId: String,
    val name: String,
    val version: String,
    val apiVersion: Int,
    val baseUrl: String,
) {
    /** `192.168.1.20:8000`, for display. */
    val address: String get() = baseUrl.substringAfter("://")
}

/**
 * Browses mDNS/DNS-SD with [NsdManager]. Discovery is a convenience: the
 * connect screen always offers manual entry too (Docker's bridge network
 * doesn't announce).
 */
@Singleton
class ServerDiscovery @Inject constructor(@ApplicationContext private val context: Context) {
    private val nsd: NsdManager? get() = context.getSystemService(NsdManager::class.java)

    /** The servers found so far, updated as they come and go; browsing stops when collection does. */
    fun servers(): Flow<List<DiscoveredServer>> = callbackFlow {
        val manager = nsd ?: run {
            trySend(emptyList())
            awaitClose()
            return@callbackFlow
        }
        val found = ConcurrentHashMap<String, DiscoveredServer>()
        val toResolve = Channel<NsdServiceInfo>(Channel.UNLIMITED)
        fun publish() = trySend(found.values.sortedBy { it.name.lowercase() })

        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) = Unit
            override fun onDiscoveryStopped(serviceType: String) = Unit
            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                Log.w(TAG, "NSD discovery failed to start: $errorCode")
            }
            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) = Unit
            override fun onServiceFound(info: NsdServiceInfo) {
                toResolve.trySend(info)
            }
            override fun onServiceLost(info: NsdServiceInfo) {
                if (found.remove(info.serviceName) != null) publish()
            }
        }

        // Resolve one at a time: before Android 14, NsdManager fails concurrent resolves.
        launch {
            for (info in toResolve) {
                resolve(manager, info)?.let(::toServer)?.let { server ->
                    found[info.serviceName] = server
                    publish()
                }
            }
        }

        publish()
        manager.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, listener)
        awaitClose {
            toResolve.close()
            runCatching { manager.stopServiceDiscovery(listener) }
        }
    }.conflate()

    private suspend fun resolve(manager: NsdManager, info: NsdServiceInfo): NsdServiceInfo? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            resolveWithCallback(manager, info)
        } else {
            resolveLegacy(manager, info)
        }

    @RequiresApi(Build.VERSION_CODES.UPSIDE_DOWN_CAKE)
    private suspend fun resolveWithCallback(manager: NsdManager, info: NsdServiceInfo): NsdServiceInfo? =
        suspendCancellableCoroutine { cont ->
            val executor = Executors.newSingleThreadExecutor()
            val callback = object : NsdManager.ServiceInfoCallback {
                override fun onServiceInfoCallbackRegistrationFailed(errorCode: Int) {
                    if (cont.isActive) cont.resume(null)
                    executor.shutdown()
                }
                override fun onServiceUpdated(serviceInfo: NsdServiceInfo) {
                    if (cont.isActive) cont.resume(serviceInfo)
                    runCatching { manager.unregisterServiceInfoCallback(this) }
                }
                override fun onServiceLost() = Unit
                override fun onServiceInfoCallbackUnregistered() {
                    executor.shutdown()
                }
            }
            manager.registerServiceInfoCallback(info, executor, callback)
            cont.invokeOnCancellation { runCatching { manager.unregisterServiceInfoCallback(callback) } }
        }

    @Suppress("DEPRECATION")
    private suspend fun resolveLegacy(manager: NsdManager, info: NsdServiceInfo): NsdServiceInfo? =
        suspendCancellableCoroutine { cont ->
            manager.resolveService(
                info,
                object : NsdManager.ResolveListener {
                    override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                        if (cont.isActive) cont.resume(null)
                    }
                    override fun onServiceResolved(serviceInfo: NsdServiceInfo) {
                        if (cont.isActive) cont.resume(serviceInfo)
                    }
                },
            )
        }

    private fun toServer(info: NsdServiceInfo): DiscoveredServer? {
        val txt = info.attributes.mapValues { (_, value) -> value?.decodeToString().orEmpty() }
        val host = hostOf(info) ?: return null
        val port = txt["port"]?.toIntOrNull() ?: info.port
        val scheme = txt["scheme"]?.takeIf { it == "http" || it == "https" } ?: "http"
        val path = txt["path"].orEmpty().trim('/').let { if (it.isEmpty()) "" else "/$it" }
        val hostPart = if (host.contains(':')) "[$host]" else host
        return DiscoveredServer(
            serviceName = info.serviceName,
            serverId = txt["id"].orEmpty(),
            name = txt["name"]?.ifBlank { null } ?: info.serviceName,
            version = txt["version"].orEmpty(),
            apiVersion = txt["api"]?.toIntOrNull() ?: 0,
            baseUrl = "$scheme://$hostPart:$port$path",
        )
    }

    /** The resolved address, IPv4 preferred. */
    private fun hostOf(info: NsdServiceInfo): String? {
        val addresses: List<InetAddress> = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            info.hostAddresses
        } else {
            @Suppress("DEPRECATION")
            listOfNotNull(info.host)
        }
        val best = addresses.firstOrNull { it is Inet4Address } ?: addresses.firstOrNull() ?: return null
        return best.hostAddress?.substringBefore('%')
    }

    private companion object {
        const val TAG = "ServerDiscovery"
        const val SERVICE_TYPE = "_downtify._tcp"
    }
}
