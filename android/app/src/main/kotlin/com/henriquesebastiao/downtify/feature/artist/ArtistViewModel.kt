package com.henriquesebastiao.downtify.feature.artist

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.henriquesebastiao.downtify.core.data.library.LibraryRepository
import com.henriquesebastiao.downtify.core.model.Artist
import com.henriquesebastiao.downtify.core.model.PlaybackContext
import com.henriquesebastiao.downtify.core.model.PlaybackContextType
import com.henriquesebastiao.downtify.core.model.Track
import com.henriquesebastiao.downtify.core.player.PlayerController
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class ArtistUiState(
    val loading: Boolean = true,
    val artist: Artist? = null,
    /** Every song, album by album (newest album first), in track order. */
    val songs: List<Track> = emptyList(),
    val currentTrackId: String? = null,
    val isPlaying: Boolean = false,
    val isCurrentContext: Boolean = false,
    val likedIds: Set<String> = emptySet(),
)

@HiltViewModel
class ArtistViewModel @Inject constructor(
    savedState: SavedStateHandle,
    private val library: LibraryRepository,
    private val player: PlayerController,
) : ViewModel() {
    private val artistId: String = savedState["artistId"] ?: ""

    val uiState: StateFlow<ArtistUiState> = combine(library.library, library.likedIds, player.nowPlaying) {
            snapshot,
            liked,
            playing,
        ->
        val artist = snapshot?.artistsById?.get(artistId)
        val inAlbums = artist?.albums.orEmpty().flatMap { it.tracks }
        val loose = artist?.tracks.orEmpty().filter { it.albumId.isEmpty() }
        ArtistUiState(
            loading = snapshot == null,
            artist = artist,
            songs = inAlbums + loose,
            currentTrackId = playing.trackId,
            isPlaying = playing.isPlaying,
            isCurrentContext =
                playing.context?.let { it.type == PlaybackContextType.Artist && it.refId == artistId } == true,
            likedIds = liked.toSet(),
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(STOP_TIMEOUT_MS), ArtistUiState())

    fun play(index: Int, shuffle: Boolean = false) {
        val state = uiState.value
        val artist = state.artist ?: return
        player.play(state.songs, index, PlaybackContext(PlaybackContextType.Artist, artist.id, artist.name), shuffle)
    }

    fun playOrPause() {
        if (uiState.value.isCurrentContext) player.togglePlayPause() else play(0)
    }

    fun shuffle() = play(0, shuffle = true)

    fun addToQueue(track: Track) = player.addToQueue(track)

    fun toggleLike(track: Track) {
        viewModelScope.launch { library.setLiked(track.id, track.id !in uiState.value.likedIds) }
    }

    private companion object {
        const val STOP_TIMEOUT_MS = 5_000L
    }
}
