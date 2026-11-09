package com.henriquesebastiao.downtify.core.model

import java.net.Inet4Address
import java.net.InetAddress
import java.net.URI
import java.net.URISyntaxException

/** Turning what the user typed into a server base URL. */
object ServerAddress {

    /** The port Downtify listens on by default. */
    const val DEFAULT_PORT = 8000

    /**
     * [input] as a base URL: `http://` added when no scheme is given, no
     * trailing slash, path kept (a reverse proxy may serve Downtify under one).
     * Null when it isn't an http(s) address with a host.
     */
    fun normalize(input: String): String? {
        var text = input.trim()
        if (text.isEmpty()) return null
        if (!text.contains("://")) text = "http://$text"
        val uri = try {
            URI(text)
        } catch (_: URISyntaxException) {
            return null
        }
        val scheme = uri.scheme?.lowercase()
        if (scheme != "http" && scheme != "https") return null
        val host = uri.host ?: return null
        if (host.isBlank()) return null
        val port = if (uri.port > 0) ":${uri.port}" else ""
        val hostPart = if (host.contains(':') && !host.startsWith("[")) "[$host]" else host
        val path = uri.rawPath.orEmpty().trimEnd('/')
        return "$scheme://$hostPart$port$path"
    }

    /**
     * Base URLs to try for [input], best first: as typed, then — when no port
     * was typed on a plain `http` address — on Downtify's default port.
     */
    fun candidates(input: String): List<String> {
        val base = normalize(input) ?: return emptyList()
        val uri = URI(base)
        val typedScheme = input.trim().contains("://")
        return if (uri.port == -1 && uri.scheme == "http") {
            val withPort = URI(uri.scheme, null, uri.host, DEFAULT_PORT, uri.rawPath, null, null).toString()
            if (typedScheme) listOf(base, withPort) else listOf(withPort, base)
        } else {
            listOf(base)
        }
    }

    /**
     * Whether [baseUrl] sends credentials in the clear over a network other than
     * the local one: plain `http` to a public address or hostname.
     */
    fun isCleartextBeyondLan(baseUrl: String): Boolean {
        val uri = try {
            URI(baseUrl)
        } catch (_: URISyntaxException) {
            return false
        }
        if (uri.scheme != "http") return false
        val host = uri.host?.trim('[', ']') ?: return false
        return !isLocalHost(host)
    }

    /** Private, loopback and link-local IPs, `.local`/`.lan`/`.home.arpa` names and single-label names. */
    fun isLocalHost(host: String): Boolean {
        val lower = host.lowercase()
        if (lower == "localhost" || LOCAL_SUFFIXES.any { lower.endsWith(it) }) return true
        if (isIpLiteral(lower)) {
            val address = try {
                InetAddress.getByName(lower)
            } catch (_: Exception) {
                return false
            }
            return address.isSiteLocalAddress || address.isLoopbackAddress || address.isLinkLocalAddress ||
                isUniqueLocalV6(address) || isCarrierGradeNat(address)
        }
        return !lower.contains('.')
    }

    private val LOCAL_SUFFIXES = listOf(".local", ".lan", ".home.arpa", ".internal", ".localdomain")

    private fun isIpLiteral(host: String): Boolean =
        host.contains(':') || (host.all { it.isDigit() || it == '.' } && host.count { it == '.' } == 3)

    private fun isUniqueLocalV6(address: InetAddress): Boolean =
        address !is Inet4Address && (address.address[0].toInt() and 0xFE) == 0xFC

    /** 100.64.0.0/10, used by Tailscale and other overlay VPNs. */
    private fun isCarrierGradeNat(address: InetAddress): Boolean {
        if (address !is Inet4Address) return false
        val bytes = address.address
        return bytes[0].toInt() == 100 && (bytes[1].toInt() and 0xC0) == 64
    }
}
