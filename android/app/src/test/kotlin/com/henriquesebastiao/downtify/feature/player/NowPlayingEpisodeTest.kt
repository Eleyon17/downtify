package com.henriquesebastiao.downtify.feature.player

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.henriquesebastiao.downtify.core.designsystem.theme.DowntifyTheme
import com.henriquesebastiao.downtify.core.player.PlayerState
import com.henriquesebastiao.downtify.core.player.PlayingEpisode
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

@Config(qualifiers = "w411dp-h914dp")
@RunWith(AndroidJUnit4::class)
class NowPlayingEpisodeTest {
    @get:Rule
    val compose = createComposeRule()

    private val episode = PlayingEpisode(7, 1, "The Sweetest Thing", "Radiolab", "", "Podcasts/R/e.mp3")
    private val state = PlayerState(
        episode = episode,
        isPlaying = true,
        positionMs = 83_000,
        durationMs = 1_862_000,
        speed = 1.25f,
    )

    @Test
    fun anEpisodeGetsSkipsAndSpeedInsteadOfShuffleAndQueue() {
        var skippedBack = 0
        var skippedForward = 0
        var speed = 0
        var show: Long? = null
        compose.setContent {
            DowntifyTheme {
                NowPlayingScreen(
                    state = state,
                    isLiked = false,
                    serverName = "nas",
                    actions = NowPlayingActions(
                        onSkipBack = { skippedBack++ },
                        onSkipForward = { skippedForward++ },
                        onCycleSpeed = { speed++ },
                        onGoToShow = { show = it },
                    ),
                )
            }
        }
        compose.onNodeWithText("PODCAST").assertIsDisplayed()
        compose.onNodeWithText("The Sweetest Thing").assertIsDisplayed()
        compose.onNodeWithText("1.25×").assertIsDisplayed()
        compose.onNodeWithContentDescription("Back 10 seconds").performClick()
        compose.onNodeWithContentDescription("Forward 30 seconds").performClick()
        compose.onNodeWithContentDescription("Playback speed 1.25×. Tap to change").performClick()
        assertEquals(1, skippedBack)
        assertEquals(1, skippedForward)
        assertEquals(1, speed)

        // Nothing to like, no lyrics, no queue, no shuffle or repeat on an episode.
        compose.onNodeWithContentDescription("Add to Liked songs").assertDoesNotExist()
        compose.onNodeWithContentDescription("Lyrics").assertDoesNotExist()
        compose.onNodeWithContentDescription("Queue").assertDoesNotExist()
        compose.onNodeWithContentDescription("Shuffle off").assertDoesNotExist()

        // The header (the show's name under "PODCAST") opens the show.
        compose.onNodeWithText("PODCAST").performClick()
        assertEquals(1L, show)
    }
}
