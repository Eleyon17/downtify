package com.henriquesebastiao.downtify.feature.library

import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AtLeastTwoColumnsTest {
    // 3x: 1 dp = 3 px, like a 360 dp phone at 1080 px.
    private val density = Density(3f)
    private val cells = AtLeastTwoColumns(160.dp)

    private fun sizes(widthDp: Int, gapDp: Int = 16) = with(density) {
        with(cells) { calculateCrossAxisCellSizes(widthDp.dp.roundToPx(), gapDp.dp.roundToPx()) }
    }

    @Test
    fun aNarrowPhoneGetsTwoColumnsNotOne() {
        // 360 dp wide, 16 dp padding each side: Adaptive(160) gave a single column here.
        assertEquals(2, sizes(widthDp = 360 - 32).size)
    }

    @Test
    fun theCellsFillTheWidthExactly() {
        listOf(328, 361, 379, 500, 840).forEach { w ->
            val list = sizes(w)
            val gap = 16 * 3
            assertEquals("width $w", w * 3, list.sum() + gap * (list.size - 1))
            assertTrue(list.max() - list.min() <= 1)
        }
    }

    @Test
    fun widerScreensGetMoreColumns() {
        assertEquals(2, sizes(379).size)
        assertEquals(3, sizes(560).size)
        assertEquals(5, sizes(900).size)
    }
}
