package com.henriquesebastiao.downtify.core.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LicenseTextTest {
    @Test
    fun joinsWrappedLinesAndSplitsAtBlankLines() {
        val parts = LicenseText.parts(
            """
            This is a paragraph that was wrapped
            by hand at eighty columns.

            And this is another one.
            """.trimIndent(),
        )
        assertEquals(
            listOf(
                LicensePart.Paragraph("This is a paragraph that was wrapped by hand at eighty columns."),
                LicensePart.Paragraph("And this is another one."),
            ),
            parts,
        )
    }

    @Test
    fun aCenteredTitleKeepsItsLinesAsAHeading() {
        val parts = LicenseText.parts(
            "                    GNU GENERAL PUBLIC LICENSE\n                       Version 3, 29 June 2007\n\nText.",
        )
        assertEquals(LicensePart.Heading("GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007"), parts.first())
        assertEquals(LicensePart.Paragraph("Text."), parts[1])
    }

    @Test
    fun sectionTitlesAreHeadings() {
        val parts = LicenseText.parts(
            "TERMS AND CONDITIONS\n\n0. Definitions.\n\n10. Automatic Licensing of Downstream Recipients.\n\n" +
                "1. Not a title because it goes on, and on, with commas and a long sentence that is a paragraph.",
        )
        assertEquals(
            listOf(true, true, true, false),
            parts.map { it is LicensePart.Heading },
        )
    }

    @Test
    fun theBundledLicenseIsTheRepositorysAndReadsAsManyParts() {
        // The copy the app shows (res/raw) must stay the repository's LICENSE.
        val root = java.io.File("../../LICENSE")
        val bundled = java.io.File("../../app/src/main/res/raw/license.txt")
        if (root.exists() && bundled.exists()) assertEquals(root.readText(), bundled.readText())
        val parts = LicenseText.parts(root.takeIf { it.exists() }?.readText() ?: bundled.readText())
        assertTrue(parts.size > 100)
        assertTrue(parts.first() is LicensePart.Heading)
        assertTrue(parts.none { it.text.isBlank() })
    }
}
