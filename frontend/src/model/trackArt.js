// Which track the "Change Track Art" dialog is open for (one at a time, for
// the whole app - see TrackArtModal in AppShell).
import { ref } from 'vue'

const track = ref(null)

function open(next) {
  track.value = next
}

function close() {
  track.value = null
}

export function useTrackArt() {
  return { track, open, close }
}
