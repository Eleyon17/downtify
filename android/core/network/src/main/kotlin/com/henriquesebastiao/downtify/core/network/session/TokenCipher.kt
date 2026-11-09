package com.henriquesebastiao.downtify.core.network.session

import android.content.Context
import android.util.Base64
import com.google.crypto.tink.Aead
import com.google.crypto.tink.KeyTemplates
import com.google.crypto.tink.RegistryConfiguration
import com.google.crypto.tink.aead.AeadConfig
import com.google.crypto.tink.integration.android.AndroidKeysetManager

/**
 * Encrypts the device token with a Tink AES-256-GCM key, itself wrapped by a
 * key in the Android Keystore — the token never touches disk in the clear.
 * (Jetpack's EncryptedSharedPreferences is deprecated; this is what it did.)
 */
internal class TokenCipher(context: Context) {
    private val aead: Aead by lazy {
        AeadConfig.register()
        AndroidKeysetManager.Builder()
            .withSharedPref(context, KEYSET_NAME, KEYSET_PREFS)
            .withKeyTemplate(KeyTemplates.get("AES256_GCM"))
            .withMasterKeyUri(MASTER_KEY_URI)
            .build()
            .keysetHandle
            .getPrimitive(RegistryConfiguration.get(), Aead::class.java)
    }

    fun encrypt(plain: String): String =
        Base64.encodeToString(aead.encrypt(plain.toByteArray(), ASSOCIATED_DATA), Base64.NO_WRAP)

    fun decrypt(cipher: String): String = String(aead.decrypt(Base64.decode(cipher, Base64.NO_WRAP), ASSOCIATED_DATA))

    private companion object {
        const val KEYSET_NAME = "downtify_token_keyset"
        const val KEYSET_PREFS = "downtify_keysets"
        const val MASTER_KEY_URI = "android-keystore://downtify_token_master_key"
        val ASSOCIATED_DATA = "downtify-device-token".toByteArray()
    }
}
