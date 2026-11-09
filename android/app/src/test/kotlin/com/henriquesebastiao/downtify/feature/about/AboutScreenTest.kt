package com.henriquesebastiao.downtify.feature.about

import androidx.compose.ui.test.hasScrollAction
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performScrollToNode
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.henriquesebastiao.downtify.core.designsystem.theme.DowntifyTheme
import com.henriquesebastiao.downtify.core.model.LicensePart
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

@Config(qualifiers = "w411dp-h914dp", sdk = [34])
@RunWith(AndroidJUnit4::class)
class AboutScreenTest {
    @get:Rule
    val compose = createComposeRule()

    // The license screen is a lazy list: what is off screen is not there until scrolled to.
    private fun scrollToText(text: String) = compose.onNode(hasScrollAction()).performScrollToNode(hasText(text))
        .let { compose.onNodeWithText(text) }

    private fun show(actions: AboutActions = AboutActions()) {
        compose.setContent { DowntifyTheme { AboutScreen(versionLabel = "1.4.0 (14)", actions = actions) } }
    }

    @Test
    fun showsTheVersionInTheHeaderAndOnItsRow() {
        show()
        compose.onNodeWithText("Version").assertExists()
        // Header and row both carry it.
        assertEquals(2, compose.onAllNodesWithText("1.4.0 (14)").fetchSemanticsNodes().size)
    }

    @Test
    fun reportingABugOpensTheIssues() {
        var opened = false
        show(AboutActions(onReportBug = { opened = true }))
        compose.onNodeWithText("Report a bug").performClick()
        assertEquals(true, opened)
    }

    @Test
    fun tappingTheVersionCopiesIt() {
        var copied = false
        show(AboutActions(onCopyVersion = { copied = true }))
        compose.onNodeWithText("Version").performClick()
        assertEquals(true, copied)
    }

    @Test
    fun sourceCodeAndLicenseHaveTheirOwnRows() {
        var source = false
        var license = false
        show(AboutActions(onOpenSource = { source = true }, onOpenLicense = { license = true }))
        compose.onNodeWithText("Source code").performClick()
        compose.onNodeWithText("GNU General Public License v3.0").performClick()
        assertEquals(true to true, source to license)
    }

    @Test
    fun termsOpenInASheetWithTheDisclaimer() {
        show()
        compose.onNodeWithText("Terms and disclaimer").performScrollTo().performClick()
        listOf("What this app is", "Your responsibility", "No affiliation", "No warranty, no liability", "Your data")
            .forEach { compose.onNodeWithText(it).assertExists() }
    }

    @Test
    fun supportOpensASheetWithBothLinks() {
        var coffee = false
        var sponsors = false
        show(AboutActions(onOpenBuyMeACoffee = { coffee = true }, onOpenGithubSponsors = { sponsors = true }))
        compose.onNodeWithText("Support the project").performScrollTo().performClick()
        compose.onNodeWithText("Buy Me a Coffee").performClick()
        compose.onNodeWithText("GitHub Sponsors").performClick()
        assertEquals(true to true, coffee to sponsors)
    }

    @Test
    fun theLicenseScreenSummarisesThenShowsTheFullText() {
        compose.setContent {
            DowntifyTheme {
                LicenseScreen(
                    fullText = listOf(
                        LicensePart.Heading("0. Definitions."),
                        LicensePart.Paragraph(
                            "\"This License\" refers to version 3 of the GNU General Public License.",
                        ),
                    ),
                    failed = false,
                    onBack = {},
                )
            }
        }
        compose.onNodeWithText("GNU General Public License v3.0").assertExists()
        listOf(
            "Permissions",
            "Commercial use",
            "Conditions",
            "Disclose source",
            "Limitations",
            "Liability",
            "Full license text",
            "0. Definitions.",
        ).forEach { scrollToText(it).assertExists() }
    }

    @Test
    fun theLicenseScreenSaysWhenTheTextIsMissing() {
        compose.setContent { DowntifyTheme { LicenseScreen(fullText = null, failed = true, onBack = {}) } }
        scrollToText("The license text couldn't be loaded.").assertExists()
    }
}
