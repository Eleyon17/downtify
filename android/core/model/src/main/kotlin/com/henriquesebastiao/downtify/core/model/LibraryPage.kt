package com.henriquesebastiao.downtify.core.model

/** One answer of the `/api/v1/library` change feed. */
data class LibraryPage(
    val cursor: Long,
    /** `tracks` is the whole library: replace everything local with it. */
    val full: Boolean,
    val tracks: List<Track>,
    val deleted: List<String>,
)
