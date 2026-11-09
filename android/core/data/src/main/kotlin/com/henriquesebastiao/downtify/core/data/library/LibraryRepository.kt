package com.henriquesebastiao.downtify.core.data.library

import android.util.Log
import android.util.LruCache
import androidx.room.withTransaction
import com.henriquesebastiao.downtify.core.data.db.DowntifyDatabase
import com.henriquesebastiao.downtify.core.data.db.LikeEntity
import com.henriquesebastiao.downtify.core.data.db.LyricsOffsetEntity
import com.henriquesebastiao.downtify.core.data.db.PlaylistEntity
import com.henriquesebastiao.downtify.core.data.di.ApplicationScope
import com.henriquesebastiao.downtify.core.data.sync.LibraryLocalStore
import com.henriquesebastiao.downtify.core.data.sync.LibraryRemote
import com.henriquesebastiao.downtify.core.data.sync.LibrarySyncer
import com.henriquesebastiao.downtify.core.data.sync.SyncOutcome
import com.henriquesebastiao.downtify.core.model.Lyrics
import com.henriquesebastiao.downtify.core.model.LyricsTiming
import com.henriquesebastiao.downtify.core.model.Playlist
import com.henriquesebastiao.downtify.core.network.ApiFactory
import com.henriquesebastiao.downtify.core.network.DowntifyApi
import com.henriquesebastiao.downtify.core.network.WebApi
import com.henriquesebastiao.downtify.core.network.dto.ApplyCoverRequest
import com.henriquesebastiao.downtify.core.network.dto.ArtistOverviewDto
import com.henriquesebastiao.downtify.core.network.dto.CoverSearchResponseDto
import com.henriquesebastiao.downtify.core.network.dto.CreatePlaylistRequest
import com.henriquesebastiao.downtify.core.network.dto.CreateShareRequest
import com.henriquesebastiao.downtify.core.network.dto.LikeRequest
import com.henriquesebastiao.downtify.core.network.dto.ListeningStatsDto
import com.henriquesebastiao.downtify.core.network.dto.MeResponse
import com.henriquesebastiao.downtify.core.network.dto.MobileUserDto
import com.henriquesebastiao.downtify.core.network.dto.PlaylistCloneRequest
import com.henriquesebastiao.downtify.core.network.dto.PlaylistFavoriteRequest
import com.henriquesebastiao.downtify.core.network.dto.PlaylistHideRequest
import com.henriquesebastiao.downtify.core.network.dto.PlaylistOwnerRequest
import com.henriquesebastiao.downtify.core.network.dto.PlaylistRenameRequest
import com.henriquesebastiao.downtify.core.network.dto.PlaylistSuggestionItemDto
import com.henriquesebastiao.downtify.core.network.dto.PlaylistTrackMutationRequest
import com.henriquesebastiao.downtify.core.network.dto.PlaylistVisibilityRequest
import com.henriquesebastiao.downtify.core.network.dto.ShareDto
import com.henriquesebastiao.downtify.core.network.dto.SuggestedMixDto
import com.henriquesebastiao.downtify.core.network.dto.UnlockCoverRequest
import com.henriquesebastiao.downtify.core.network.dto.UpdateCheckDto
import com.henriquesebastiao.downtify.core.network.dto.UpdateMeRequest
import com.henriquesebastiao.downtify.core.network.dto.UpgradeStartRequest
import com.henriquesebastiao.downtify.core.network.dto.UpgradeStatusDto
import com.henriquesebastiao.downtify.core.network.dto.UserPreferencesDto
import com.henriquesebastiao.downtify.core.network.session.SessionStore
import java.util.Locale
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.jsonPrimitive
import retrofit2.HttpException

private data class PlaylistExtraMeta(
    val manual: Boolean = false,
    val isPublic: Boolean = false,
    val monitored: Boolean = false,
    val owner: String = "",
    val ownerId: Int = 0,
    val isOwner: Boolean = false,
    val canEdit: Boolean = false,
    val canChangeOwner: Boolean = false,
    val hidden: Boolean = false,
)

sealed interface SyncStatus {
    data object Idle : SyncStatus
    data object Syncing : SyncStatus
    data class Failed(val offline: Boolean) : SyncStatus
}

/** The synced library, playlists and likes, and keeping them in step with the server. */
// Server calls here fail soft: any error leaves the local library as it was.
@Suppress("TooGenericExceptionCaught")
@Singleton
class LibraryRepository @Inject constructor(
    private val db: DowntifyDatabase,
    private val store: LibraryLocalStore,
    private val sessions: SessionStore,
    private val apis: ApiFactory,
    @ApplicationScope scope: CoroutineScope,
) {
    /** Null until the database was read once. */
    val library: StateFlow<LibrarySnapshot?> = db.tracks().observeAll()
        .distinctUntilChanged()
        .map { rows -> LibrarySnapshot(rows.map { it.toModel() }) }
        .flowOn(Dispatchers.Default)
        .stateIn(scope, SharingStarted.Eagerly, null)

    private val playlistExtras = MutableStateFlow<Map<String, PlaylistExtraMeta>>(emptyMap())

    val playlists: StateFlow<List<Playlist>> = combine(
        db.playlists().observeAll(),
        playlistExtras,
    ) { rows, extras ->
        rows.map { row ->
            val model = row.toModel()
            val extra = extras[row.name] ?: return@map model
            model.copy(
                manual = extra.manual,
                isPublic = extra.isPublic,
                monitored = extra.monitored,
                owner = extra.owner,
                ownerId = extra.ownerId,
                isOwner = extra.isOwner,
                canEdit = extra.canEdit,
                canChangeOwner = extra.canChangeOwner,
                hidden = extra.hidden,
            )
        }
    }.stateIn(scope, SharingStarted.Eagerly, emptyList())

    /** Liked track ids, most recently liked first. */
    val likedIds: StateFlow<List<String>> = db.likes().observeIds()
        .stateIn(scope, SharingStarted.Eagerly, emptyList())

    private val status = MutableStateFlow<SyncStatus>(SyncStatus.Idle)
    val syncStatus: StateFlow<SyncStatus> = status.asStateFlow()
    private val successful = MutableStateFlow(0L)
    val successfulSync: StateFlow<Long> = successful.asStateFlow()

    private val lyricsCache = LruCache<String, Lyrics>(LYRICS_CACHE_SIZE)

    private fun api(): DowntifyApi? = sessions.current?.let { apis.create(it.baseUrl) }
    private fun webApi(): WebApi? = sessions.current?.let { apis.createWeb(it.baseUrl) }

    /**
     * Pulls the library feed, then playlists and likes. [refresh] asks the server
     * to rescan its folder now (pull to refresh). Returns false when the server
     * couldn't be reached.
     */
    suspend fun sync(refresh: Boolean = false): Boolean {
        val session = sessions.current ?: return false
        val api = apis.create(session.baseUrl)
        status.value = SyncStatus.Syncing
        return try {
            val outcome = LibrarySyncer(store, remoteFor(api)).sync(session.serverId, refresh)
            if (outcome != SyncOutcome.Unchanged) Log.i(TAG, "Library sync: $outcome")
            refreshPlaylists(api)
            refreshLikes(api)
            successful.value += 1
            status.value = SyncStatus.Idle
            true
        } catch (e: CancellationException) {
            status.value = SyncStatus.Idle
            throw e
        } catch (e: HttpException) {
            Log.w(TAG, "Library sync failed", e)
            status.value = SyncStatus.Failed(offline = false)
            false
        } catch (e: Exception) {
            Log.w(TAG, "Library sync failed", e)
            status.value = SyncStatus.Failed(offline = true)
            false
        }
    }

    suspend fun refreshLikes() {
        api()?.let { runCatching { refreshLikes(it) }.onFailure { if (it is CancellationException) throw it } }
    }

    suspend fun setPlaylistFavorite(name: String, favorite: Boolean): Boolean {
        val session = sessions.current ?: return false
        val api = apis.create(session.baseUrl)
        return try {
            api.setPlaylistFavorite(PlaylistFavoriteRequest(name, favorite))
            if (sessions.current != session) return false
            refreshPlaylists(api)
            true
        } catch (error: CancellationException) {
            throw error
        } catch (error: Exception) {
            Log.w(TAG, "Could not change a playlist favorite", error)
            false
        }
    }

    /** Likes or unlikes [trackId] here at once, then on the server; undone if the server says no. */
    suspend fun setLiked(trackId: String, liked: Boolean): Boolean {
        val likes = db.likes()
        if (liked) likes.upsert(listOf(LikeEntity(trackId, (likes.minPosition() ?: 0) - 1))) else likes.delete(trackId)
        val api = api() ?: return false
        return try {
            api.setLike(LikeRequest(trackId, liked))
            true
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not change the like of $trackId", e)
            runCatching { refreshLikes(api) }
            false
        }
    }

    /**
     * `{synced, plain}` lyrics, cached for the session; [Lyrics.Empty] when
     * there are none or the server can't be reached.
     */
    suspend fun lyrics(trackId: String): Lyrics {
        val lang = Locale.getDefault().language.ifBlank { "en" }
        val cacheKey = "$trackId:$lang"
        lyricsCache[cacheKey]?.let { return it }
        val api = api() ?: return Lyrics.Empty
        return try {
            withContext(Dispatchers.Default) { api.lyrics(trackId, lang).toModel() }.also {
                lyricsCache.put(cacheKey, it)
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "No lyrics for $trackId", e)
            Lyrics.Empty
        }
    }

    /** How much later than its LRC [trackId]'s synced lyrics run (0 until moved). */
    fun lyricsOffset(trackId: String): Flow<Long> =
        db.lyricsOffsets().observe(trackId).map { it ?: 0L }.distinctUntilChanged()

    /** Moves [trackId]'s lyrics [byMs] later (earlier when negative), within [LyricsTiming.MAX_MS]. */
    suspend fun shiftLyrics(trackId: String, byMs: Long) {
        val offsets = db.lyricsOffsets()
        // Read and write in one transaction, so quick presses add up instead of overwriting each other.
        db.withTransaction {
            val offset = LyricsTiming.clamp((offsets.get(trackId) ?: 0L) + byMs)
            if (offset == 0L) offsets.delete(trackId) else offsets.upsert(LyricsOffsetEntity(trackId, offset))
        }
    }

    /** Puts [trackId]'s lyrics back on their LRC's times. */
    suspend fun resetLyricsOffset(trackId: String) = db.lyricsOffsets().delete(trackId)

    suspend fun suggestedMix(): SuggestedMixDto? {
        val api = api() ?: return null
        return try {
            api.suggestedMix()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not fetch suggested mix", e)
            null
        }
    }

    suspend fun artistOverview(name: String): ArtistOverviewDto? {
        val web = webApi() ?: return null
        return try {
            web.artistOverview(name)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not fetch artist overview for $name", e)
            null
        }
    }

    suspend fun checkUpdate(): UpdateCheckDto? {
        val web = webApi() ?: return null
        return try {
            web.checkUpdate()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not check update", e)
            null
        }
    }

    suspend fun fetchAllPlaylistsIncludingHidden(): List<Playlist> {
        val api = api() ?: return emptyList()
        return try {
            api.playlists(includeHidden = true).map { it.toModel() }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not fetch hidden playlists", e)
            emptyList()
        }
    }

    suspend fun createPlaylist(name: String, isPublic: Boolean): Boolean {
        val api = api() ?: return false
        return try {
            api.createPlaylist(CreatePlaylistRequest(name.trim(), isPublic))
            refreshPlaylists(api)
            true
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not create playlist $name", e)
            false
        }
    }

    suspend fun deletePlaylist(name: String): Boolean {
        val api = api() ?: return false
        return try {
            api.deletePlaylist(name)
            refreshPlaylists(api)
            true
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not delete playlist $name", e)
            false
        }
    }

    suspend fun setPlaylistVisibility(name: String, isPublic: Boolean): Boolean {
        val api = api() ?: return false
        return try {
            api.setPlaylistVisibility(name, PlaylistVisibilityRequest(isPublic))
            refreshPlaylists(api)
            true
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not set visibility for $name", e)
            false
        }
    }

    suspend fun clonePlaylist(name: String, newName: String = ""): String? {
        val api = api() ?: return null
        return try {
            val res = api.clonePlaylist(name, PlaylistCloneRequest(newName.trim()))
            refreshPlaylists(api)
            res["name"]?.jsonPrimitive?.content ?: newName.ifBlank { "$name (Copy)" }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not clone playlist $name", e)
            null
        }
    }

    suspend fun setPlaylistHidden(name: String, hidden: Boolean): Boolean {
        val api = api() ?: return false
        return try {
            api.setPlaylistHidden(name, PlaylistHideRequest(hidden))
            refreshPlaylists(api)
            true
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not hide/unhide playlist $name", e)
            false
        }
    }

    suspend fun renamePlaylist(name: String, newName: String): String? {
        val api = api() ?: return null
        return try {
            val res = api.renamePlaylist(name, PlaylistRenameRequest(newName.trim()))
            refreshPlaylists(api)
            res["name"]?.jsonPrimitive?.content ?: newName.trim()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not rename playlist $name", e)
            null
        }
    }

    suspend fun changePlaylistOwner(name: String, ownerId: Int): Boolean {
        val api = api() ?: return false
        return try {
            api.changePlaylistOwner(name, PlaylistOwnerRequest(ownerId))
            refreshPlaylists(api)
            true
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not change owner for $name", e)
            false
        }
    }

    suspend fun addTrackToPlaylist(playlistName: String, trackId: String): Boolean {
        val api = api() ?: return false
        return try {
            api.addPlaylistTrack(playlistName, PlaylistTrackMutationRequest(trackId = trackId))
            refreshPlaylists(api)
            true
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not add track $trackId to $playlistName", e)
            false
        }
    }

    suspend fun removeTrackFromPlaylist(playlistName: String, trackId: String): Boolean {
        val api = api() ?: return false
        return try {
            api.removePlaylistTrack(playlistName, PlaylistTrackMutationRequest(trackId = trackId))
            refreshPlaylists(api)
            true
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not remove track $trackId from $playlistName", e)
            false
        }
    }

    suspend fun playlistSuggestions(name: String): List<PlaylistSuggestionItemDto> {
        val api = api() ?: return emptyList()
        return try {
            api.playlistSuggestions(name).suggestions
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not load suggestions for $name", e)
            emptyList()
        }
    }

    suspend fun createShare(
        trackId: String? = null,
        playlist: String? = null,
        title: String? = null,
    ): ShareDto? {
        val api = api() ?: return null
        return try {
            val kind = if (playlist != null) "playlist" else "track"
            api.createShare(CreateShareRequest(kind = kind, trackId = trackId, playlist = playlist, title = title))
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not create share link", e)
            null
        }
    }

    suspend fun myStats(days: Int = 30): ListeningStatsDto? {
        val api = api() ?: return null
        return try {
            api.myStats(days)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not fetch listening stats", e)
            null
        }
    }

    suspend fun clearMyStats(): Boolean {
        val api = api() ?: return false
        return try {
            api.clearMyStats()
            true
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not clear listening stats", e)
            false
        }
    }

    suspend fun fetchMe(): MeResponse? {
        val api = api() ?: return null
        return try {
            api.me()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not fetch me", e)
            null
        }
    }

    suspend fun updateMe(username: String? = null, email: String? = null, displayName: String? = null): Boolean {
        val api = api() ?: return false
        return try {
            api.updateMe(UpdateMeRequest(username = username, email = email, displayName = displayName))
            true
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not update profile", e)
            false
        }
    }

    suspend fun setMyPreferences(hidePublicPlaylistsByDefault: Boolean): Boolean {
        val api = api() ?: return false
        return try {
            api.setMyPreferences(UserPreferencesDto(hidePublicPlaylistsByDefault = hidePublicPlaylistsByDefault))
            true
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not update preferences", e)
            false
        }
    }

    suspend fun listUsers(): List<MobileUserDto> {
        val api = api() ?: return emptyList()
        return try {
            api.listUsers()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not list users", e)
            emptyList()
        }
    }

    suspend fun searchCovers(
        artist: String = "",
        title: String = "",
        track: String? = null,
        query: String? = null,
        trackId: String? = null,
    ): CoverSearchResponseDto? {
        val api = api() ?: return null
        return try {
            api.searchCovers(artist = artist, title = title, track = track, query = query, trackId = trackId)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not search covers", e)
            null
        }
    }

    suspend fun applyCover(
        trackId: String?,
        artist: String,
        album: String,
        url: String,
        scope: String = "album",
        lock: Boolean = true,
    ): Boolean {
        val api = api() ?: return false
        return try {
            api.applyCover(
                ApplyCoverRequest(
                    trackId = trackId,
                    artist = artist,
                    album = album,
                    url = url,
                    scope = scope,
                    lock = lock,
                ),
            )
            sync(refresh = false)
            true
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not apply cover", e)
            false
        }
    }

    suspend fun unlockCover(
        trackId: String?,
        artist: String,
        album: String,
        scope: String = "album",
    ): Boolean {
        val api = api() ?: return false
        return try {
            api.unlockCover(UnlockCoverRequest(trackId = trackId, artist = artist, album = album, scope = scope))
            true
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not unlock cover", e)
            false
        }
    }

    suspend fun upgradeStatus(): UpgradeStatusDto? {
        val api = api() ?: return null
        return try {
            api.upgradeStatus()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not get upgrade status", e)
            null
        }
    }

    suspend fun upgradeScan(): UpgradeStatusDto? {
        val api = api() ?: return null
        return try {
            api.upgradeScan()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not scan for upgrades", e)
            null
        }
    }

    suspend fun upgradeStart(targetFormat: String = "mp3", minBitrate: Int = 256): UpgradeStatusDto? {
        val api = api() ?: return null
        return try {
            api.upgradeStart(UpgradeStartRequest(targetFormat = targetFormat, minBitrate = minBitrate))
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Could not start upgrade", e)
            null
        }
    }

    private suspend fun refreshPlaylists(api: DowntifyApi) {
        val remote = api.playlists()
        playlistExtras.value = remote.associate { p ->
            p.name to PlaylistExtraMeta(
                manual = p.manual,
                isPublic = p.public,
                monitored = p.monitored,
                owner = p.owner,
                ownerId = p.ownerId,
                isOwner = p.isOwner,
                canEdit = p.canEdit,
                canChangeOwner = p.canChangeOwner,
                hidden = p.hidden,
            )
        }
        db.withTransaction {
            db.playlists().deleteAll()
            db.playlists().upsert(
                remote.mapIndexed { index, p ->
                    PlaylistEntity(
                        p.name,
                        p.liked,
                        p.cover,
                        index,
                        p.trackIds,
                        p.favorite == true,
                        p.displayName,
                        p.favorite != null,
                    )
                },
            )
        }
    }

    private suspend fun refreshLikes(api: DowntifyApi) {
        val ids = api.likes().trackIds
        db.withTransaction {
            db.likes().deleteAll()
            db.likes().upsert(ids.mapIndexed { index, id -> LikeEntity(id, index) })
        }
    }

    private fun remoteFor(api: DowntifyApi) = LibraryRemote { since, refresh ->
        val response = api.library(since, if (refresh) true else null)
        when {
            response.code() == HTTP_NOT_MODIFIED -> null
            response.isSuccessful -> response.body()?.toModel() ?: error("Empty library response")
            else -> throw HttpException(response)
        }
    }

    private companion object {
        const val TAG = "LibraryRepository"
        const val HTTP_NOT_MODIFIED = 304
        const val LYRICS_CACHE_SIZE = 32
    }
}
