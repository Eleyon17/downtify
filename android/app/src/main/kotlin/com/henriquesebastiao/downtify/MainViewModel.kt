package com.henriquesebastiao.downtify

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.henriquesebastiao.downtify.core.data.session.ServerRepository
import com.henriquesebastiao.downtify.core.data.settings.SettingsRepository
import com.henriquesebastiao.downtify.core.data.settings.UserSettings
import com.henriquesebastiao.downtify.core.model.PairingPayload
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.emitAll
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

sealed interface AppState {
    data object Loading : AppState
    data object NeedsPairing : AppState
    data class Paired(val baseUrl: String, val serverName: String) : AppState
}

@HiltViewModel
class MainViewModel @Inject constructor(private val server: ServerRepository, settings: SettingsRepository) :
    ViewModel() {
    private val loaded = MutableStateFlow(false)
    private val pendingPairing = MutableStateFlow<PairingPayload?>(null)

    val settings: StateFlow<UserSettings?> = settings.settings
        .stateIn(viewModelScope, SharingStarted.Eagerly, null)

    val appState: StateFlow<AppState> = combine(loaded, serverSession()) { isLoaded, session ->
        when {
            !isLoaded -> AppState.Loading
            session == null -> AppState.NeedsPairing
            else -> AppState.Paired(session.baseUrl, session.serverName)
        }
    }.stateIn(viewModelScope, SharingStarted.Eagerly, AppState.Loading)

    /** A pairing QR code opened from outside the app (the system camera). */
    val pairingRequest: StateFlow<PairingPayload?> = pendingPairing.asStateFlow()

    init {
        viewModelScope.launch {
            server.ensureLoaded()
            loaded.value = true
        }
    }

    /** Keep the splash screen until the session and settings are read (a few ms). */
    val isReady: Boolean get() = appState.value != AppState.Loading && settings.value != null

    fun onPairingLink(uri: String) {
        PairingPayload.parse(uri)?.let { pendingPairing.value = it }
    }

    fun consumePairingRequest() {
        pendingPairing.value = null
    }

    private fun serverSession() = flow {
        server.ensureLoaded()
        emitAll(server.session)
    }
}
