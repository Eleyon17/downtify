plugins {
    alias(libs.plugins.downtify.android.library)
    alias(libs.plugins.downtify.hilt)
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "com.henriquesebastiao.downtify.core.network"
}

dependencies {
    api(projects.core.model)
    api(libs.okhttp)
    api(libs.retrofit)
    implementation(libs.retrofit.kotlinx.serialization)
    api(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.tink.android)

    testImplementation(libs.okhttp.mockwebserver)
}
