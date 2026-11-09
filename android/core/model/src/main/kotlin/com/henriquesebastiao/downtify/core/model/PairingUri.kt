package com.henriquesebastiao.downtify.core.model

import java.net.URI
import java.net.URISyntaxException
import java.net.URLDecoder

/**
 * The QR code the web page shows under Settings › Apps › Pair a phone:
 * `downtify://pair?url=<base URL>&sid=<server_id>&code=<code>`.
 */
data class PairingPayload(val baseUrl: String, val serverId: String, val code: String) {
    companion object {
        private const val SCHEME = "downtify"
        private const val HOST = "pair"

        /** The payload in [text], or null when it isn't a Downtify pairing code. */
        fun parse(text: String): PairingPayload? {
            val uri = try {
                URI(text.trim())
            } catch (_: URISyntaxException) {
                return null
            }
            if (!uri.scheme.equals(SCHEME, ignoreCase = true) || !uri.host.equals(HOST, ignoreCase = true)) {
                return null
            }
            val params = queryParams(uri.rawQuery ?: return null)
            val url = params["url"]?.let(ServerAddress::normalize) ?: return null
            val sid = params["sid"]?.trim().orEmpty()
            val code = params["code"]?.trim().orEmpty()
            if (sid.isEmpty() || code.isEmpty()) return null
            return PairingPayload(baseUrl = url, serverId = sid, code = code)
        }

        private fun queryParams(raw: String): Map<String, String> = raw.split('&')
            .mapNotNull { part ->
                val key = part.substringBefore('=')
                if (key.isEmpty()) return@mapNotNull null
                val value = part.substringAfter('=', missingDelimiterValue = "")
                decode(key) to decode(value)
            }
            .toMap()

        private fun decode(value: String): String = URLDecoder.decode(value, "UTF-8")
    }
}
