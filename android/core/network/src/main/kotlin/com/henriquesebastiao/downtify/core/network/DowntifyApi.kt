package com.henriquesebastiao.downtify.core.network

import com.henriquesebastiao.downtify.core.network.dto.ApplyCoverRequest
import com.henriquesebastiao.downtify.core.network.dto.AuthStatusDto
import com.henriquesebastiao.downtify.core.network.dto.BlockArtistRequest
import com.henriquesebastiao.downtify.core.network.dto.CoverSearchResponseDto
import com.henriquesebastiao.downtify.core.network.dto.CreatePlaylistRequest
import com.henriquesebastiao.downtify.core.network.dto.CreateShareRequest
import com.henriquesebastiao.downtify.core.network.dto.DiscoverArtistsDto
import com.henriquesebastiao.downtify.core.network.dto.DiscoverCollectionsDto
import com.henriquesebastiao.downtify.core.network.dto.DiscoverRequest
import com.henriquesebastiao.downtify.core.network.dto.LibraryPageDto
import com.henriquesebastiao.downtify.core.network.dto.LikeRequest
import com.henriquesebastiao.downtify.core.network.dto.LikeResponse
import com.henriquesebastiao.downtify.core.network.dto.LikesDto
import com.henriquesebastiao.downtify.core.network.dto.ListenRequest
import com.henriquesebastiao.downtify.core.network.dto.ListeningStatsDto
import com.henriquesebastiao.downtify.core.network.dto.LoudnessDto
import com.henriquesebastiao.downtify.core.network.dto.LyricsDto
import com.henriquesebastiao.downtify.core.network.dto.MeResponse
import com.henriquesebastiao.downtify.core.network.dto.MobileUserDto
import com.henriquesebastiao.downtify.core.network.dto.PairRequest
import com.henriquesebastiao.downtify.core.network.dto.PairResponse
import com.henriquesebastiao.downtify.core.network.dto.PlaybackActivityRequest
import com.henriquesebastiao.downtify.core.network.dto.PlaylistCloneRequest
import com.henriquesebastiao.downtify.core.network.dto.PlaylistCreatedDto
import com.henriquesebastiao.downtify.core.network.dto.PlaylistDto
import com.henriquesebastiao.downtify.core.network.dto.PlaylistFavoriteRequest
import com.henriquesebastiao.downtify.core.network.dto.PlaylistFavoriteResponse
import com.henriquesebastiao.downtify.core.network.dto.PlaylistHideRequest
import com.henriquesebastiao.downtify.core.network.dto.PlaylistOwnerRequest
import com.henriquesebastiao.downtify.core.network.dto.PlaylistRenameRequest
import com.henriquesebastiao.downtify.core.network.dto.PlaylistSuggestionsResponseDto
import com.henriquesebastiao.downtify.core.network.dto.PlaylistTrackMutationRequest
import com.henriquesebastiao.downtify.core.network.dto.PlaylistVisibilityRequest
import com.henriquesebastiao.downtify.core.network.dto.PodcastEpisodeDto
import com.henriquesebastiao.downtify.core.network.dto.PodcastEpisodesDto
import com.henriquesebastiao.downtify.core.network.dto.PodcastPlaybackRequest
import com.henriquesebastiao.downtify.core.network.dto.PodcastShowDto
import com.henriquesebastiao.downtify.core.network.dto.ServerInfoDto
import com.henriquesebastiao.downtify.core.network.dto.ShareDto
import com.henriquesebastiao.downtify.core.network.dto.SignInRequest
import com.henriquesebastiao.downtify.core.network.dto.SignUpRequest
import com.henriquesebastiao.downtify.core.network.dto.SignUpResponse
import com.henriquesebastiao.downtify.core.network.dto.SuggestedMixDto
import com.henriquesebastiao.downtify.core.network.dto.UnlockCoverRequest
import com.henriquesebastiao.downtify.core.network.dto.UpdateMeRequest
import com.henriquesebastiao.downtify.core.network.dto.UpgradeStartRequest
import com.henriquesebastiao.downtify.core.network.dto.UpgradeStatusDto
import com.henriquesebastiao.downtify.core.network.dto.UserPreferencesDto
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * The server routes this app uses — only those in the mobile client contract
 * (`~/git/downtify/docs/mobile-client-contract.md`). Paths are relative so a
 * base URL with a path (a reverse proxy) works.
 */
interface DowntifyApi {
    @GET("api/server/info")
    suspend fun serverInfo(): ServerInfoDto

    @GET("api/auth/status")
    suspend fun authStatus(): AuthStatusDto

    @POST("api/auth/pair")
    suspend fun pair(@Body body: PairRequest): PairResponse

    @POST("api/auth/token")
    suspend fun signIn(@Body body: SignInRequest): PairResponse

    @POST("api/auth/signup")
    suspend fun signUp(@Body body: SignUpRequest): SignUpResponse

    @GET("api/v1/library")
    suspend fun library(
        @Query("since") since: Long,
        @Query("refresh") refresh: Boolean? = null,
    ): Response<LibraryPageDto>

    @GET("api/v1/playlists")
    suspend fun playlists(@Query("include_hidden") includeHidden: Boolean = false): List<PlaylistDto>

    @PUT("api/v1/playlists/favorite")
    suspend fun setPlaylistFavorite(@Body body: PlaylistFavoriteRequest): PlaylistFavoriteResponse

    @POST("api/v1/playlists")
    suspend fun createPlaylist(@Body body: CreatePlaylistRequest): PlaylistCreatedDto

    @DELETE("api/v1/playlists/{name}")
    suspend fun deletePlaylist(@Path("name") name: String): JsonObject

    @PUT("api/v1/playlists/{name}/visibility")
    suspend fun setPlaylistVisibility(@Path("name") name: String, @Body body: PlaylistVisibilityRequest): JsonObject

    @POST("api/v1/playlists/{name}/clone")
    suspend fun clonePlaylist(@Path("name") name: String, @Body body: PlaylistCloneRequest = PlaylistCloneRequest()): JsonObject

    @PUT("api/v1/playlists/{name}/hide")
    suspend fun setPlaylistHidden(@Path("name") name: String, @Body body: PlaylistHideRequest): JsonObject

    @PUT("api/v1/playlists/{name}/rename")
    suspend fun renamePlaylist(@Path("name") name: String, @Body body: PlaylistRenameRequest): JsonObject

    @PUT("api/v1/playlists/{name}/owner")
    suspend fun changePlaylistOwner(@Path("name") name: String, @Body body: PlaylistOwnerRequest): JsonObject

    @POST("api/v1/playlists/{name}/tracks")
    suspend fun addPlaylistTrack(@Path("name") name: String, @Body body: PlaylistTrackMutationRequest): JsonObject

    @POST("api/v1/playlists/{name}/tracks/remove")
    suspend fun removePlaylistTrack(@Path("name") name: String, @Body body: PlaylistTrackMutationRequest): JsonObject

    @GET("api/v1/playlists/{name}/suggestions")
    suspend fun playlistSuggestions(@Path("name") name: String, @Query("limit") limit: Int = 8): PlaylistSuggestionsResponseDto

    @GET("api/v1/suggested-mix")
    suspend fun suggestedMix(): SuggestedMixDto

    @POST("api/v1/shares")
    suspend fun createShare(@Body body: CreateShareRequest): ShareDto

    @GET("api/v1/stats")
    suspend fun myStats(@Query("days") days: Int = 30): ListeningStatsDto

    @DELETE("api/v1/stats")
    suspend fun clearMyStats(): JsonObject

    @PATCH("api/v1/me")
    suspend fun updateMe(@Body body: UpdateMeRequest): JsonObject

    @PUT("api/v1/me/preferences")
    suspend fun setMyPreferences(@Body body: UserPreferencesDto): JsonObject

    @GET("api/v1/users")
    suspend fun listUsers(): List<MobileUserDto>

    @GET("api/v1/covers/search")
    suspend fun searchCovers(
        @Query("artist") artist: String = "",
        @Query("title") title: String = "",
        @Query("track") track: String? = null,
        @Query("query") query: String? = null,
        @Query("track_id") trackId: String? = null,
    ): CoverSearchResponseDto

    @POST("api/v1/covers/apply")
    suspend fun applyCover(@Body body: ApplyCoverRequest): JsonObject

    @POST("api/v1/covers/unlock")
    suspend fun unlockCover(@Body body: UnlockCoverRequest): JsonObject

    @GET("api/v1/upgrade")
    suspend fun upgradeStatus(): UpgradeStatusDto

    @POST("api/v1/upgrade/scan")
    suspend fun upgradeScan(): UpgradeStatusDto

    @POST("api/v1/upgrade/start")
    suspend fun upgradeStart(@Body body: UpgradeStartRequest = UpgradeStartRequest()): UpgradeStatusDto

    @GET("api/v1/likes")
    suspend fun likes(): LikesDto

    @PUT("api/v1/likes")
    suspend fun setLike(@Body body: LikeRequest): LikeResponse

    @GET("api/v1/tracks/{id}/lyrics")
    suspend fun lyrics(
        @Path("id") trackId: String,
        @Query("lang") lang: String? = null,
    ): LyricsDto

    @GET("api/v1/tracks/{id}/loudness")
    suspend fun loudness(@Path("id") trackId: String): LoudnessDto

    @GET("api/me")
    suspend fun me(): MeResponse

    @POST("api/activity/playback")
    suspend fun reportPlayback(@Body body: PlaybackActivityRequest): Response<Unit>

    @POST("api/discover/listens")
    suspend fun reportListen(@Body body: ListenRequest): Response<Unit>
}
