package com.henriquesebastiao.downtify.core.network.dto

import com.henriquesebastiao.downtify.core.model.DiscoverAlbum
import com.henriquesebastiao.downtify.core.model.DiscoverArtist
import com.henriquesebastiao.downtify.core.model.DiscoverPlaylist
import com.henriquesebastiao.downtify.core.model.DiscoverSeed
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// The web API's Discover objects (`/api/discover…`); lenient like the podcast ones.

@Serializable
data class DiscoverLibraryArtistDto(val name: String, val tracks: Int, val liked: Int)

/** `POST /api/discover` and `POST /api/discover/collections`. */
@Serializable
data class DiscoverRequest(
    val library: List<DiscoverLibraryArtistDto>,
    /** Collections only: albums already in the library (left out of the answer). */
    val albums: List<DiscoverLibraryAlbumDto>? = null,
) {
    companion object {
        fun of(seeds: List<DiscoverSeed>, albums: List<Pair<String, String>>? = null) = DiscoverRequest(
            library = seeds.map { DiscoverLibraryArtistDto(it.name, it.tracks, it.liked) },
            albums = albums?.map { (artist, title) -> DiscoverLibraryAlbumDto(artist, title) },
        )
    }
}

@Serializable
data class DiscoverLibraryAlbumDto(val artist: String, val title: String)

@Serializable
data class DiscoverArtistDto(
    val name: String = "",
    @SerialName("picture_url") val pictureUrl: String? = null,
    val because: List<String> = emptyList(),
) {
    fun toModel() = DiscoverArtist(name, pictureUrl.orEmpty(), because, spotifyUrl = "")
}

@Serializable
data class DiscoverArtistsDto(val artists: List<DiscoverArtistDto> = emptyList(), val partial: Boolean = false)

@Serializable
data class DiscoverAlbumDto(
    val name: String = "",
    val artist: String? = null,
    val year: String? = null,
    @SerialName("cover_url") val coverUrl: String? = null,
    val url: String? = null,
    val reason: String? = null,
    val because: List<String> = emptyList(),
) {
    fun toModel() = DiscoverAlbum(
        name,
        artist.orEmpty(),
        year.orEmpty(),
        coverUrl.orEmpty(),
        url.orEmpty(),
        reason.orEmpty(),
        because,
    )
}

@Serializable
data class DiscoverPlaylistDto(
    val name: String = "",
    val owner: String? = null,
    @SerialName("cover_url") val coverUrl: String? = null,
    val url: String? = null,
    val reason: String? = null,
    val artist: String? = null,
) {
    fun toModel() =
        DiscoverPlaylist(name, owner.orEmpty(), coverUrl.orEmpty(), url.orEmpty(), reason.orEmpty(), artist.orEmpty())
}

@Serializable
data class DiscoverCollectionsDto(
    val albums: List<DiscoverAlbumDto> = emptyList(),
    @SerialName("more_albums") val moreAlbums: List<DiscoverAlbumDto> = emptyList(),
    val playlists: List<DiscoverPlaylistDto> = emptyList(),
    @SerialName("artist_urls") val artistUrls: Map<String, String> = emptyMap(),
    val partial: Boolean = false,
)

@Serializable
data class BlockArtistRequest(val name: String)
