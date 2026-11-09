package com.henriquesebastiao.downtify.core.network

import retrofit2.HttpException

/** The HTTP status of a failed call, or null for a network failure. */
val Throwable.httpStatus: Int? get() = (this as? HttpException)?.code()

/** `Retry-After` in seconds from a failed call, when the server sent one. */
val Throwable.retryAfterSeconds: Long? get() =
    (this as? HttpException)?.response()?.headers()?.get("Retry-After")?.trim()?.toLongOrNull()
