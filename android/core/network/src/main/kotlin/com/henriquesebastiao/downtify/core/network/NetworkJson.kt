package com.henriquesebastiao.downtify.core.network

import kotlinx.serialization.json.Json

/** Lenient on purpose: new fields and missing optional ones must not break the app. */
val NetworkJson = Json {
    ignoreUnknownKeys = true
    explicitNulls = false
    coerceInputValues = true
    encodeDefaults = true
}
