// Player display preferences. Remembered in this browser, like the theme,
// and kept with the signed-in account (see model/account.js).
import { useLocalStorage } from '@vueuse/core'

// Only hides the lyrics; the files keep the ones Downtify embedded, and
// "Download lyrics" (a server setting) is untouched.
const showLyrics = useLocalStorage('downtify-show-lyrics', true)
const translateLyrics = useLocalStorage('downtify-translate-lyrics', true)

export function usePlayerPrefs() {
  return { showLyrics, translateLyrics }
}
