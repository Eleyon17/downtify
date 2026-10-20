// The signed-in user's own preferences (Settings > General) and the
// "what am I playing" reports behind the admins' Activity page.
//
// Theme, language and "Show lyrics" still apply at once in this browser
// (and are remembered in it); they are also kept with the account, so
// signing in somewhere else brings them along. "Albums in search" lives
// only with the account - and changing any of these changes nothing for
// anyone else.
import { ref, watch } from 'vue'

import API from '/src/model/api'
import { currentLocale, setLocale } from '/src/i18n'
import { playbackReport } from '/src/lib/auth'
import { useAuth } from '/src/model/auth'
import { usePlayer } from '/src/model/player'
import { usePlayerPrefs } from '/src/model/playerPrefs'
import { useTheme } from '/src/model/theme'

const searchAlbums = ref(true)
const hidePublicPlaylists = ref(true)
const ready = ref(false)
let started = false

function current() {
  const theme = useTheme()
  const { showLyrics, translateLyrics } = usePlayerPrefs()
  return {
    theme: theme.mode.value,
    locale: currentLocale.value,
    show_lyrics: showLyrics.value,
    translate_lyrics: translateLyrics.value,
    search_albums: searchAlbums.value,
    hide_public_playlists_by_default: hidePublicPlaylists.value,
  }
}

function apply(prefs) {
  const theme = useTheme()
  const { showLyrics, translateLyrics } = usePlayerPrefs()
  if (prefs.theme) theme.setMode(prefs.theme)
  if (prefs.locale && prefs.locale !== currentLocale.value)
    setLocale(prefs.locale)
  if (typeof prefs.show_lyrics === 'boolean')
    showLyrics.value = prefs.show_lyrics
  if (typeof prefs.translate_lyrics === 'boolean')
    translateLyrics.value = prefs.translate_lyrics
  if (typeof prefs.search_albums === 'boolean')
    searchAlbums.value = prefs.search_albums
  if (typeof prefs.hide_public_playlists_by_default === 'boolean')
    hidePublicPlaylists.value = prefs.hide_public_playlists_by_default
}

async function save() {
  try {
    await API.setPreferences(current())
  } catch {
    // Kept in this browser anyway; the next change tries again.
  }
}

/** Load the account's preferences, then keep them in step. */
async function start() {
  if (started) return
  started = true
  let prefs = {}
  try {
    prefs = (await API.getMe()).data?.preferences || {}
  } catch {
    started = false
    return
  }
  apply(prefs)
  ready.value = true
  // An account without them adopts this browser's.
  if (Object.keys(prefs).length < 5) save()
  const theme = useTheme()
  const { showLyrics, translateLyrics } = usePlayerPrefs()
  watch(
    [
      theme.mode,
      currentLocale,
      showLyrics,
      translateLyrics,
      searchAlbums,
      hidePublicPlaylists,
    ],
    () => save(),
    {
      flush: 'post',
    }
  )
}

// ── Playback reports ──────────────────────────────────────────────────
const HEARTBEAT_MS = 30000
let reporting = false

function startPlaybackReports() {
  if (reporting) return
  reporting = true
  const player = usePlayer()
  let lastSent = 0
  let lastState = ''
  let lastFile = ''

  function send(state) {
    const track = player.currentTrack.value
    const report = playbackReport(track, {
      player: API.clientId,
      state,
      position: player.currentTime.value,
    })
    if (!report) return
    lastSent = Date.now()
    lastState = state
    lastFile = track?.file || ''
    API.reportPlayback(report).catch(() => {
      // Best effort: it only feeds the admins' Activity page.
    })
  }

  watch(
    () => [player.currentTrack.value?.file, player.isPlaying.value],
    ([file, playing]) => {
      if (!file) {
        if (lastFile) send('stopped')
        lastFile = ''
        return
      }
      const state = playing ? 'playing' : 'paused'
      if (file !== lastFile || state !== lastState) send(state)
    }
  )
  watch(player.currentTime, () => {
    if (player.isPlaying.value && Date.now() - lastSent > HEARTBEAT_MS)
      send('playing')
  })
  window.addEventListener('pagehide', () => {
    if (lastFile) send('stopped')
  })
}

export function useAccount() {
  const auth = useAuth()
  return {
    searchAlbums,
    hidePublicPlaylists,
    ready,
    start,
    startPlaybackReports,
    user: auth.user,
  }
}
