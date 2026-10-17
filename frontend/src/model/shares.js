// Reactive store for creating and viewing persistent share links.
import { ref } from 'vue'
import API from '/src/model/api'
import { useUi } from '/src/model/ui'
import { useI18n } from '/src/i18n'

const shareModalOpen = ref(false)
const currentShare = ref(null)
const sharing = ref(false)

async function copyToClipboard(text) {
  if (!text) return false
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // Fallback below
  }
  try {
    const input = document.createElement('textarea')
    input.value = text
    input.style.position = 'fixed'
    input.style.opacity = '0'
    document.body.appendChild(input)
    input.focus()
    input.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(input)
    return ok
  } catch {
    return false
  }
}

export function useShares() {
  const ui = useUi()
  const { t } = useI18n()

  async function shareTrack(track) {
    if (!track?.file) return
    sharing.value = true
    try {
      const res = await API.createShare({
        kind: 'track',
        target: track.file,
        title: track.title || '',
      })
      const shareData = res.data
      currentShare.value = shareData
      shareModalOpen.value = true
      const copied = await copyToClipboard(shareData.url)
      if (copied) {
        ui.toast(t('share.copied'), { kind: 'success' })
      }
      return shareData
    } catch (err) {
      ui.toast(err?.response?.data?.detail || t('toast.actionFailed'), {
        kind: 'error',
      })
    } finally {
      sharing.value = false
    }
  }

  async function sharePlaylist(playlist) {
    const name = playlist?.name || playlist?.title
    if (!name) return
    sharing.value = true
    try {
      const res = await API.createShare({
        kind: 'playlist',
        target: playlist.name,
        title: playlist.title || playlist.name,
      })
      const shareData = res.data
      currentShare.value = shareData
      shareModalOpen.value = true
      const copied = await copyToClipboard(shareData.url)
      if (copied) {
        ui.toast(t('share.copied'), { kind: 'success' })
      }
      return shareData
    } catch (err) {
      ui.toast(err?.response?.data?.detail || t('toast.actionFailed'), {
        kind: 'error',
      })
    } finally {
      sharing.value = false
    }
  }

  function closeShareModal() {
    shareModalOpen.value = false
  }

  return {
    shareModalOpen,
    currentShare,
    sharing,
    shareTrack,
    sharePlaylist,
    copyToClipboard,
    closeShareModal,
  }
}
