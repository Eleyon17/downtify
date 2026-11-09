# ML Kit (the QR scanner) finds its components by reading class names from the manifest and
# instantiating them by reflection through their no-argument constructors. R8 sees no caller,
# strips the constructors, and the scanner fails at runtime ("Invalid component registrar").
-keep class * implements com.google.firebase.components.ComponentRegistrar {
    <init>();
}

# Retrofit reads a suspend function's response type from the generic signature of its
# Continuation parameter. A response DTO the app never reads (PUT /api/v1/likes answers with
# LikeResponse) has no other users, so R8 removed the class and erased the signature to
# Continuation<Object>: the call then failed to convert the body after the server had saved
# the like, and the app undid it. Keep the DTO classes themselves; their names may still change.
-keep,allowobfuscation class com.henriquesebastiao.downtify.core.network.dto.**
