package com.henriquesebastiao.downtify.feature.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.henriquesebastiao.downtify.core.data.library.LibraryRepository
import com.henriquesebastiao.downtify.core.data.library.RecentsRepository
import com.henriquesebastiao.downtify.core.data.library.SyncStatus
import com.henriquesebastiao.downtify.core.data.session.ConnectionState
import com.henriquesebastiao.downtify.core.data.session.ServerRepository
import com.henriquesebastiao.downtify.core.data.sync.SyncCoordinator
import com.henriquesebastiao.downtify.core.model.Album
import com.henriquesebastiao.downtify.core.model.PlaybackContext
import com.henriquesebastiao.downtify.core.model.PlaybackContextType
import com.henriquesebastiao.downtify.core.model.Playlist
import com.henriquesebastiao.downtify.core.model.RecentContext
import com.henriquesebastiao.downtify.core.model.Track
import com.henriquesebastiao.downtify.core.network.dto.SuggestedMixDto
import com.henriquesebastiao.downtify.core.player.PlayerController
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

enum class ServerStatus { Streaming, Syncing, Unreachable, DifferentServer }

data class SuggestedMixArtistUi(
    val name: String,
    val coverTrackId: String? = null,
)

data class SuggestedMixUi(
    val title: String = "Suggested Mix",
    val subtitle: String = "",
    val topArtists: List<SuggestedMixArtistUi> = emptyList(),
    val tracks: List<Track> = emptyList(),
)

data class HomeUiState(
    val loading: Boolean = true,
    val serverName: String = "",
    val status: ServerStatus = ServerStatus.Streaming,
    /** "Jump back in": recent contexts, or — before anything was played — Liked songs and the newest albums. */
    val jumpBackIn: List<RecentContext> = emptyList(),
    val recentlyAdded: List<Album> = emptyList(),
    val favoritePlaylists: List<Playlist> = emptyList(),
    val suggestedMix: SuggestedMixUi? = null,
    val refreshing: Boolean = false,
    val libraryEmpty: Boolean = false,
    /** What the server can do (`capabilities`): the shortcuts below "Recently added". */
    val showDiscover: Boolean = false,
    val showPodcasts: Boolean = false,
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val library: LibraryRepository,
    recents: RecentsRepository,
    server: ServerRepository,
    private val sync: SyncCoordinator,
    private val player: PlayerController,
) : ViewModel() {

    private val remoteMix = MutableStateFlow<SuggestedMixDto?>(null)

    init {
        viewModelScope.launch {
            library.successfulSync.collect {
                remoteMix.value = library.suggestedMix()
            }
        }
    }

    val uiState: StateFlow<HomeUiState> = combine(
        combine(library.library, library.likedIds, library.playlists, ::Triple),
        combine(recents.recents(RECENT_CONTEXT_LIMIT), remoteMix, ::Pair),
        library.syncStatus,
        combine(server.connection, server.session, server.serverInfo, ::Triple),
    ) { (snapshot, likedIds, playlists), (recentList, mixDto), syncStatus, (connection, session, info) ->
        val newest = snapshot?.albums.orEmpty().sortedByDescending { it.added }
        val jump = recentList.ifEmpty {
            buildList {
                if (likedIds.isNotEmpty()) add(RecentContext(PlaybackContextType.Liked, "", "", null, 0))
                newest.take(JUMP_BACK_IN_SIZE - size).forEach {
                    add(RecentContext(PlaybackContextType.Album, it.id, it.title, it.coverTrackId, 0))
                }
            }
        }
        val mixUi = if (snapshot != null && !snapshot.isEmpty) {
            val byFile = snapshot.tracks.associateBy { it.file }
            val resolvedTracks = mixDto?.tracks.orEmpty().mapNotNull { t ->
                snapshot.byId[t.trackId] ?: byFile[t.file]
            }.ifEmpty {
                snapshot.tracks.take(25)
            }
            val resolvedArtists = mixDto?.topArtists.orEmpty().map { a ->
                val coverId = byFile[a.coverFile]?.id
                    ?: snapshot.tracks.firstOrNull {
                        it.hasCover && (it.albumArtist.equals(a.name, ignoreCase = true) || it.artist.contains(a.name, ignoreCase = true))
                    }?.id
                SuggestedMixArtistUi(name = a.name, coverTrackId = coverId)
            }.ifEmpty {
                snapshot.artists.take(5).map { SuggestedMixArtistUi(it.name, it.coverTrackId) }
            }
            if (resolvedTracks.isNotEmpty()) {
                val subtitle = mixDto?.subtitle?.takeIf { it.isNotBlank() } ?: run {
                    val names = resolvedArtists.take(3).map { it.name }.filter { it.isNotBlank() }
                    when (names.size) {
                        0 -> "Your personalized daily mix"
                        1 -> "Your personalized mix featuring ${names[0]}"
                        2 -> "Your personalized mix including ${names[0]} and ${names[1]}"
                        else -> "Your personalized mix including ${names[0]}, ${names[1]}, and ${names[2]}..."
                    }
                }
                SuggestedMixUi(
                    title = mixDto?.title?.ifBlank { "Suggested Mix" } ?: "Suggested Mix",
                    subtitle = subtitle,
                    topArtists = resolvedArtists.take(5),
                    tracks = resolvedTracks,
                )
            } else {
                null
            }
        } else {
            null
        }
        HomeUiState(
            loading = snapshot == null,
            serverName = session?.serverName.orEmpty().ifBlank { session?.baseUrl?.substringAfter("://").orEmpty() },
            status = when {
                connection == ConnectionState.DifferentServer -> ServerStatus.DifferentServer
                syncStatus == SyncStatus.Syncing -> ServerStatus.Syncing
                connection == ConnectionState.Unreachable || syncStatus is SyncStatus.Failed -> ServerStatus.Unreachable
                else -> ServerStatus.Streaming
            },
            jumpBackIn = jump.take(RECENT_CONTEXT_LIMIT),
            recentlyAdded = newest.take(RECENTLY_ADDED_SIZE),
            favoritePlaylists = playlists.filter { it.favorite && !it.liked }.sortedBy { it.title.lowercase() },
            suggestedMix = mixUi,
            refreshing = syncStatus == SyncStatus.Syncing,
            libraryEmpty = snapshot?.isEmpty == true,
            showDiscover = info?.capabilities?.discover == true,
            showPodcasts = info?.capabilities?.podcasts == true,
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(STOP_TIMEOUT_MS), HomeUiState())

    /** Pull to refresh: the server rescans its folder, then the app syncs. */
    fun refresh() = sync.requestSync(refresh = true)

    fun playSuggestedMix() {
        val mix = uiState.value.suggestedMix ?: return
        if (mix.tracks.isEmpty()) return
        player.play(
            mix.tracks,
            0,
            PlaybackContext(PlaybackContextType.Songs, "", mix.title),
            shuffle = false,
        )
    }

    private companion object {
        const val JUMP_BACK_IN_SIZE = 6
        const val RECENT_CONTEXT_LIMIT = 12
        const val RECENTLY_ADDED_SIZE = 12
        const val STOP_TIMEOUT_MS = 5_000L
    }
}
