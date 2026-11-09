package com.henriquesebastiao.downtify.ui.common

import com.henriquesebastiao.downtify.core.data.ServerResult

/** Why a screen that asks the server for its content has none. */
enum class LoadError { Unreachable, Failed }

/** The [LoadError] a failed [ServerResult] comes to, or null for a good one. */
fun ServerResult<*>.loadError(): LoadError? = when (this) {
    is ServerResult.Ok -> null
    ServerResult.Unreachable -> LoadError.Unreachable
    is ServerResult.Failed -> LoadError.Failed
}
