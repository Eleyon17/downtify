package com.henriquesebastiao.downtify.feature.collection

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.henriquesebastiao.downtify.core.data.library.LibraryRepository
import com.henriquesebastiao.downtify.core.data.offline.OfflineRepository
import com.henriquesebastiao.downtify.core.model.CatalogSource
import com.henriquesebastiao.downtify.core.model.PlaybackContext
import com.henriquesebastiao.downtify.core.model.PlaybackContextType
import com.henriquesebastiao.downtify.core.model.Playlist
import com.henriquesebastiao.downtify.core.model.RemoteSong
import com.henriquesebastiao.downtify.core.model.Track
import com.henriquesebastiao.downtify.core.network.dto.MobileUserDto
import com.henriquesebastiao.downtify.core.network.dto.PlaylistSuggestionItemDto
import com.henriquesebastiao.downtify.core.player.PlayerController
import com.henriquesebastiao.downtify.core.player.RemotePlayback
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class CollectionKind { Album, Playlist, Liked }

data class CollectionUiState(
    val loading: Boolean = true,
    val notFound: Boolean = false,
    val kind: CollectionKind = CollectionKind.Album,
    val title: String = "",
    val artist: String = "",
    val artistId: String = "",
    val year: String = "",
    val tracks: List<Track> = emptyList(),
    val coverTrackId: String? = null,
    /** For a playlist with its own cover on the server. */
    val playlist: Playlist? = null,
    val currentTrackId: String? = null,
    val isPlaying: Boolean = false,
    /** This album/playlist is what's loaded in the player. */
    val isCurrentContext: Boolean = false,
    val likedIds: Set<String> = emptySet(),
    val offline: CollectionOffline = CollectionOffline(),
    val favoriteBusy: Boolean = false,
    val favoriteError: Boolean = false,
    val suggestions: List<PlaylistSuggestionItemDto> = emptyList(),
    val loadingSuggestions: Boolean = false,
    val addingSuggestionIds: Set<String> = emptySet(),
    val addedSuggestionIds: Set<String> = emptySet(),
    val users: List<MobileUserDto> = emptyList(),
) {
    val durationSeconds: Double get() = tracks.sumOf { it.duration }
}

/** Whether this collection is kept on the phone, and how far its download got. */
data class CollectionOffline(
    val kept: Boolean = false,
    val downloaded: Int = 0,
    val total: Int = 0,
    /** Tracks of this collection with a copy on the phone (kept here or by another collection). */
    val downloadedIds: Set<String> = emptySet(),
) {
    val isComplete: Boolean get() = kept && total > 0 && downloaded == total
}

/** An album, a playlist or Liked songs: a header and its tracks. */
@HiltViewModel
class CollectionViewModel @Inject constructor(
    savedState: SavedStateHandle,
    private val library: LibraryRepository,
    private val player: PlayerController,
    private val offline: OfflineRepository,
    private val remotePlayback: RemotePlayback,
) : ViewModel() {
    private val albumId: String? = savedState["albumId"]
    private val playlistName: String? = savedState["name"]
    val kind = when {
        albumId != null -> CollectionKind.Album
        playlistName != null -> CollectionKind.Playlist
        else -> CollectionKind.Liked
    }

    private val contextType = when (kind) {
        CollectionKind.Album -> PlaybackContextType.Album
        CollectionKind.Playlist -> PlaybackContextType.Playlist
        CollectionKind.Liked -> PlaybackContextType.Liked
    }

    private val refId: String = albumId ?: playlistName.orEmpty()
    private val mutableFavoriteBusy = MutableStateFlow(false)
    val favoriteBusy = mutableFavoriteBusy.asStateFlow()
    private val mutableFavoriteError = MutableStateFlow(false)
    val favoriteError = mutableFavoriteError.asStateFlow()
    private val mutableSuggestions = MutableStateFlow<List<PlaylistSuggestionItemDto>>(emptyList())
    val suggestions = mutableSuggestions.asStateFlow()
    private val mutableLoadingSuggestions = MutableStateFlow(false)
    val loadingSuggestions = mutableLoadingSuggestions.asStateFlow()
    private val mutableAddingSuggestionIds = MutableStateFlow<Set<String>>(emptySet())
    val addingSuggestionIds = mutableAddingSuggestionIds.asStateFlow()
    private val mutableAddedSuggestionIds = MutableStateFlow<Set<String>>(emptySet())
    val addedSuggestionIds = mutableAddedSuggestionIds.asStateFlow()
    private val mutableUsers = MutableStateFlow<List<MobileUserDto>>(emptyList())
    val users = mutableUsers.asStateFlow()
    val playlists: StateFlow<List<Playlist>> = library.playlists

    init {
        if (kind == CollectionKind.Playlist) {
            loadSuggestions()
        }
    }

    val uiState: StateFlow<CollectionUiState> = combine(
        library.library,
        library.playlists,
        library.likedIds,
        player.nowPlaying,
        offline.state,
    ) { snapshot, playlists, liked, playing, offlineState ->
        if (snapshot == null) return@combine CollectionUiState(kind = kind)
        val base = CollectionUiState(
            loading = false,
            kind = kind,
            currentTrackId = playing.trackId,
            isPlaying = playing.isPlaying,
            likedIds = liked.toSet(),
        )
        val state = when (kind) {
            CollectionKind.Album -> snapshot.albumsById[albumId]?.let { album ->
                base.copy(
                    title = album.title,
                    artist = album.artist,
                    artistId = album.artistId,
                    year = album.year,
                    tracks = album.tracks,
                    coverTrackId = album.coverTrackId,
                )
            }

            CollectionKind.Playlist -> playlists.firstOrNull { it.name == playlistName }?.let { p ->
                val tracks = snapshot.tracks(p.trackIds)
                base.copy(
                    title = p.title,
                    tracks = tracks,
                    playlist = p,
                    coverTrackId = tracks.firstOrNull {
                        it.hasCover
                    }?.id,
                )
            }

            CollectionKind.Liked -> {
                val tracks = snapshot.tracks(liked)
                base.copy(tracks = tracks, coverTrackId = tracks.firstOrNull { it.hasCover }?.id)
            }
        } ?: base.copy(notFound = true)
        val kept = offlineState?.kept(contextType, refId)
        state.copy(
            isCurrentContext = playing.context == context(state.title),
            offline = CollectionOffline(
                kept = kept != null,
                downloaded = kept?.progress?.downloaded ?: 0,
                total = kept?.progress?.total ?: 0,
                downloadedIds =
                    offlineState?.files?.keys?.let { ids ->
                        state.tracks.map { it.id }.filterTo(mutableSetOf()) {
                            it in
                                ids
                        }
                    }
                        ?: emptySet(),
            ),
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(STOP_TIMEOUT_MS), CollectionUiState(kind = kind))

    fun play(index: Int, shuffle: Boolean = false) {
        val state = uiState.value
        player.play(state.tracks, index, context(state.title), shuffle)
    }

    /** The big play button: pause/resume when this is what's playing, else play from the top. */
    fun playOrPause() {
        if (uiState.value.isCurrentContext) player.togglePlayPause() else play(0)
    }

    fun shuffle() = play(0, shuffle = true)

    fun addToQueue(track: Track) = player.addToQueue(track)

    fun toggleLike(track: Track) {
        viewModelScope.launch { library.setLiked(track.id, track.id !in uiState.value.likedIds) }
    }

    fun toggleFavorite() {
        val playlist = uiState.value.playlist ?: return
        if (!playlist.favoriteSupported || mutableFavoriteBusy.value) return
        mutableFavoriteBusy.value = true
        mutableFavoriteError.value = false
        viewModelScope.launch {
            try {
                mutableFavoriteError.value = !library.setPlaylistFavorite(playlist.name, !playlist.favorite)
            } finally {
                mutableFavoriteBusy.value = false
            }
        }
    }

    /** Keeps this collection on the phone, or removes its copies. */
    fun toggleOffline() {
        val keep = !uiState.value.offline.kept
        viewModelScope.launch { offline.setKept(contextType, refId, keep) }
    }

    fun loadSuggestions() {
        val name = playlistName ?: return
        if (mutableLoadingSuggestions.value) return
        mutableLoadingSuggestions.value = true
        viewModelScope.launch {
            try {
                mutableSuggestions.value = library.playlistSuggestions(name)
            } finally {
                mutableLoadingSuggestions.value = false
            }
        }
    }

    fun playSuggestedSong(item: PlaylistSuggestionItemDto) {
        val tracks = uiState.value.tracks
        val matchingLocal = if (item.trackId.isNotBlank()) {
            tracks.firstOrNull { it.id == item.trackId }
        } else if (item.displayFile.isNotBlank()) {
            tracks.firstOrNull { it.id == item.displayFile }
        } else null

        if (matchingLocal != null) {
            val idx = tracks.indexOf(matchingLocal).coerceAtLeast(0)
            player.play(tracks, idx, context(uiState.value.title))
            return
        }

        viewModelScope.launch {
            val remote = RemoteSong(
                id = item.displayId,
                title = item.displayTitle,
                artists = if (item.displayArtist.isNotBlank()) listOf(item.displayArtist) else emptyList(),
                album = item.displayAlbum,
                coverUrl = item.displayCover,
                durationSeconds = 0,
                url = item.url,
                source = CatalogSource.YouTube,
                previewUrl = "",
                year = "",
                raw = "",
            )
            remotePlayback.play(
                listOf(remote),
                0,
                PlaybackContext(PlaybackContextType.Playlist, playlistName.orEmpty(), playlistName.orEmpty())
            )
        }
    }

    fun addSuggestedSong(item: PlaylistSuggestionItemDto) {
        val name = playlistName ?: return
        val id = item.displayId.ifBlank { item.displayTitle }
        if (mutableAddingSuggestionIds.value.contains(id) || mutableAddedSuggestionIds.value.contains(id)) return
        mutableAddingSuggestionIds.update { it + id }
        viewModelScope.launch {
            try {
                val ok = if (item.inLibrary && item.trackId.isNotBlank()) {
                    library.addTrackToPlaylist(name, item.trackId)
                } else {
                    library.addSuggestionToPlaylist(name, item)
                }
                if (ok) {
                    mutableAddedSuggestionIds.update { it + id }
                }
            } finally {
                mutableAddingSuggestionIds.update { it - id }
            }
        }
    }

    fun addTrackToPlaylist(targetPlaylist: String, track: Track) {
        viewModelScope.launch { library.addTrackToPlaylist(targetPlaylist, track.id) }
    }

    fun removeTrackFromPlaylist(track: Track) {
        val name = playlistName ?: return
        viewModelScope.launch { library.removeTrackFromPlaylist(name, track.id) }
    }

    fun toggleVisibility() {
        val p = uiState.value.playlist ?: return
        viewModelScope.launch { library.setPlaylistVisibility(p.name, !p.isPublic) }
    }

    fun clonePlaylist(newName: String) {
        val p = uiState.value.playlist ?: return
        viewModelScope.launch { library.clonePlaylist(p.name, newName.trim()) }
    }

    fun toggleHidden() {
        val p = uiState.value.playlist ?: return
        viewModelScope.launch { library.setPlaylistHidden(p.name, !p.hidden) }
    }

    fun renamePlaylist(newName: String) {
        val p = uiState.value.playlist ?: return
        viewModelScope.launch { library.renamePlaylist(p.name, newName.trim()) }
    }

    fun deletePlaylist(onDeleted: () -> Unit) {
        val p = uiState.value.playlist ?: return
        viewModelScope.launch {
            if (library.deletePlaylist(p.name)) {
                onDeleted()
            }
        }
    }

    fun loadUsers() {
        viewModelScope.launch { mutableUsers.value = library.listUsers() }
    }

    fun changeOwner(ownerId: Int) {
        val p = uiState.value.playlist ?: return
        viewModelScope.launch { library.changePlaylistOwner(p.name, ownerId) }
    }

    fun shareCollection(onShareUrl: (String) -> Unit) {
        val state = uiState.value
        viewModelScope.launch {
            val share = when (state.kind) {
                CollectionKind.Playlist -> library.createShare(playlist = playlistName, title = state.title)
                CollectionKind.Album -> state.tracks.firstOrNull()?.let {
                    library.createShare(trackId = it.id, title = state.title)
                }
                CollectionKind.Liked -> null
            }
            val url = share?.url.orEmpty()
            if (url.isNotBlank()) onShareUrl(url)
        }
    }

    fun shareTrack(track: Track, onShareUrl: (String) -> Unit) {
        viewModelScope.launch {
            val url = library.createShare(trackId = track.id, title = track.displayTitle)?.url.orEmpty()
            if (url.isNotBlank()) onShareUrl(url)
        }
    }

    private fun context(title: String) = when (kind) {
        CollectionKind.Album -> PlaybackContext(PlaybackContextType.Album, albumId.orEmpty(), title)
        CollectionKind.Playlist -> PlaybackContext(PlaybackContextType.Playlist, playlistName.orEmpty(), title)
        CollectionKind.Liked -> PlaybackContext(PlaybackContextType.Liked, "", title)
    }

    private companion object {
        const val STOP_TIMEOUT_MS = 5_000L
    }
}
