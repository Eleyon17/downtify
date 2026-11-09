package com.henriquesebastiao.downtify.feature.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.henriquesebastiao.downtify.core.data.library.LibraryRepository
import com.henriquesebastiao.downtify.core.data.offline.OfflineRepository
import com.henriquesebastiao.downtify.core.data.session.ConnectionState
import com.henriquesebastiao.downtify.core.data.session.ServerRepository
import com.henriquesebastiao.downtify.core.data.settings.SettingsRepository
import com.henriquesebastiao.downtify.core.data.settings.ThemeMode
import com.henriquesebastiao.downtify.core.data.settings.UserSettings
import com.henriquesebastiao.downtify.core.model.AppFont
import com.henriquesebastiao.downtify.core.model.NormalizationLevel
import com.henriquesebastiao.downtify.core.model.StreamFormat
import com.henriquesebastiao.downtify.core.model.StreamQuality
import com.henriquesebastiao.downtify.core.model.Transcoding
import com.henriquesebastiao.downtify.core.network.dto.ListeningStatsDto
import com.henriquesebastiao.downtify.core.network.dto.UpdateCheckDto
import com.henriquesebastiao.downtify.core.network.dto.UpgradeStatusDto
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class SettingsUiState(
    val serverName: String = "",
    /** The account this phone belongs to; blank on servers without accounts. */
    val username: String = "",
    val address: String = "",
    val baseUrl: String = "",
    val version: String = "",
    val apiVersion: Int = 0,
    val connection: ConnectionState = ConnectionState.Unknown,
    val transcoding: Transcoding = Transcoding(),
    val settings: UserSettings = UserSettings(),
    /** Qualities to offer for mobile data (and Wi-Fi): Original first, then what the server can make. */
    val qualityOptions: List<StreamQuality> = listOf(StreamQuality.Original),
    /** Bytes the offline copies take now. */
    val offlineUsedBytes: Long = 0,
    val role: String = "",
    val displayName: String = "",
    val email: String = "",
    val hidePublicPlaylistsByDefault: Boolean = false,
    val stats: ListeningStatsDto? = null,
    val statsLoading: Boolean = false,
    val upgradeStatus: UpgradeStatusDto? = null,
    val updateCheck: UpdateCheckDto? = null,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val server: ServerRepository,
    private val settings: SettingsRepository,
    private val library: LibraryRepository,
    offline: OfflineRepository,
) : ViewModel() {

    private val mutableStats = MutableStateFlow<ListeningStatsDto?>(null)
    val stats = mutableStats.asStateFlow()
    private val mutableStatsLoading = MutableStateFlow(false)
    val statsLoading = mutableStatsLoading.asStateFlow()
    private val mutableUpgradeStatus = MutableStateFlow<UpgradeStatusDto?>(null)
    val upgradeStatus = mutableUpgradeStatus.asStateFlow()
    private val mutableUpdateCheck = MutableStateFlow<UpdateCheckDto?>(null)
    val updateCheck = mutableUpdateCheck.asStateFlow()
    private val mutableRole = MutableStateFlow("")
    val role = mutableRole.asStateFlow()
    private val mutableDisplayName = MutableStateFlow("")
    val displayName = mutableDisplayName.asStateFlow()
    private val mutableEmail = MutableStateFlow("")
    val email = mutableEmail.asStateFlow()
    private val mutableHidePublic = MutableStateFlow(false)
    val hidePublic = mutableHidePublic.asStateFlow()

    val uiState: StateFlow<SettingsUiState> = combine(
        server.session,
        server.serverInfo,
        server.connection,
        settings.settings,
        offline.state,
    ) { session, info, connection, prefs, offlineState ->
        val transcoding = info?.capabilities?.transcoding ?: Transcoding()
        SettingsUiState(
            serverName = session?.serverName.orEmpty().ifBlank { info?.name.orEmpty() },
            username = session?.username.orEmpty(),
            address = session?.baseUrl.orEmpty().substringAfter("://"),
            baseUrl = session?.baseUrl.orEmpty(),
            version = info?.version.orEmpty(),
            apiVersion = info?.apiVersion ?: 0,
            connection = connection,
            transcoding = transcoding,
            settings = prefs,
            qualityOptions = qualityOptions(transcoding),
            offlineUsedBytes = offlineState?.usedBytes ?: 0,
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(STOP_TIMEOUT_MS), SettingsUiState())

    init {
        viewModelScope.launch { server.refresh() }
        refreshAccountAndUpdate()
    }

    fun refreshAccountAndUpdate() {
        viewModelScope.launch {
            library.fetchMe()?.let { me ->
                mutableRole.value = me.user?.role.orEmpty()
                mutableDisplayName.value = me.user?.displayName.orEmpty()
                mutableEmail.value = me.user?.email.orEmpty()
                mutableHidePublic.value = me.preferences.hidePublicPlaylistsByDefault
            }
            mutableUpdateCheck.value = library.checkUpdate()
        }
    }

    fun loadStats() {
        if (mutableStatsLoading.value) return
        mutableStatsLoading.value = true
        viewModelScope.launch {
            try {
                mutableStats.value = library.myStats()
            } finally {
                mutableStatsLoading.value = false
            }
        }
    }

    fun clearStats() {
        viewModelScope.launch {
            if (library.clearMyStats()) {
                mutableStats.value = library.myStats()
            }
        }
    }

    fun updateProfile(newDisplayName: String, newEmail: String, hidePublicByDefault: Boolean) {
        viewModelScope.launch {
            if (library.updateMe(displayName = newDisplayName.trim(), email = newEmail.trim())) {
                mutableDisplayName.value = newDisplayName.trim()
                mutableEmail.value = newEmail.trim()
            }
            if (library.setMyPreferences(hidePublicByDefault)) {
                mutableHidePublic.value = hidePublicByDefault
            }
        }
    }

    fun loadUpgradeStatus() {
        viewModelScope.launch {
            mutableUpgradeStatus.value = library.upgradeStatus()
        }
    }

    fun scanUpgrade() {
        viewModelScope.launch {
            mutableUpgradeStatus.value = library.upgradeScan() ?: library.upgradeStatus()
        }
    }

    fun startUpgrade() {
        viewModelScope.launch {
            mutableUpgradeStatus.value = library.upgradeStart() ?: library.upgradeStatus()
        }
    }

    fun setWifiQuality(value: StreamQuality) = launch { settings.setWifiQuality(value) }
    fun setMobileQuality(value: StreamQuality) = launch { settings.setMobileQuality(value) }
    fun setNormalizeVolume(value: Boolean) = launch { settings.setNormalizeVolume(value) }
    fun setNormalizationLevel(value: NormalizationLevel) = launch { settings.setNormalizationLevel(value) }
    fun setTheme(value: ThemeMode) = launch { settings.setTheme(value) }
    fun setDynamicColor(value: Boolean) = launch { settings.setDynamicColor(value) }
    fun setAmoled(value: Boolean) = launch { settings.setAmoled(value) }
    fun setFont(value: AppFont) = launch { settings.setFont(value) }
    fun setFloatingNavBar(value: Boolean) = launch { settings.setFloatingNavBar(value) }
    fun setDownloadWifiOnly(value: Boolean) = launch { settings.setDownloadWifiOnly(value) }
    fun setOfflineLimit(bytes: Long) = launch { settings.setOfflineLimit(bytes) }
    fun setReadAhead(tracks: Int) = launch { settings.setReadAhead(tracks) }
    fun setStreamCacheMb(mb: Int) = launch { settings.setStreamCacheMb(mb) }
    fun setReadAheadMobile(enabled: Boolean) = launch { settings.setReadAheadMobile(enabled) }
    fun unpair() = launch { server.unpair() }

    private fun launch(block: suspend () -> Unit) {
        viewModelScope.launch { block() }
    }

    companion object {
        private const val STOP_TIMEOUT_MS = 5_000L

        /** A short list per format rather than every format × bitrate the server allows. */
        private val SUGGESTED = mapOf(
            StreamFormat.Opus to listOf(96, 128, 160, 256),
            StreamFormat.Aac to listOf(128, 192, 256),
            StreamFormat.Mp3 to listOf(128, 192, 320),
        )

        fun qualityOptions(transcoding: Transcoding): List<StreamQuality> {
            if (!transcoding.available) return listOf(StreamQuality.Original)
            val transcoded = SUGGESTED.flatMap { (format, bitrates) ->
                if (transcoding.formats.isNotEmpty() &&
                    format.wireName !in transcoding.formats
                ) {
                    return@flatMap emptyList()
                }
                bitrates.filter {
                    transcoding.bitrates.isEmpty() || it in transcoding.bitrates
                }.map { StreamQuality(format, it) }
            }
            return listOf(StreamQuality.Original) + transcoded
        }
    }
}
