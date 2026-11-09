package com.henriquesebastiao.downtify.core.network

import com.henriquesebastiao.downtify.core.model.DiscoverSeed
import com.henriquesebastiao.downtify.core.network.dto.DiscoverArtistsDto
import com.henriquesebastiao.downtify.core.network.dto.DiscoverCollectionsDto
import com.henriquesebastiao.downtify.core.network.dto.DiscoverRequest
import com.henriquesebastiao.downtify.core.network.dto.PodcastEpisodesDto
import com.henriquesebastiao.downtify.core.network.dto.PodcastPlaybackRequest
import com.henriquesebastiao.downtify.core.network.dto.PodcastShowDto
import kotlinx.serialization.encodeToString
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** The API reference's own examples for podcasts and Discover parse into what the app expects. */
class PodcastDiscoverJsonTest {

    @Test
    fun `a show and its episodes`() {
        val answer = NetworkJson.decodeFromString<PodcastEpisodesDto>(
            """
            {"show":{"id":1,"feed_url":"https://feeds.simplecast.com/x","name":"Radiolab","author":"WNYC Studios",
              "description":"…","artwork_url":"https://a/b.jpg","folder_name":"Radiolab","retention":3,
              "watch_id":1,"interval_minutes":720,"enabled":true,"last_checked":"2026-09-27T10:00:00+00:00",
              "episode_count":671,"downloaded_count":3},
             "episodes":[
              {"id":1,"show_id":1,"guid":"g","title":"The Sweetest Thing","description":"d",
               "published_at":"2026-09-18T14:00:00+00:00","duration_seconds":1862,"season_number":null,
               "episode_number":712,"enclosure_url":"https://e","enclosure_type":"audio/mpeg",
               "filename":"Podcasts/Radiolab/2026-09-18 - The Sweetest Thing.mp3","downloaded_at":"x",
               "dismissed":false,"position_seconds":13.9,"played":false},
              {"id":2,"show_id":1,"title":"Older","duration_seconds":null,"filename":null,"position_seconds":null,
               "played":null}]}
            """.trimIndent(),
        )
        val show = answer.show.toModel()
        assertEquals("Radiolab", show.name)
        assertEquals(671, show.episodeCount)
        val (first, second) = answer.episodes.map { it.toModel() }
        assertEquals(1862, first.durationSeconds)
        assertEquals(13.9, first.positionSeconds, 0.0)
        assertTrue(first.isDownloaded)
        assertEquals(712, first.episodeNumber)
        // A server that leaves fields out or sends null never breaks the list.
        assertFalse(second.isDownloaded)
        assertEquals(0, second.durationSeconds)
        assertFalse(second.played)
    }

    @Test
    fun `a show without an author or artwork`() {
        val show = NetworkJson.decodeFromString<PodcastShowDto>("""{"id":2,"name":"X","author":null}""").toModel()
        assertEquals("", show.author)
        assertEquals("", show.artworkUrl)
    }

    @Test
    fun `playback is saved with only what changed`() {
        assertEquals(
            """{"position_seconds":42.5}""",
            NetworkJson.encodeToString(PodcastPlaybackRequest(positionSeconds = 42.5)),
        )
        assertEquals(
            """{"position_seconds":0.0,"played":false}""",
            NetworkJson.encodeToString(PodcastPlaybackRequest(positionSeconds = 0.0, played = false)),
        )
        assertEquals("""{"played":true}""", NetworkJson.encodeToString(PodcastPlaybackRequest(played = true)))
    }

    @Test
    fun `suggested artists`() {
        val answer = NetworkJson.decodeFromString<DiscoverArtistsDto>(
            """
            {"artists":[{"name":"Hooverphonic","deezer_id":"1146","picture_url":"https://cdn/500x500.jpg",
              "fans":402551,"score":4.428,"because":["Portishead","Massive Attack"]},
             {"name":"Archive","picture_url":null}],
             "seeds":["Portishead"],"partial":true}
            """.trimIndent(),
        )
        assertTrue(answer.partial)
        val (first, second) = answer.artists.map { it.toModel() }
        assertEquals(listOf("Portishead", "Massive Attack"), first.because)
        assertEquals("https://cdn/500x500.jpg", first.pictureUrl)
        assertEquals("", second.pictureUrl)
    }

    @Test
    fun `albums and playlists built on the suggestions`() {
        val answer = NetworkJson.decodeFromString<DiscoverCollectionsDto>(
            """
            {"albums":[{"name":"Grace","artist":"Jeff Buckley","year":"1994","cover_url":"https://i.scdn.co/x",
               "spotify_id":"7yQ","url":"https://open.spotify.com/album/7yQ","reason":"similar","because":["Radiohead"]}],
             "more_albums":[],
             "playlists":[{"name":"Portishead Radio","owner":"Spotify","cover_url":"c","spotify_id":"37i",
               "url":"https://open.spotify.com/playlist/37i","reason":"radio","artist":"Portishead"}],
             "artist_urls":{"Jeff Buckley":"https://open.spotify.com/artist/3nn"},"partial":false}
            """.trimIndent(),
        )
        assertEquals("https://open.spotify.com/album/7yQ", answer.albums.single().toModel().url)
        assertEquals("radio", answer.playlists.single().toModel().reason)
        assertEquals("https://open.spotify.com/artist/3nn", answer.artistUrls["Jeff Buckley"])
    }

    @Test
    fun `the request sends the library's artists and, for collections, its albums`() {
        val seeds = listOf(DiscoverSeed("Portishead", 12, 3))
        assertEquals(
            """{"library":[{"name":"Portishead","tracks":12,"liked":3}]}""",
            NetworkJson.encodeToString(DiscoverRequest.of(seeds)),
        )
        val withAlbums = NetworkJson.encodeToString(DiscoverRequest.of(seeds, listOf("Portishead" to "Dummy")))
        assertEquals(
            """{"library":[{"name":"Portishead","tracks":12,"liked":3}],""" +
                """"albums":[{"artist":"Portishead","title":"Dummy"}]}""",
            withAlbums,
        )
        assertNull(DiscoverRequest.of(seeds).albums)
    }
}
