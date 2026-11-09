package com.henriquesebastiao.downtify.core.network

import com.henriquesebastiao.downtify.core.network.session.AuthInterceptor
import okhttp3.HttpUrl.Companion.toHttpUrl
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AuthInterceptorTest {

    @Test
    fun `sends the token only to the paired server`() {
        val base = "http://192.168.1.20:8000"
        assertTrue(AuthInterceptor.belongsTo("http://192.168.1.20:8000/api/v1/library".toHttpUrl(), base))
        assertFalse(AuthInterceptor.belongsTo("http://192.168.1.20:8001/api/v1/library".toHttpUrl(), base))
        assertFalse(AuthInterceptor.belongsTo("https://192.168.1.20:8000/api".toHttpUrl(), base))
        assertFalse(AuthInterceptor.belongsTo("http://evil.example/api".toHttpUrl(), base))
    }

    @Test
    fun `respects a base path`() {
        val base = "https://music.example.com/downtify"
        assertTrue(AuthInterceptor.belongsTo("https://music.example.com/downtify/api/ws".toHttpUrl(), base))
        assertFalse(AuthInterceptor.belongsTo("https://music.example.com/downtify-other/api".toHttpUrl(), base))
        assertFalse(AuthInterceptor.belongsTo("https://music.example.com/api".toHttpUrl(), base))
    }
}
