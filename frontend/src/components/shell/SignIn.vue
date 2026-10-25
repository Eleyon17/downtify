<template>
  <main class="flex min-h-dvh items-center justify-center bg-bg px-4 py-8 text-fg">
    <div
      class="flex w-full max-w-sm flex-col gap-6 rounded-panel border border-line-2 bg-surface p-6 sm:p-8"
    >
      <div class="flex flex-col items-center gap-3 text-center">
        <AppLogo :size="48" />
        <h1 class="text-display text-2xl font-semibold">
          {{ isSignUp ? t('auth.signUpTitle') : t('auth.signInTitle') }}
        </h1>
        <p class="text-sm text-muted">
          {{ isSignUp ? t('auth.signUpBody') : t('auth.signInBody') }}
        </p>
      </div>

      <!-- Tab toggle: Sign in vs Sign up -->
      <div class="flex rounded-control bg-surface-2 p-1 text-sm font-medium">
        <button
          type="button"
          class="flex-1 rounded-[8px] py-1.5 text-center transition-colors"
          :class="!isSignUp ? 'bg-surface font-semibold text-fg shadow-sm' : 'text-muted hover:text-fg'"
          @click="isSignUp = false; error = ''"
        >
          {{ t('auth.signIn') }}
        </button>
        <button
          type="button"
          class="flex-1 rounded-[8px] py-1.5 text-center transition-colors"
          :class="isSignUp ? 'bg-surface font-semibold text-fg shadow-sm' : 'text-muted hover:text-fg'"
          @click="isSignUp = true; error = ''"
        >
          {{ t('auth.signUp') }}
        </button>
      </div>

      <!-- Google OAuth Button -->
      <button
        type="button"
        class="flex h-11 w-full items-center justify-center gap-3 rounded-control border border-line-2 bg-surface hover:bg-surface-2 transition-colors px-4 text-sm font-semibold text-fg shadow-sm active:scale-[0.99]"
        :disabled="busy"
        @click="triggerGoogleAuth"
      >
        <svg class="size-4 shrink-0" viewBox="0 0 24 24">
          <path
            fill="#4285F4"
            d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.8-2.4 3.68v3.05h3.88c2.27-2.09 3.66-5.17 3.66-9.17z"
          />
          <path
            fill="#34A853"
            d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.33 24 12 24z"
          />
          <path
            fill="#FBBC05"
            d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 9.99 0 12s.45 3.82 1.25 5.42l4.03-3.15z"
          />
          <path
            fill="#EA4335"
            d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98z"
          />
        </svg>
        <span>{{ isSignUp ? t('auth.signUpWithGoogle') : t('auth.signInWithGoogle') }}</span>
      </button>

      <div class="relative flex items-center justify-center">
        <div class="w-full border-t border-line" />
        <span class="absolute bg-surface px-3 text-xs text-faint uppercase tracking-wider">or</span>
      </div>

      <!-- Sign In / Sign Up Form -->
      <form class="flex flex-col gap-4" @submit.prevent="submit">
        <template v-if="isSignUp">
          <UiInput
            v-model="displayName"
            :label="t('auth.name')"
            icon="user"
            autocomplete="name"
            placeholder="Your name"
          />
          <UiInput
            v-model="email"
            type="email"
            :label="t('auth.email')"
            icon="mail"
            autocomplete="email"
            placeholder="you@example.com"
          />
          <UiInput
            v-model="username"
            :label="t('auth.username')"
            icon="user"
            autocomplete="username"
            placeholder="Optional (defaults to email prefix)"
          />
          <UiInput
            v-model="password"
            type="password"
            :label="t('auth.password')"
            icon="lock"
            autocomplete="new-password"
            :error="error"
          />
        </template>

        <template v-else>
          <UiInput
            v-model="username"
            :label="t('auth.username')"
            icon="user"
            autocomplete="username"
          />
          <UiInput
            v-model="password"
            type="password"
            :label="t('auth.password')"
            icon="lock"
            autocomplete="current-password"
            :error="error"
          />
        </template>

        <UiButton
          type="submit"
          variant="primary"
          size="lg"
          class="mt-2"
          :loading="busy"
          :disabled="isSignUp ? (!password || (!username.trim() && !email.trim())) : (!username.trim() || !password)"
        >
          {{ isSignUp ? t('auth.createAccount') : t('auth.signIn') }}
        </UiButton>
      </form>

      <p class="text-center text-[12px] text-faint">
        {{ t('auth.forgotHint') }}
      </p>
    </div>

    <!-- Google OAuth Setup Modal (shown when Google Client ID has not been set up) -->
    <UiModal
      :open="googleModalOpen"
      :title="t('auth.googleNotConfiguredTitle')"
      @close="googleModalOpen = false"
    >
      <div class="flex flex-col gap-4 text-sm text-pretty text-fg-2">
        <p>{{ t('auth.googleNotConfiguredBody') }}</p>
        <div class="flex flex-col gap-2 rounded-control border border-line-2 bg-surface-2 p-3 text-xs">
          <div class="flex items-center justify-between">
            <span class="text-muted font-medium">Authorized redirect URI:</span>
            <button
              type="button"
              class="text-accent hover:underline text-[11px] font-semibold"
              @click="copyText(redirectUri, 'uri')"
            >
              {{ copiedField === 'uri' ? 'Copied!' : 'Copy' }}
            </button>
          </div>
          <span class="font-mono select-all text-fg break-all">{{ redirectUri }}</span>

          <div class="flex items-center justify-between mt-2 pt-2 border-t border-line">
            <span class="text-muted font-medium">Authorized JavaScript origin:</span>
            <button
              type="button"
              class="text-accent hover:underline text-[11px] font-semibold"
              @click="copyText(origin, 'origin')"
            >
              {{ copiedField === 'origin' ? 'Copied!' : 'Copy' }}
            </button>
          </div>
          <span class="font-mono select-all text-fg break-all">{{ origin }}</span>
        </div>
        <div class="text-xs text-muted space-y-1">
          <p>
            In Google Cloud Console under <strong>APIs &amp; Services &gt; Credentials &gt; OAuth 2.0 Client ID</strong>:
          </p>
          <ul class="list-disc pl-4 space-y-0.5">
            <li>Add the <strong>Authorized redirect URI</strong> above.</li>
            <li>Add the <strong>Authorized JavaScript origin</strong> above.</li>
          </ul>
        </div>
      </div>
      <template #footer>
        <UiButton variant="primary" @click="googleModalOpen = false">
          {{ t('auth.noticeOk') }}
        </UiButton>
      </template>
    </UiModal>

    <!-- A server upgraded from a version without accounts says so once. -->
    <UiModal
      :open="noticeOpen"
      :title="t('auth.noticeTitle')"
      @close="noticeOpen = false"
    >
      <div class="flex flex-col gap-4 text-sm text-pretty text-fg-2">
        <p>{{ t('auth.noticeBody') }}</p>
        <dl
          v-if="notice"
          class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 rounded-control border border-line-2 bg-surface-2 px-4 py-3"
        >
          <dt class="text-muted">{{ t('auth.username') }}</dt>
          <dd class="font-mono font-semibold select-all">
            {{ notice.username }}
          </dd>
          <dt class="text-muted">{{ t('auth.password') }}</dt>
          <dd
            class="font-semibold"
            :class="notice.password ? 'font-mono select-all' : ''"
          >
            {{ notice.password || t('auth.noticeKeptPassword') }}
          </dd>
        </dl>
        <p class="text-muted">{{ t('auth.noticeChange') }}</p>
      </div>
      <template #footer>
        <UiButton variant="primary" @click="useNotice">
          {{ t('auth.noticeOk') }}
        </UiButton>
      </template>
    </UiModal>
  </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import AppLogo from '../ui/AppLogo.vue'
import UiButton from '../ui/UiButton.vue'
import UiInput from '../ui/UiInput.vue'
import UiModal from '../ui/UiModal.vue'
import { useAuth } from '/src/model/auth'
import { useI18n } from '/src/i18n'

const { t } = useI18n()
const auth = useAuth()
const isSignUp = ref(false)
const displayName = ref('')
const email = ref('')
const username = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')

const googleModalOpen = ref(false)
const copiedField = ref('')
const origin = computed(() => {
  return typeof window !== 'undefined' ? window.location.origin : ''
})
const redirectUri = computed(() => {
  return auth.status.value?.google_redirect_uri || (origin.value ? `${origin.value}/api/auth/google/callback` : '/api/auth/google/callback')
})

function copyText(text, field) {
  if (navigator?.clipboard?.writeText) {
    navigator.clipboard.writeText(text)
    copiedField.value = field
    setTimeout(() => {
      if (copiedField.value === field) copiedField.value = ''
    }, 2000)
  }
}

const notice = computed(() => auth.status.value?.notice || null)
const noticeOpen = ref(false)
watch(
  notice,
  (value) => {
    if (value) noticeOpen.value = true
  },
  { immediate: true }
)

onMounted(() => {
  // Check for error parameters returned from OAuth callback
  const params = new URLSearchParams(window.location.search)
  const err = params.get('error')
  if (err) {
    if (err === 'missing_code') error.value = 'Google sign-in was cancelled.'
    else if (err.includes('redirect_uri_mismatch')) {
      error.value = `Google redirect_uri_mismatch: Add ${redirectUri.value} to Authorized Redirect URIs in Google Cloud Console.`
    } else error.value = `Google sign-in failed (${err})`
  }

  // If GIS is available and Google client ID is configured, initialize GIS
  const clientId = auth.status.value?.google_client_id
  if (clientId && window.google?.accounts?.id) {
    try {
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: async (resp) => {
          if (resp?.credential) {
            busy.value = true
            const res = await auth.signInWithGoogle({ credential: resp.credential })
            if (res !== true) {
              error.value = String(res)
              busy.value = false
            }
          }
        },
      })
    } catch {
      // Ignore GIS init errors
    }
  }
})

function useNotice() {
  username.value = notice.value?.username || username.value
  if (notice.value?.password) password.value = notice.value.password
  noticeOpen.value = false
}

function triggerGoogleAuth() {
  if (auth.status.value?.google_auth_enabled) {
    // Initiate real Google OAuth flow with explicit redirect_uri
    const uri = redirectUri.value
    window.location.href = `/api/auth/google/login?redirect_uri=${encodeURIComponent(uri)}`
    return
  }
  // Not configured yet on server -> show setup guidance modal
  googleModalOpen.value = true
}

async function submit() {
  if (busy.value) return
  busy.value = true
  error.value = ''

  if (isSignUp.value) {
    const result = await auth.signUp({
      username: username.value.trim() || undefined,
      email: email.value.trim() || undefined,
      display_name: displayName.value.trim() || undefined,
      password: password.value,
    })
    if (result !== true) {
      error.value = String(result)
      busy.value = false
    }
  } else {
    if (!username.value.trim() || !password.value) {
      busy.value = false
      return
    }
    const result = await auth.signIn(username.value.trim(), password.value)
    if (result !== true) {
      if (result === 'Wrong username or password')
        error.value = t('auth.wrongPassword')
      else if (result === 'tooMany') error.value = t('auth.tooMany')
      else error.value = String(result)
      busy.value = false
    }
  }
}
</script>
