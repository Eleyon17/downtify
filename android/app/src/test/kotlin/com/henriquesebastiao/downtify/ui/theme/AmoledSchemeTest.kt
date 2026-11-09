package com.henriquesebastiao.downtify.ui.theme

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import com.henriquesebastiao.downtify.core.designsystem.theme.DowntifyDarkColors
import com.henriquesebastiao.downtify.core.designsystem.theme.amoled
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AmoledSchemeTest {
    private val dark = DowntifyDarkColors
    private val black = dark.amoled()

    @Test
    fun theBackgroundAndBaseSurfacesAreTrueBlack() {
        assertEquals(Color.Black, black.background)
        assertEquals(Color.Black, black.surface)
        assertEquals(Color.Black, black.surfaceDim)
        assertEquals(Color.Black, black.surfaceContainerLowest)
    }

    @Test
    fun raisedSurfacesAreDarkerThanBeforeButStillTellApartFromBlack() {
        val raised = listOf(
            dark.surfaceContainerLow to black.surfaceContainerLow,
            dark.surfaceContainer to black.surfaceContainer,
            dark.surfaceContainerHigh to black.surfaceContainerHigh,
            dark.surfaceContainerHighest to black.surfaceContainerHighest,
        )
        raised.forEach { (before, after) ->
            assertTrue(after.luminance() < before.luminance())
            assertTrue(after.luminance() > Color.Black.luminance())
        }
        // The steps keep their order: low < container < high < highest.
        val order = raised.map { it.second.luminance() }
        assertEquals(order.sorted(), order)
    }

    @Test
    fun accentsAreLeftAlone() {
        assertEquals(dark.primary, black.primary)
        assertEquals(dark.onSurface, black.onSurface)
    }
}
