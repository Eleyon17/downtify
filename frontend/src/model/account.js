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
import { addPlayed } from '/src/lib/discover'
import { useAuth } from '/src/model/auth'
import { usePlayer } from '/src/model/player'
import { usePlayerPrefs } from '/src/model/playerPrefs'
import { useTheme } from '/src/model/theme'

const searchAlbums = ref(true)
const hidePublicPlaylists = ref(true)
const sidebarDiscovery = ref(true)
const sidebarMonitor = ref(true)
const sidebarPodcasts = ref(true)
const sidebarCharts = ref(true)
const sidebarSimilar = ref(true)
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
    sidebar_discovery: sidebarDiscovery.value,
    sidebar_monitor: sidebarMonitor.value,
    sidebar_podcasts: sidebarPodcasts.value,
    sidebar_charts: sidebarCharts.value,
    sidebar_similar: sidebarSimilar.value,
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
  if (typeof prefs.sidebar_discovery === 'boolean')
    sidebarDiscovery.value = prefs.sidebar_discovery
  if (typeof prefs.sidebar_monitor === 'boolean')
    sidebarMonitor.value = prefs.sidebar_monitor
  if (typeof prefs.sidebar_podcasts === 'boolean')
    sidebarPodcasts.value = prefs.sidebar_podcasts
  if (typeof prefs.sidebar_charts === 'boolean')
    sidebarCharts.value = prefs.sidebar_charts
  if (typeof prefs.sidebar_similar === 'boolean')
    sidebarSimilar.value = prefs.sidebar_similar
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
      sidebarDiscovery,
      sidebarMonitor,
      sidebarPodcasts,
      sidebarCharts,
      sidebarSimilar,
    ],
    () => save(),
    {
      flush: 'post',
    }
  )
}

// ── Playback reports ──────────────────────────────────────────────────
const HEARTBEAT_MS = 15000
const MIN_COUNTED_SECONDS = 15
let reporting = false

function minRequiredSeconds(duration) {
  const dur = Number(duration) || 0
  return dur > 0 ? Math.min(MIN_COUNTED_SECONDS, Math.max(5, dur * 0.5)) : MIN_COUNTED_SECONDS
}

function startPlaybackReports() {
  if (reporting) return
  reporting = true
  const player = usePlayer()
  let lastSent = 0
  let lastState = ''
  let lastFile = ''
  let lastTrack = null
  let lastPosition = 0
  let maxPosition = 0
  let playedSeconds = 0
  let thresholdReported = false

  function send(state, { trackOverride = null, listenedOverride = null, skipped = false, posOverride = null } = {}) {
    const track = trackOverride || player.currentTrack.value
    const enrichedTrack = track
      ? {
          ...track,
          duration: Number(track.duration || player.duration.value) || 0,
        }
      : track
    const listenedVal = listenedOverride !== null ? listenedOverride : playedSeconds
    const posVal = posOverride !== null ? posOverride : player.currentTime.value
    const report = playbackReport(enrichedTrack, {
      player: API.clientId,
      state,
      position: posVal,
      listened: listenedVal,
      skipped,
    })
    if (!report) return
    lastSent = Date.now()
    if (!trackOverride) {
      lastState = state
      lastFile = track?.file || ''
      lastTrack = enrichedTrack
    }
    API.reportPlayback(report).catch(() => {
      // Best effort: feeds Activity & Listening Stats.
    })
  }

  function flushPreviousTrack() {
    if (!lastFile || !lastTrack) return
    const reqSec = minRequiredSeconds(lastTrack.duration)
    const wasSkipped = playedSeconds < reqSec
    if (wasSkipped) {
      send('stopped', {
        trackOverride: lastTrack,
        listenedOverride: playedSeconds,
        skipped: true,
        posOverride: lastPosition,
      })
    } else {
      send('paused', {
        trackOverride: lastTrack,
        listenedOverride: playedSeconds,
        skipped: false,
        posOverride: lastPosition,
      })
    }
  }

  watch(
    () => [player.currentTrack.value?.file, player.isPlaying.value],
    ([file, playing]) => {
      if (!file) {
        if (lastFile) {
          flushPreviousTrack()
          send('stopped', { listenedOverride: playedSeconds })
        }
        lastFile = ''
        lastTrack = null
        lastPosition = 0
        maxPosition = 0
        playedSeconds = 0
        thresholdReported = false
        return
      }
      if (file !== lastFile) {
        if (lastFile) {
          flushPreviousTrack()
        }
        lastPosition = Number(player.currentTime.value) || 0
        maxPosition = lastPosition
        playedSeconds = 0
        thresholdReported = false
      }
      const state = playing ? 'playing' : 'paused'
      if (file !== lastFile || state !== lastState) send(state)
    }
  )
  watch(player.currentTime, (now) => {
    const pos = Number(now) || 0
    if (player.isPlaying.value && maxPosition >= 30 && pos < 2 && lastPosition > pos) {
      // Track looped / restarted from beginning: flush completed play and start fresh
      flushPreviousTrack()
      lastPosition = pos
      maxPosition = pos
      playedSeconds = 0
      thresholdReported = false
      send('playing', { posOverride: 0, listenedOverride: 0 })
      return
    }
    playedSeconds = addPlayed(playedSeconds, lastPosition, pos)
    lastPosition = pos
    if (pos > maxPosition) maxPosition = pos

    const curDur = Number(player.currentTrack.value?.duration || player.duration.value) || 0
    const reqSec = minRequiredSeconds(curDur)
    if (!thresholdReported && playedSeconds >= reqSec) {
      thresholdReported = true
      send(player.isPlaying.value ? 'playing' : 'paused')
      return
    }
    if (player.isPlaying.value && Date.now() - lastSent >= HEARTBEAT_MS) {
      send('playing')
    }
  })
  window.addEventListener('pagehide', () => {
    if (lastFile) {
      flushPreviousTrack()
      send('stopped')
    }
  })
}

export function useAccount() {
  const auth = useAuth()
  return {
    searchAlbums,
    hidePublicPlaylists,
    sidebarDiscovery,
    sidebarMonitor,
    sidebarPodcasts,
    sidebarCharts,
    sidebarSimilar,
    ready,
    start,
    startPlaybackReports,
    user: auth.user,
  }
}
