package com.henriquesebastiao.downtify.core.model

/** A library artist as `POST /api/discover` wants it: how much of them the user has and likes. */
data class DiscoverSeed(val name: String, val tracks: Int, val liked: Int)

/** An artist the library doesn't have, suggested from the ones it does. */
data class DiscoverArtist(
    val name: String,
    /** Deezer's photo, or blank. */
    val pictureUrl: String,
    /** Up to three library artists that suggested it, the biggest contributor first. */
    val because: List<String>,
    /** Its Spotify page, when the server found it by exact name (from the collections answer). */
    val spotifyUrl: String,
)

/** An album or playlist built on the suggested artists. Opens like a pasted Spotify link. */
data class DiscoverAlbum(
    val name: String,
    val artist: String,
    val year: String,
    val coverUrl: String,
    val url: String,
    /** "similar" (by a suggested artist) or "more_from" (another from an artist you already have). */
    val reason: String,
    val because: List<String>,
)

data class DiscoverPlaylist(
    val name: String,
    val owner: String,
    val coverUrl: String,
    val url: String,
    /** "radio" (around a library artist) or "this_is" (a suggested artist). */
    val reason: String,
    val artist: String,
)

data class DiscoverArtists(
    val artists: List<DiscoverArtist>,
    /** True when Deezer couldn't be asked for some artists: the list is shorter than usual, not an error. */
    val partial: Boolean,
)

data class DiscoverCollections(
    val albums: List<DiscoverAlbum>,
    val moreAlbums: List<DiscoverAlbum>,
    val playlists: List<DiscoverPlaylist>,
    /** Suggested artist name → its Spotify page. */
    val artistUrls: Map<String, String>,
    val partial: Boolean,
)

object DiscoverInput {
    /**
     * The library's artists as the server weighs them: songs in the library and,
     * of those, songs liked. Grouped by `artist_id` like the Library's Artists tab.
     */
    fun seeds(artists: List<Artist>, likedTrackIds: Set<String>): List<DiscoverSeed> = artists
        .filter { it.name.isNotBlank() }
        .map { artist ->
            DiscoverSeed(
                name = artist.name,
                tracks = artist.tracks.size,
                liked = artist.tracks.count { it.id in likedTrackIds },
            )
        }

    /** What an album already in the library is called for the server to leave it out: artist and title. */
    fun albumKeys(albums: List<Album>): List<Pair<String, String>> = albums.map { it.artist to it.title }

    /** The first suggestions get a Spotify link from the collections answer, matched by exact name. */
    fun withLinks(artists: List<DiscoverArtist>, urls: Map<String, String>): List<DiscoverArtist> =
        artists.map { it.copy(spotifyUrl = urls[it.name].orEmpty()) }

    /**
     * What to search for when a suggestion is opened: its Spotify page, or —
     * when Spotify didn't find it by that exact name — the name itself.
     */
    fun searchFor(artist: DiscoverArtist): String = artist.spotifyUrl.ifBlank { artist.name }
}
