package com.henriquesebastiao.downtify.core.model

/** A piece of the license, ready to show: a title or a paragraph. */
sealed interface LicensePart {
    val text: String

    data class Heading(override val text: String) : LicensePart

    data class Paragraph(override val text: String) : LicensePart
}

/**
 * Turns the license's plain text, hard-wrapped at about 80 columns, into paragraphs that wrap to the
 * screen: lines within a block are joined, blocks are split at blank lines, and the section titles
 * ("TERMS AND CONDITIONS", "0. Definitions.") are marked as headings.
 */
object LicenseText {
    private val numberedTitle = Regex("""^\d+\.\s+\S[^.]{0,60}\.?$""")
    private const val CENTERED_INDENT = 10

    fun parts(raw: String): List<LicensePart> = raw.replace("\r\n", "\n")
        .split(Regex("""\n[ \t]*\n"""))
        .mapNotNull { block ->
            val lines = block.lines().filter { it.isNotBlank() }
            if (lines.isEmpty()) return@mapNotNull null
            val centered = lines.first().takeWhile { it == ' ' }.length >= CENTERED_INDENT
            val text = if (centered) lines.joinToString("\n") { it.trim() } else lines.joinToString(" ") { it.trim() }
            when {
                centered || isTitle(text) -> LicensePart.Heading(text)
                else -> LicensePart.Paragraph(text)
            }
        }

    private fun isTitle(text: String): Boolean {
        val letters = text.filter { it.isLetter() }
        val allCaps = letters.length >= 3 && letters.all { it.isUpperCase() }
        return !text.contains('\n') && (allCaps || numberedTitle.matches(text))
    }
}
