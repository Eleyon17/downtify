// Google Cast & Remote Playback integration for web browsers / PC.
import { ref, watch } from 'vue'
import { usePlayer } from './player'

const isAvailable = ref(true) // Show cast control in Chromium / Cast-capable environments
const isConnected = ref(false)
const isConnecting = ref(false)
const deviceName = ref('')
const castType = ref(null) // 'chromecast' | 'remote-playback' | null

let castSession = null
let initialized = false

function initGoogleCast() {
  if (typeof window === 'undefined') return
  if (window.cast?.framework) {
    try {
      const context = window.cast.framework.CastContext.getInstance()
      context.setOptions({
        receiverApplicationId:
          window.chrome?.cast?.media?.DEFAULT_MEDIA_RECEIVER_APP_ID ||
          'CC1AD845',
        autoJoinPolicy:
          window.chrome?.cast?.AutoJoinPolicy?.ORIGIN_SCOPED || 'origin_scoped',
      })
      isAvailable.value = true

      context.addEventListener(
        window.cast.framework.CastContextEventType.SESSION_STATE_CHANGED,
        (event) => {
          const state = event.sessionState
          const SessionState = window.cast.framework.SessionState
          if (
            state === SessionState.SESSION_STARTED ||
            state === SessionState.SESSION_RESUMED
          ) {
            castSession = context.getCurrentSession()
            isConnected.value = true
            isConnecting.value = false
            castType.value = 'chromecast'
            deviceName.value =
              castSession?.getCastDevice()?.friendlyName || 'Chromecast'
            syncMediaToCast()
          } else if (
            state === SessionState.SESSION_STARTING ||
            state === SessionState.SESSION_RESUMING
          ) {
            isConnecting.value = true
          } else if (state === SessionState.SESSION_ENDED) {
            castSession = null
            isConnected.value = false
            isConnecting.value = false
            castType.value = null
            deviceName.value = ''
          }
        }
      )
    } catch {
      // Cast SDK might not be initialized yet
    }
  }
}

function initRemotePlayback() {
  if (typeof window === 'undefined') return
  try {
    const player = usePlayer()
    const audio = player.getAudio()
    if (audio?.remote) {
      isAvailable.value = true
      audio.remote.addEventListener('connecting', () => {
        isConnecting.value = true
      })
      audio.remote.addEventListener('connect', () => {
        isConnected.value = true
        isConnecting.value = false
        castType.value = 'remote-playback'
        deviceName.value = 'Cast Device'
      })
      audio.remote.addEventListener('disconnect', () => {
        isConnected.value = false
        isConnecting.value = false
        castType.value = null
        deviceName.value = ''
      })
      if (typeof audio.remote.watchAvailability === 'function') {
        audio.remote
          .watchAvailability((avail) => {
            if (avail) isAvailable.value = true
          })
          .catch(() => {
            isAvailable.value = true
          })
      }
    }
  } catch {
    // Ignore
  }
}

function syncMediaToCast() {
  if (!castSession || typeof window === 'undefined') return
  const player = usePlayer()
  const track = player.currentTrack.value
  if (!track || !track.url) return

  try {
    const fullUrl = track.url.startsWith('http')
      ? track.url
      : `${window.location.origin}${track.url}`
    const fullCover = track.cover?.startsWith('http')
      ? track.cover
      : track.cover
        ? `${window.location.origin}${track.cover}`
        : ''

    const mediaInfo = new window.chrome.cast.media.MediaInfo(
      fullUrl,
      'audio/mpeg'
    )
    mediaInfo.metadata = new window.chrome.cast.media.MusicTrackMediaMetadata()
    mediaInfo.metadata.title = track.title || 'Track'
    mediaInfo.metadata.artist = track.artist || ''
    mediaInfo.metadata.albumName = track.album || ''
    if (fullCover) {
      mediaInfo.metadata.images = [{ url: fullCover }]
    }

    const request = new window.chrome.cast.media.LoadRequest(mediaInfo)
    request.autoplay = player.isPlaying.value
    request.currentTime = player.currentTime.value || 0

    castSession.loadMedia(request).then(
      () => {},
      () => {}
    )
  } catch {
    // Cast load failed or not available
  }
}

export function useCast() {
  if (!initialized && typeof window !== 'undefined') {
    initialized = true

    // Detect Google Cast
    if (window.__onGCastApiAvailable) {
      const prev = window.__onGCastApiAvailable
      window.__onGCastApiAvailable = (isAvail) => {
        prev(isAvail)
        if (isAvail) initGoogleCast()
      }
    } else {
      window.__onGCastApiAvailable = (isAvail) => {
        if (isAvail) initGoogleCast()
      }
    }
    if (window.cast?.framework) {
      initGoogleCast()
    }

    // Also check RemotePlayback API
    initRemotePlayback()

    // Watch track changes when casting via Google Cast
    try {
      const player = usePlayer()
      watch(player.currentTrack, (newTrack) => {
        if (isConnected.value && castType.value === 'chromecast' && newTrack) {
          syncMediaToCast()
        }
      })
    } catch {
      // ignore
    }
  }

  async function requestCast() {
    // Try Google Cast SDK first
    if (window.cast?.framework) {
      try {
        const context = window.cast.framework.CastContext.getInstance()
        await context.requestSession()
        return
      } catch (err) {
        if (err !== 'cancel' && err?.message !== 'cancel') {
          // Fall through to remote playback
        }
      }
    }

    // Try Remote Playback API
    const player = usePlayer()
    const audio = player.getAudio()
    if (audio?.remote && typeof audio.remote.prompt === 'function') {
      try {
        await audio.remote.prompt()
        return
      } catch {
        // prompt canceled or failed
      }
    }

    // If neither succeeds, let the user know Cast is built-in to Chrome / Edge
    if (typeof window !== 'undefined' && !isAvailable.value) {
      window.alert(
        'Cast device picker can be opened from your browser menu: Cast / Media Output.'
      )
    }
  }

  function disconnect() {
    if (castSession && window.cast?.framework) {
      try {
        window.cast.framework.CastContext.getInstance().endCurrentSession(true)
      } catch {
        // ignore
      }
    }
    castSession = null
    isConnected.value = false
    isConnecting.value = false
    castType.value = null
    deviceName.value = ''
  }

  function toggleCast() {
    if (isConnected.value) {
      disconnect()
    } else {
      requestCast()
    }
  }

  return {
    isAvailable,
    isConnected,
    isConnecting,
    deviceName,
    castType,
    requestCast,
    disconnect,
    toggleCast,
  }
}
