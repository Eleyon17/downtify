package com.henriquesebastiao.downtify.core.network.dto

import com.henriquesebastiao.downtify.core.model.Capabilities
import com.henriquesebastiao.downtify.core.model.LibraryPage
import com.henriquesebastiao.downtify.core.model.LrcParser
import com.henriquesebastiao.downtify.core.model.Lyrics
import com.henriquesebastiao.downtify.core.model.Playlist
import com.henriquesebastiao.downtify.core.model.ServerInfo
import com.henriquesebastiao.downtify.core.model.Track
import com.henriquesebastiao.downtify.core.model.Transcoding
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// Wire shapes of the mobile client contract (api_version 1). Unknown fields are
// ignored and missing ones take the defaults below, so additions on the server
// side never break the app.

@Serializable
data class ServerInfoDto(
    @SerialName("server_id") val serverId: String = "",
    val name: String = "",
    val product: String = "",
    val version: String = "",
    @SerialName("api_version") val apiVersion: Int = 0,
    @SerialName("require_sign_in") val requireSignIn: Boolean = false,
    val capabilities: CapabilitiesDto = CapabilitiesDto(),
) {
    fun toModel() = ServerInfo(serverId, name, product, version, apiVersion, requireSignIn, capabilities.toModel())

    companion object {
        fun from(info: ServerInfo) = ServerInfoDto(
            serverId = info.serverId,
            name = info.name,
            product = info.product,
            version = info.version,
            apiVersion = info.apiVersion,
            requireSignIn = info.requireSignIn,
            capabilities = info.capabilities.let { c ->
                CapabilitiesDto(
                    transcoding = TranscodingDto(
                        c.transcoding.available,
                        c.transcoding.formats,
                        c.transcoding.bitrates,
                    ),
                    signedUrls = c.signedUrls,
                    pairing = c.pairing,
                    podcasts = c.podcasts,
                    discover = c.discover,
                    lyrics = c.lyrics,
                    librarySync = c.librarySync,
                    passwordSignIn = c.passwordSignIn,
                )
            },
        )
    }
}

@Serializable
data class CapabilitiesDto(
    val transcoding: TranscodingDto = TranscodingDto(),
    @SerialName("signed_urls") val signedUrls: Boolean = false,
    val pairing: Boolean = false,
    val podcasts: Boolean = false,
    val discover: Boolean = false,
    val lyrics: Boolean = false,
    @SerialName("library_sync") val librarySync: Boolean = false,
    /** Missing on servers older than `POST /api/auth/token`, and false while sign-in is turned off. */
    @SerialName("password_sign_in") val passwordSignIn: Boolean = false,
) {
    fun toModel() = Capabilities(
        transcoding.toModel(),
        signedUrls,
        pairing,
        podcasts,
        discover,
        lyrics,
        librarySync,
        passwordSignIn,
    )
}

@Serializable
data class TranscodingDto(
    val available: Boolean = false,
    val formats: List<String> = emptyList(),
    val bitrates: List<Int> = emptyList(),
) {
    fun toModel() = Transcoding(available, formats, bitrates)
}

@Serializable
data class PairRequest(
    val code: String,
    @SerialName("device_name") val deviceName: String,
    val platform: String = "android",
)

/** `POST /api/auth/token`: sign in with the account's password instead of a pairing code. */
@Serializable
data class SignInRequest(
    val username: String,
    val password: String,
    @SerialName("device_name") val deviceName: String,
    val platform: String = "android",
)

/** `POST /api/auth/signup`: register a new user account and obtain a device token. */
@Serializable
data class SignUpRequest(
    val username: String,
    val password: String,
    val email: String? = null,
    @SerialName("display_name") val displayName: String = "",
    @SerialName("device_name") val deviceName: String = "",
    val platform: String = "android",
)

@Serializable
data class SignUpResponse(
    @SerialName("signed_in") val signedIn: Boolean = false,
    val token: String = "",
    val device: DeviceDto = DeviceDto(),
    val server: PairedServerDto = PairedServerDto(),
    val user: UserDto? = null,
)

/** `POST /api/auth/pair` and `POST /api/auth/token`. */
@Serializable
data class PairResponse(
    val token: String,
    val device: DeviceDto,
    val server: PairedServerDto = PairedServerDto(),
    /** Who showed the code or signed in (servers with accounts, 3.2+); the device belongs to them. */
    val user: UserDto? = null,
)

@Serializable
data class UserDto(
    val id: Int = 0,
    val username: String = "",
    val role: String = "",
    val email: String = "",
    @SerialName("display_name") val displayName: String = "",
)

/** `POST /api/stream/prefetch`: warm the server's stream cache for a video. */
@Serializable
data class PrefetchRequestDto(@SerialName("video_id") val videoId: String)

/** `GET /api/me`. */
@Serializable
data class MeResponse(
    val user: UserDto? = null,
    val preferences: UserPreferencesDto = UserPreferencesDto(),
)

@Serializable
data class UserPreferencesDto(
    @SerialName("hide_public_playlists_by_default") val hidePublicPlaylistsByDefault: Boolean = false,
)

/** `POST /api/activity/playback`: what this player is doing, for the admins' Activity page. */
@Serializable
data class PlaybackActivityRequest(
    val player: String,
    val state: String,
    val track: ActivityTrackDto = ActivityTrackDto(),
    val position: Int = 0,
    val listened: Double = 0.0,
    val skipped: Boolean = false,
)

/** Empty (`{}`) with `stopped`. */
@Serializable
data class ActivityTrackDto(
    @SerialName("track_id") val trackId: String? = null,
    /** A podcast episode's library path, for what has no track id. */
    val file: String? = null,
    val title: String? = null,
    val artist: String? = null,
    val album: String? = null,
    val duration: Int? = null,
)

@Serializable
data class DeviceDto(val id: String = "", val name: String = "")

@Serializable
data class PairedServerDto(@SerialName("server_id") val serverId: String = "", val name: String = "")

@Serializable
data class AuthStatusDto(
    @SerialName("require_sign_in") val requireSignIn: Boolean = false,
    @SerialName("signed_in") val signedIn: Boolean = false,
    val via: String? = null,
    val device: DeviceDto? = null,
)

@Serializable
data class LibraryPageDto(
    val cursor: Long = 0,
    val full: Boolean = false,
    val tracks: List<TrackDto> = emptyList(),
    val deleted: List<String> = emptyList(),
) {
    fun toModel() = LibraryPage(cursor, full, tracks.map { it.toModel() }, deleted)
}

@Serializable
data class TrackDto(
    val id: String,
    val file: String = "",
    val title: String = "",
    val artist: String = "",
    val artists: List<String> = emptyList(),
    val album: String = "",
    @SerialName("album_artist") val albumArtist: String = "",
    @SerialName("album_id") val albumId: String = "",
    @SerialName("artist_id") val artistId: String = "",
    @SerialName("track_number") val trackNumber: Int = 0,
    val year: String = "",
    val duration: Double = 0.0,
    val codec: String = "",
    val bitrate: Int = 0,
    @SerialName("sample_rate") val sampleRate: Int = 0,
    val channels: Int = 0,
    val size: Long = 0,
    val added: Long = 0,
    @SerialName("has_cover") val hasCover: Boolean = false,
    val playlists: List<String> = emptyList(),
) {
    fun toModel() = Track(
        id = id,
        file = file,
        title = title,
        artist = artist,
        artists = artists,
        album = album,
        albumArtist = albumArtist,
        albumId = albumId,
        artistId = artistId,
        trackNumber = trackNumber,
        year = year,
        duration = duration,
        codec = codec,
        bitrate = bitrate,
        sampleRate = sampleRate,
        channels = channels,
        size = size,
        added = added,
        hasCover = hasCover,
        playlists = playlists,
    )
}

@Serializable
data class PlaylistDto(
    val name: String,
    val liked: Boolean = false,
    val count: Int = 0,
    val cover: String = "",
    @SerialName("track_ids") val trackIds: List<String> = emptyList(),
    val favorite: Boolean? = null,
    @SerialName("display_name") val displayName: String = "",
    val manual: Boolean = false,
    val public: Boolean = false,
    val monitored: Boolean = false,
    val owner: String = "",
    @SerialName("owner_id") val ownerId: Int = 0,
    @SerialName("is_owner") val isOwner: Boolean = false,
    @SerialName("can_edit") val canEdit: Boolean = false,
    @SerialName("can_change_owner") val canChangeOwner: Boolean = false,
    val hidden: Boolean = false,
) {
    fun toModel() = Playlist(
        name = name,
        liked = liked,
        cover = cover,
        trackIds = trackIds,
        favorite = favorite == true,
        displayName = displayName,
        favoriteSupported = favorite != null,
        manual = manual,
        isPublic = public,
        monitored = monitored,
        owner = owner,
        ownerId = ownerId,
        isOwner = isOwner,
        canEdit = canEdit,
        canChangeOwner = canChangeOwner,
        hidden = hidden,
    )
}

@Serializable
data class PlaylistFavoriteRequest(val name: String, val favorite: Boolean)

@Serializable
data class PlaylistFavoriteResponse(val name: String = "", val favorite: Boolean = false)

@Serializable
data class LikesDto(@SerialName("track_ids") val trackIds: List<String> = emptyList())

@Serializable
data class LikeRequest(@SerialName("track_id") val trackId: String, val liked: Boolean)

@Serializable
data class LikeResponse(@SerialName("track_id") val trackId: String = "", val liked: Boolean = false)

@Serializable
data class LyricsDto(
    val synced: String = "",
    val plain: String = "",
    @SerialName("translated_synced") val translatedSynced: String = "",
    @SerialName("translated_plain") val translatedPlain: String = "",
    @SerialName("target_lang") val targetLang: String = "",
) {
    fun toModel(): Lyrics {
        val primarySynced = if (synced.isBlank()) emptyList() else LrcParser.parse(synced)
        val transSynced = if (translatedSynced.isBlank()) emptyList() else LrcParser.parse(translatedSynced)
        val mergedSynced = LrcParser.mergeTranslations(primarySynced, transSynced)
        return Lyrics(
            synced = mergedSynced,
            plain = plain,
            translatedSynced = transSynced,
            translatedPlain = translatedPlain,
            targetLang = targetLang,
        )
    }
}

@Serializable
data class ListenRequest(
    @SerialName("track_id") val trackId: String,
    @SerialName("play_id") val playId: String,
    /** ISO 8601, UTC. */
    @SerialName("played_at") val playedAt: String,
)

@Serializable
data class SuggestedMixArtistDto(
    val name: String = "",
    @SerialName("cover_file") val coverFile: String = "",
    val weight: Double = 0.0,
)

@Serializable
data class SuggestedMixTrackDto(
    val file: String = "",
    @SerialName("track_id") val trackId: String = "",
    val title: String = "",
    val artist: String = "",
    val album: String = "",
    val duration: Double = 0.0,
    @SerialName("has_cover") val hasCover: Boolean = false,
)

@Serializable
data class SuggestedMixDto(
    val title: String = "Suggested Mix",
    val subtitle: String = "",
    @SerialName("top_artists") val topArtists: List<SuggestedMixArtistDto> = emptyList(),
    val tracks: List<SuggestedMixTrackDto> = emptyList(),
    @SerialName("track_ids") val trackIds: List<String> = emptyList(),
)

@Serializable
data class CreatePlaylistRequest(
    val name: String,
    val public: Boolean = false,
)

@Serializable
data class PlaylistCreatedDto(
    val name: String = "",
    val public: Boolean = false,
    val manual: Boolean = true,
)

@Serializable
data class PlaylistVisibilityRequest(val public: Boolean)

@Serializable
data class PlaylistCloneRequest(@SerialName("new_name") val newName: String = "")

@Serializable
data class PlaylistHideRequest(val hidden: Boolean)

@Serializable
data class PlaylistRenameRequest(@SerialName("new_name") val newName: String)

@Serializable
data class PlaylistOwnerRequest(@SerialName("owner_id") val ownerId: Int)

@Serializable
data class PlaylistTrackMutationRequest(
    @SerialName("track_id") val trackId: String? = null,
    val file: String? = null,
)

@Serializable
data class PlaylistSuggestionItemDto(
    @SerialName("video_id") val videoId: String = "",
    val title: String = "",
    val artist: String = "",
    val album: String = "",
    val duration: String = "",
    val thumbnail: String = "",
    val url: String = "",
    @SerialName("in_library") val inLibrary: Boolean = false,
    @SerialName("local_file") val localFile: String = "",
    @SerialName("track_id") val trackId: String = "",
)

@Serializable
data class PlaylistSuggestionsResponseDto(
    val playlist: String = "",
    val suggestions: List<PlaylistSuggestionItemDto> = emptyList(),
)

@Serializable
data class CreateShareRequest(
    val kind: String = "",
    @SerialName("track_id") val trackId: String? = null,
    val playlist: String? = null,
    val target: String? = null,
    val title: String? = null,
)

@Serializable
data class ShareDto(
    val id: String = "",
    val kind: String = "",
    val target: String = "",
    val title: String = "",
    val url: String = "",
)

@Serializable
data class ListeningStatsTotalsDto(
    val plays: Int = 0,
    val hours: Double = 0.0,
    val seconds: Int = 0,
    @SerialName("unique_tracks") val uniqueTracks: Int = 0,
    @SerialName("unique_artists") val uniqueArtists: Int = 0,
    @SerialName("unique_albums") val uniqueAlbums: Int = 0,
    val skips: Int = 0,
)

@Serializable
data class ListeningStatsArtistDto(
    val artist: String = "",
    val plays: Int = 0,
    val seconds: Int = 0,
    val hours: Double = 0.0,
    @SerialName("cover_file") val coverFile: String? = null,
)

@Serializable
data class ListeningStatsTrackDto(
    val title: String = "",
    val artist: String = "",
    val album: String = "",
    val file: String? = null,
    val plays: Int = 0,
    val seconds: Int = 0,
    @SerialName("has_cover") val hasCover: Boolean = false,
)

@Serializable
data class ListeningStatsGenreDto(
    val genre: String = "",
    val plays: Int = 0,
    val share: Double = 0.0,
)

@Serializable
data class ListeningStatsDto(
    @SerialName("window_days") val windowDays: Int = 30,
    val totals: ListeningStatsTotalsDto = ListeningStatsTotalsDto(),
    val lifetime: ListeningStatsTotalsDto = ListeningStatsTotalsDto(),
    @SerialName("top_artists") val topArtists: List<ListeningStatsArtistDto> = emptyList(),
    @SerialName("top_tracks") val topTracks: List<ListeningStatsTrackDto> = emptyList(),
    @SerialName("top_genres") val topGenres: List<ListeningStatsGenreDto> = emptyList(),
)

@Serializable
data class UpdateMeRequest(
    val username: String? = null,
    val email: String? = null,
    @SerialName("display_name") val displayName: String? = null,
)

@Serializable
data class MobileUserDto(
    val id: Int = 0,
    val username: String = "",
    @SerialName("display_name") val displayName: String = "",
    val role: String = "user",
)

@Serializable
data class CoverCandidateDto(
    val source: String = "",
    val title: String = "",
    val artist: String = "",
    val year: String = "",
    val url: String = "",
    @SerialName("thumb_url") val thumbUrl: String = "",
)

@Serializable
data class CoverSearchResponseDto(
    val candidates: List<CoverCandidateDto> = emptyList(),
    @SerialName("cover_locked") val coverLocked: Boolean = false,
)

@Serializable
data class ApplyCoverRequest(
    @SerialName("track_id") val trackId: String? = null,
    val file: String? = null,
    val artist: String = "",
    val album: String = "",
    val url: String = "",
    val scope: String = "album",
    val lock: Boolean = true,
)

@Serializable
data class UnlockCoverRequest(
    @SerialName("track_id") val trackId: String? = null,
    val file: String? = null,
    val artist: String = "",
    val album: String = "",
    val scope: String = "album",
)

@Serializable
data class UpgradeStatusDto(
    val running: Boolean = false,
    val phase: String = "idle",
    val total: Int = 0,
    val processed: Int = 0,
    val upgraded: Int = 0,
    val skipped: Int = 0,
    val failed: Int = 0,
    val current: String = "",
    @SerialName("candidates_count") val candidatesCount: Int = 0,
)

@Serializable
data class UpgradeStartRequest(
    @SerialName("target_format") val targetFormat: String = "mp3",
    @SerialName("min_bitrate") val minBitrate: Int = 256,
)

@Serializable
data class ArtistPopularSongDto(
    val title: String = "",
    val name: String = "",
    val artist: String = "",
    val album: String = "",
    @SerialName("album_name") val albumName: String = "",
    val duration: Double = 0.0,
    val cover: String = "",
    @SerialName("cover_url") val coverUrl: String = "",
    @SerialName("song_id") val songId: String = "",
    @SerialName("video_id") val videoId: String = "",
    @SerialName("in_library") val inLibrary: Boolean = false,
    @SerialName("local_file") val localFile: String? = null,
    @SerialName("local_title") val localTitle: String? = null,
    @SerialName("local_track_id") val localTrackId: String? = null,
) {
    val displayTitle: String get() = title.ifBlank { name }
    val displayAlbum: String get() = album.ifBlank { albumName }
    val displayCover: String get() = cover.ifBlank { coverUrl }
    val streamVideoId: String get() = songId.ifBlank { videoId }
}

@Serializable
data class ArtistTopAlbumDto(
    val title: String = "",
    val name: String = "",
    val year: String = "",
    val cover: String = "",
    @SerialName("cover_url") val coverUrl: String = "",
    @SerialName("record_type") val recordType: String = "album",
    @SerialName("in_library") val inLibrary: Boolean = false,
    @SerialName("local_track_count") val localTrackCount: Int = 0,
    @SerialName("browse_id") val browseId: String = "",
    @SerialName("album_id") val albumId: String = "",
    @SerialName("local_album_id") val localAlbumId: String? = null,
) {
    val displayTitle: String get() = title.ifBlank { name }
    val displayCover: String get() = cover.ifBlank { coverUrl }
}

@Serializable
data class ArtistSimilarDto(
    val name: String = "",
    val image: String = "",
    @SerialName("in_library") val inLibrary: Boolean = false,
)

@Serializable
data class ArtistOverviewDto(
    val artist: String = "",
    val name: String = "",
    val bio: String = "",
    @SerialName("bio_source") val bioSource: String = "",
    @SerialName("bio_url") val bioUrl: String = "",
    val image: String = "",
    @SerialName("cover_url") val coverUrl: String = "",
    val fans: Int = 0,
    @SerialName("popular_songs") val popularSongs: List<ArtistPopularSongDto> = emptyList(),
    @SerialName("top_songs") val topSongs: List<ArtistPopularSongDto> = emptyList(),
    @SerialName("top_albums") val topAlbums: List<ArtistTopAlbumDto> = emptyList(),
    @SerialName("similar_artists") val similarArtists: List<ArtistSimilarDto> = emptyList(),
) {
    val displayArtist: String get() = artist.ifBlank { name }
    val displayImage: String get() = image.ifBlank { coverUrl }
    val allSongs: List<ArtistPopularSongDto> get() = popularSongs.ifEmpty { topSongs }
}

@Serializable
data class UpdateCheckDto(
    val current: String = "",
    val latest: String = "",
    @SerialName("update_available") val updateAvailable: Boolean = false,
    val url: String = "",
    @SerialName("apk_url") val apkUrl: String? = null,
    @SerialName("apk_direct_url") val apkDirectUrl: String? = null,
)
