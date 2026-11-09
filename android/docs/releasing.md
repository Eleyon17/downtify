# Releasing

Publishing a GitHub release builds the app in CI and attaches the signed APK
(`downtify-android-v<version>.apk`, plus a `.sha256`) to it — see
`.github/workflows/release.yml`.

## Each release

1. In `app/build.gradle.kts`, under `defaultConfig`:
   - `versionName` — the version people see, e.g. `"0.2.0"`. It's the only place: Settings › About reads it
     from `BuildConfig.VERSION_NAME`.
   - `versionCode` — an integer that **must go up with every release** (Android refuses to update to an equal
     or lower one). Nothing checks it for you.
2. Commit and push that change.
3. On GitHub, create a release with the tag `v<versionName>` (e.g. `v0.2.0`) on that commit and **publish** it
   (a draft or a pre-release saved as a draft doesn't trigger the build).
4. The workflow checks the tag against `versionName` (and fails with a message if they differ), builds, checks the
   signature, and uploads the APK to the release. A few minutes later it's in the release's assets.

To rebuild an existing release (say a secret was wrong): Actions › Release APK › Run workflow, and give its tag.

## One-time setup: the release key

The APK has to be signed with the same key every time, or phones can't update from one release to the next.
Create it once and **keep a backup outside GitHub** — if it's lost, no future release can update the installed apps.

```bash
keytool -genkeypair -v -keystore downtify-release.jks -alias downtify \
  -keyalg RSA -keysize 4096 -validity 10000
base64 -w0 downtify-release.jks   # macOS: base64 -i downtify-release.jks
```

Then add four repository secrets (Settings › Secrets and variables › Actions):

| Secret | Value |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | the base64 output above |
| `ANDROID_KEYSTORE_PASSWORD` | the keystore password |
| `ANDROID_KEY_ALIAS` | `downtify` (the `-alias` you gave) |
| `ANDROID_KEY_PASSWORD` | the key password |

Never commit the keystore (`*.jks` is git-ignored).

## Building a release APK locally

`./gradlew :app:assembleRelease` signs with the debug key unless these are set (the CI workflow sets them):

```bash
export DOWNTIFY_KEYSTORE_FILE=/path/to/downtify-release.jks
export DOWNTIFY_KEYSTORE_PASSWORD=…
export DOWNTIFY_KEY_ALIAS=downtify
export DOWNTIFY_KEY_PASSWORD=…
```

The result is `app/build/outputs/apk/release/app-release.apk`. R8 shrinks it, so run a release build on a device
before you publish when you've added a library: reflection-based libraries need keep rules in
`app/proguard-rules.pro` (the ML Kit scanner one is there).
