package com.henriquesebastiao.downtify.core.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PairingPayloadTest {

    @Test
    fun `parses the web page's QR code`() {
        val payload = PairingPayload.parse(
            "downtify://pair?url=http%3A%2F%2F192.168.1.20%3A8000&sid=cf12b3c4f530731551690cc62b1365a1&code=K7QM-2XPD",
        )
        assertEquals(
            PairingPayload("http://192.168.1.20:8000", "cf12b3c4f530731551690cc62b1365a1", "K7QM-2XPD"),
            payload,
        )
    }

    @Test
    fun `accepts an unencoded url with a path and a trailing slash`() {
        val payload = PairingPayload.parse(
            "downtify://pair?url=https://music.example.com/downtify/&sid=abc&code=1234-ABCD",
        )
        assertEquals("https://music.example.com/downtify", payload?.baseUrl)
    }

    @Test
    fun `parameter order does not matter`() {
        val payload = PairingPayload.parse("downtify://pair?code=AAAA-BBBB&sid=s1&url=http%3A%2F%2Fnas%3A8000")
        assertEquals(PairingPayload("http://nas:8000", "s1", "AAAA-BBBB"), payload)
    }

    @Test
    fun `rejects other schemes, hosts and missing fields`() {
        assertNull(PairingPayload.parse("https://pair?url=http://x&sid=a&code=b"))
        assertNull(PairingPayload.parse("downtify://login?url=http://x&sid=a&code=b"))
        assertNull(PairingPayload.parse("downtify://pair?url=http://x&sid=a"))
        assertNull(PairingPayload.parse("downtify://pair?sid=a&code=b"))
        assertNull(PairingPayload.parse("downtify://pair?url=ftp://x&sid=a&code=b"))
        assertNull(PairingPayload.parse("downtify://pair"))
        assertNull(PairingPayload.parse("not a uri at all %%%"))
    }
}
