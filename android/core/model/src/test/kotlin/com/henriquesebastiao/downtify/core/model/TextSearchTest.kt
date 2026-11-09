package com.henriquesebastiao.downtify.core.model

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TextSearchTest {
    @Test
    fun `matches every word, ignoring case and accents`() {
        assertTrue(TextSearch.matches("beyonce halo", "Halo", "Beyoncé"))
        assertTrue(TextSearch.matches("  ROADS ", "Roads"))
        assertFalse(TextSearch.matches("roads live", "Roads", "Portishead"))
        assertFalse(TextSearch.matches("   ", "anything"))
    }
}
