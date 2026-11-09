package com.henriquesebastiao.downtify.core.model

import java.text.Normalizer

/** Accent- and case-insensitive matching for searching the local library. */
object TextSearch {
    private val marks = Regex("\\p{Mn}+")

    fun normalize(text: String): String =
        marks.replace(Normalizer.normalize(text, Normalizer.Form.NFD), "").lowercase().trim()

    /** Every word of [query] appears in one of [fields]. */
    fun matches(query: String, vararg fields: String): Boolean {
        val words = normalize(query).split(' ').filter { it.isNotEmpty() }
        if (words.isEmpty()) return false
        val haystack = fields.joinToString(" ") { normalize(it) }
        return words.all { it in haystack }
    }
}
