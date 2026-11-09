package com.henriquesebastiao.downtify.core.network.dto

import com.henriquesebastiao.downtify.core.model.PodcastEpisode
import com.henriquesebastiao.downtify.core.model.PodcastShow
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// The web API's podcast objects (`/api/podcasts/…`). Like the rest of the web API they aren't
// versioned like `/api/v1`, so every field has a default and unknown ones are ignored.

@Serializable
data class PodcastShowDto(
    val id: Long = 0,
    val name: String = "",
    val author: String? = null,
    val description: String? = null,
    @SerialName("artwork_url") val artworkUrl: String? = null,
    @SerialName("episode_count") val episodeCount: Int = 0,
    @SerialName("downloaded_count") val downloadedCount: Int = 0,
) {
    fun toModel() = PodcastShow(
        id = id,
        name = name,
        author = author.orEmpty(),
        description = description.orEmpty(),
        artworkUrl = artworkUrl.orEmpty(),
        episodeCount = episodeCount,
        downloadedCount = downloadedCount,
    )
}

@Serializable
data class PodcastEpisodeDto(
    val id: Long = 0,
    @SerialName("show_id") val showId: Long = 0,
    val title: String? = null,
    val description: String? = null,
    @SerialName("published_at") val publishedAt: String? = null,
    @SerialName("duration_seconds") val durationSeconds: Double? = null,
    @SerialName("season_number") val seasonNumber: Int? = null,
    @SerialName("episode_number") val episodeNumber: Int? = null,
    val filename: String? = null,
    @SerialName("position_seconds") val positionSeconds: Double? = null,
    val played: Boolean? = null,
) {
    fun toModel() = PodcastEpisode(
        id = id,
        showId = showId,
        title = title.orEmpty(),
        description = description.orEmpty(),
        publishedAt = publishedAt.orEmpty(),
        durationSeconds = durationSeconds?.toInt() ?: 0,
        seasonNumber = seasonNumber,
        episodeNumber = episodeNumber,
        filename = filename?.takeIf { it.isNotBlank() },
        positionSeconds = positionSeconds ?: 0.0,
        played = played == true,
    )
}

/** `GET /api/podcasts/shows/{id}/episodes`. */
@Serializable
data class PodcastEpisodesDto(
    val show: PodcastShowDto = PodcastShowDto(),
    val episodes: List<PodcastEpisodeDto> = emptyList(),
)

/** `PUT /api/podcasts/episodes/{id}/playback`: either field alone is fine. */
@Serializable
data class PodcastPlaybackRequest(
    @SerialName("position_seconds") val positionSeconds: Double? = null,
    val played: Boolean? = null,
)
