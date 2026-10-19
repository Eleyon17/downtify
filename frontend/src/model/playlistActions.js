// Actions for downloaded playlists (library + Spotify download tracking)
// and for playlists the user creates in the Library.
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import API from '/src/model/api'
import monitorAPI from '/src/model/monitor'
import { syncQueueFromServer } from '/src/model/download'
import { useLibrary } from '/src/model/library'
import { useLikes } from '/src/model/likes'
import { useTrackActions } from '/src/model/trackActions'
import { useUi } from '/src/model/ui'
import { usePlayer } from '/src/model/player'
import { useHistory } from '/src/model/history'
import { useI18n } from '/src/i18n'
import { itemTrackCount } from '/src/lib/library'
import { useShares } from '/src/model/shares'

const createOpen = ref(false)
const createFiles = ref([])
const addOpen = ref(false)
const addPlaylist = ref(null)
const renameOpen = ref(false)
const renamePlaylist = ref(null)

export function usePlaylistActions() {
  const library = useLibrary()
  const likes = useLikes()
  const tracks = useTrackActions()
  const shares = useShares()
  const ui = useUi()
  const player = usePlayer()
  const history = useHistory()
  const router = useRouter()
  const { t } = useI18n()

  function contextFor(playlist) {
    return {
      type: 'playlist',
      title: playlist.title,
      cover: playlist.cover || '',
      covers: playlist.covers || [],
      route: { name: 'Playlist', query: { name: playlist.name } },
      manual: Boolean(playlist.manual),
      canEdit: Boolean(playlist.canEdit),
      isOwner: Boolean(playlist.isOwner),
      playlistName: playlist.name,
    }
  }

  async function play(playlist, options = {}) {
    await library.loadPlaylistTracks(playlist.name)
    const live = library.findPlaylist(playlist.name) || playlist
    tracks.play(live.tracks, 0, contextFor(live), options)
  }

  function manuals() {
    return library.playlists.value.filter(
      (item) => item.manual && item.isOwner
    )
  }

  function editables() {
    return library.playlists.value.filter(
      (item) => item.canEdit && !item.liked
    )
  }

  function openCreate(files = []) {
    createFiles.value = files.map((item) =>
      typeof item === 'string' ? item : item.file
    )
    createOpen.value = true
  }

  function openAddSongs(playlist) {
    addPlaylist.value = playlist
    addOpen.value = true
  }

  function openRename(playlist) {
    renamePlaylist.value = playlist
    renameOpen.value = true
  }

  async function createNamed(name, files = []) {
    try {
      const res = await API.createLibraryPlaylist(name)
      const created = res.data?.name || name
      if (files.length) {
        await API.editLibraryPlaylistTracks(created, { add: files })
      }
      await library.load({ force: true })
      ui.toast(t('playlists.created', { name: created }), { kind: 'success' })
      return created
    } catch (err) {
      ui.toast(err?.response?.data?.detail || t('toast.actionFailed'), {
        kind: 'error',
      })
      throw err
    }
  }

  async function renameNamed(playlist, newName) {
    try {
      const res = await API.renameLibraryPlaylist(playlist.name, newName)
      const renamed = res.data?.name || newName
      const previous = playlist.name
      history.retitlePlaylist(previous, renamed)
      const ctx = player.context.value
      if (
        ctx?.type === 'playlist' &&
        (ctx.playlistName === previous ||
          ctx.title === previous ||
          ctx.route?.query?.name === previous)
      ) {
        player.context.value = {
          ...ctx,
          title: renamed,
          playlistName: renamed,
          route: { name: 'Playlist', query: { name: renamed } },
        }
      }
      await library.load({ force: true })
      ui.toast(t('playlists.renamed', { name: renamed }), { kind: 'success' })
      return renamed
    } catch (err) {
      ui.toast(err?.response?.data?.detail || t('toast.actionFailed'), {
        kind: 'error',
      })
      throw err
    }
  }

  async function addFiles(playlist, files) {
    const names = files.map((item) =>
      typeof item === 'string' ? item : item.file
    )
    try {
      const res = await API.editLibraryPlaylistTracks(playlist.name, {
        add: names,
      })
      // The server skips what the playlist already has: report what it did.
      const added = Number(res.data?.added ?? names.length)
      await library.load({ force: true })
      ui.toast(
        added
          ? t('playlists.added', { count: added, name: playlist.title })
          : t('playlists.alreadyIn', { name: playlist.title }),
        { kind: 'success' }
      )
    } catch (err) {
      ui.toast(err?.response?.data?.detail || t('toast.actionFailed'), {
        kind: 'error',
      })
    }
  }

  async function removeFiles(playlist, files) {
    const names = files.map((item) =>
      typeof item === 'string' ? item : item.file
    )
    try {
      await API.editLibraryPlaylistTracks(playlist.name, { remove: names })
      await library.load({ force: true })
      await library.loadPlaylistTracks(playlist.name)
      ui.toast(t('playlists.removedTrack', { name: playlist.title }), {
        kind: 'success',
      })
    } catch (err) {
      ui.toast(err?.response?.data?.detail || t('toast.actionFailed'), {
        kind: 'error',
      })
    }
  }

  async function toggleVisibility(playlist) {
    const nextPublic = !playlist.public
    try {
      await API.setPlaylistVisibility(playlist.name, nextPublic)
      await library.load({ force: true })
      ui.toast(
        t(nextPublic ? 'playlists.madePublic' : 'playlists.madePrivate', {
          name: playlist.title,
        }),
        { kind: 'success' }
      )
    } catch (err) {
      ui.toast(err?.response?.data?.detail || t('toast.actionFailed'), {
        kind: 'error',
      })
    }
  }

  async function clone(playlist) {
    try {
      const res = await API.clonePlaylist(playlist.name)
      const clonedName = res.data?.name || `${playlist.name} (Copy)`
      await library.load({ force: true })
      ui.toast(t('playlists.cloned', { name: clonedName }), {
        kind: 'success',
        action: {
          label: t('likes.open'),
          run: () =>
            router.push({ name: 'Playlist', query: { name: clonedName } }),
        },
      })
      return clonedName
    } catch (err) {
      ui.toast(err?.response?.data?.detail || t('toast.actionFailed'), {
        kind: 'error',
      })
      return null
    }
  }

  async function toggleHidden(playlist) {
    const nextHidden = !playlist.hidden
    try {
      await API.hidePlaylist(playlist.name, nextHidden)
      await library.load({ force: true })
      ui.toast(
        t(nextHidden ? 'playlists.hiddenToast' : 'playlists.unhiddenToast', {
          name: playlist.title,
        }),
        { kind: 'success' }
      )
    } catch (err) {
      ui.toast(err?.response?.data?.detail || t('toast.actionFailed'), {
        kind: 'error',
      })
    }
  }

  function addMenuItems(files) {
    const list = Array.isArray(files) ? files : [files]
    const items = [
      { heading: t('playlists.addTo') },
      ...editables().map((playlist) => ({
        label: playlist.title,
        icon: 'playlist',
        action: () => addFiles(playlist, list),
      })),
      {
        label: t('playlists.new'),
        icon: 'plus',
        action: () => openCreate(list),
      },
    ]
    return items
  }

  async function downloadMissing(playlist) {
    const batch = playlist.batch
    if (!batch) return
    try {
      const res = await API.downloadMissingPlaylistTracks({
        spotify_playlist_id: batch.spotify_playlist_id,
        playlist_url: batch.playlist_url,
      })
      const count = res.data?.count || 0
      if (count) {
        ui.toast(t('toast.queuedMissing', { count }), {
          kind: 'success',
          action: {
            label: t('nav.queue'),
            run: () => router.push({ name: 'Queue' }),
          },
        })
        syncQueueFromServer().catch(() => {})
      } else {
        ui.toast(t('toast.playlistComplete'), { kind: 'success' })
      }
      library.refreshSoon(500)
    } catch (err) {
      ui.toast(err?.response?.data?.detail || t('toast.actionFailed'), {
        kind: 'error',
      })
    }
  }

  async function watch(playlist) {
    const url = playlist.batch?.playlist_url
    if (!url) return
    try {
      await monitorAPI.addMonitoredPlaylist(url, 360)
      ui.toast(t('toast.watching', { name: playlist.name }), {
        kind: 'success',
        action: {
          label: t('nav.monitor'),
          run: () =>
            router.push({ name: 'Monitor', params: { tab: 'playlists' } }),
        },
      })
    } catch (err) {
      ui.toast(err?.response?.data?.detail || t('toast.actionFailed'), {
        kind: 'error',
      })
    }
  }

  // Deleting the liked songs playlist would delete songs from disk, so it
  // only ever means "unlike everything" (the server enforces this too).
  async function removeLikes() {
    const ok = await ui.confirm({
      title: t('likes.removeAllTitle'),
      body: t('likes.removeAllBody'),
      confirmLabel: t('likes.removeAll'),
      danger: true,
    })
    if (!ok) return false
    const done = await likes.clear()
    if (done) ui.toast(t('likes.cleared'), { kind: 'success' })
    return done
  }

  async function remove(playlist) {
    if (playlist.liked) return removeLikes()
    const ok = await ui.confirm({
      title: t('confirm.deletePlaylistTitle', { name: playlist.name }),
      body: playlist.manual
        ? t('confirm.deleteManualPlaylistBody')
        : t('confirm.deletePlaylistBody'),
      confirmLabel: t('common.delete'),
      danger: true,
    })
    if (!ok) return false
    try {
      const result = await library.deletePlaylist(playlist)
      ui.toast(
        t('toast.playlistDeleted', {
          name: playlist.name,
          count: result?.deleted_count ?? 0,
        }),
        { kind: 'success' }
      )
      return true
    } catch (err) {
      ui.toast(err?.response?.data?.detail || t('toast.actionFailed'), {
        kind: 'error',
      })
      return false
    }
  }

  function menuFor(playlist, { hide = [] } = {}) {
    const batch = playlist.batch
    const empty = !itemTrackCount(playlist)
    const isOwner = Boolean(playlist.isOwner)
    const canEdit = Boolean(playlist.canEdit)
    return [
      {
        label: t('actions.play'),
        icon: 'play',
        hidden: empty,
        action: () => play(playlist),
      },
      {
        label: t('actions.shuffle'),
        icon: 'shuffle',
        hidden: empty,
        action: () => play(playlist, { shuffled: true }),
      },
      {
        label: t('actions.addToQueue'),
        icon: 'queue',
        hidden: empty,
        action: async () => {
          await library.loadPlaylistTracks(playlist.name)
          const live = library.findPlaylist(playlist.name) || playlist
          tracks.enqueue(live.tracks)
        },
      },
      { divider: true },
      {
        label: t('playlists.downloadMissing', {
          count: batch?.missing_count || 0,
        }),
        icon: 'download',
        hidden: !isOwner || !batch?.missing_count,
        action: () => downloadMissing(playlist),
      },
      {
        label: t('playlists.watch'),
        icon: 'radar',
        hidden: !isOwner || !batch?.playlist_url || hide.includes('watch'),
        action: () => watch(playlist),
      },
      {
        label: t('playlists.openSource'),
        icon: 'arrow-up-right',
        hidden: !batch?.playlist_url,
        action: () => window.open(batch.playlist_url, '_blank', 'noopener'),
      },
      {
        label: t('playlists.addSongs'),
        icon: 'plus',
        hidden: !canEdit,
        action: () => openAddSongs(playlist),
      },
      {
        label: playlist.public
          ? t('playlists.makePrivate')
          : t('playlists.makePublic'),
        icon: playlist.public ? 'lock' : 'globe',
        hidden: !isOwner || playlist.liked || playlist.monitored,
        action: () => toggleVisibility(playlist),
      },
      {
        label: t('playlists.rename'),
        icon: 'pencil',
        hidden: !isOwner || !playlist.manual,
        action: () => openRename(playlist),
      },
      {
        label: t('playlists.clone'),
        icon: 'copy',
        hidden: playlist.liked,
        action: () => clone(playlist),
      },
      {
        label: playlist.hidden ? t('playlists.unhide') : t('playlists.hide'),
        icon: 'eye',
        hidden: isOwner || playlist.liked,
        action: () => toggleHidden(playlist),
      },
      {
        label: t('library.downloadZip'),
        icon: 'zip',
        hidden: empty,
        action: () => tracks.downloadZip(playlist.tracks),
      },
      {
        label: t('actions.share'),
        icon: 'share',
        action: () => shares.sharePlaylist(playlist),
      },
      { divider: true, hidden: !isOwner && !playlist.liked },
      {
        label: playlist.liked ? t('likes.removeAll') : t('playlists.delete'),
        icon: 'trash',
        danger: true,
        hidden: !isOwner && !playlist.liked,
        action: () => remove(playlist),
      },
    ]
  }

  return {
    contextFor,
    play,
    downloadMissing,
    watch,
    remove,
    menuFor,
    manuals,
    editables,
    openCreate,
    openAddSongs,
    openRename,
     rename: openRename,
    createNamed,
    renameNamed,
    addFiles,
    removeFiles,
    toggleVisibility,
    clone,
    toggleHidden,
    addMenuItems,
    createOpen,
    createFiles,
    addOpen,
    addPlaylist,
    renameOpen,
    renamePlaylist,
  }
}
