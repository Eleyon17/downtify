package com.henriquesebastiao.downtify.core.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ServerAddressTest {

    @Test
    fun `normalizes typed addresses`() {
        assertEquals("http://192.168.1.20:8000", ServerAddress.normalize(" 192.168.1.20:8000/ "))
        assertEquals(
            "https://music.example.com/downtify",
            ServerAddress.normalize("https://music.example.com/downtify/"),
        )
        assertEquals("http://nas.local", ServerAddress.normalize("HTTP://nas.local"))
        assertNull(ServerAddress.normalize(""))
        assertNull(ServerAddress.normalize("ftp://nas"))
    }

    @Test
    fun `tries the default port first when only a host was typed`() {
        assertEquals(listOf("http://nas:8000", "http://nas"), ServerAddress.candidates("nas"))
        assertEquals(listOf("http://nas", "http://nas:8000"), ServerAddress.candidates("http://nas"))
        assertEquals(listOf("http://nas:9000"), ServerAddress.candidates("nas:9000"))
        assertEquals(listOf("https://nas"), ServerAddress.candidates("https://nas"))
    }

    @Test
    fun `flags cleartext only beyond the local network`() {
        assertFalse(ServerAddress.isCleartextBeyondLan("http://192.168.1.20:8000"))
        assertFalse(ServerAddress.isCleartextBeyondLan("http://10.0.2.2:8000"))
        assertFalse(ServerAddress.isCleartextBeyondLan("http://nas.local:8000"))
        assertFalse(ServerAddress.isCleartextBeyondLan("http://nas:8000"))
        assertFalse(ServerAddress.isCleartextBeyondLan("http://100.101.102.103:8000"))
        assertFalse(ServerAddress.isCleartextBeyondLan("https://music.example.com"))
        assertTrue(ServerAddress.isCleartextBeyondLan("http://music.example.com"))
        assertTrue(ServerAddress.isCleartextBeyondLan("http://203.0.113.7:8000"))
    }
}
