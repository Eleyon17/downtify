<template>
  <div
    class="group flex h-16 items-center gap-3 rounded-[12px] px-3 transition-colors hover:bg-surface-2/60"
  >
    <button
      type="button"
      class="relative shrink-0 overflow-hidden rounded-[8px]"
      :aria-label="play.playLabel.value"
      :disabled="!play.playable.value"
      @click.stop="play.toggle()"
    >
      <CoverArt
        :src="song.cover_url"
        :name="song.album_name || song.name"
        rounded="rounded-[8px]"
        :letter-size="14"
        class="size-11"
      />
      <span
        v-if="play.playable.value"
        class="absolute inset-0 flex items-center justify-center bg-black/45 text-white transition-opacity"
        :class="
          play.isCurrent.value
            ? 'opacity-100'
            : 'opacity-0 group-hover:opacity-100'
        "
      >
        <AppIcon
          v-if="play.loading.value"
          name="refresh"
          :size="16"
          class="animate-spin"
        />
        <AppIcon v-else :name="overlayIcon" :size="16" />
      </span>
    </button>

    <div class="min-w-0 flex-1">
      <p class="truncate text-sm font-semibold text-fg">{{ song.name }}</p>
      <p class="truncate text-[13px] text-muted">{{ artistName }}</p>
    </div>

    <span
      v-if="song.album_name"
      class="hidden w-[28%] truncate text-[13px] text-muted md:block"
    >
      {{ song.album_name }}
    </span>

    <span
      class="tabular hidden w-12 text-right text-[13px] text-muted sm:block"
    >
      {{ song.duration ? formatDuration(song.duration) : '' }}
    </span>

    <!-- Action buttons: Add to playlist & Dismiss -->
    <div class="flex shrink-0 items-center gap-1.5 sm:gap-2">
      <!-- Add to playlist button -->
      <button
        type="button"
        class="inline-flex h-9 items-center justify-center gap-1.5 rounded-full px-2.5 text-xs font-medium transition-colors sm:px-3"
        :class="
          state === 'added'
            ? 'bg-accent/15 text-accent'
            : state === 'adding'
              ? 'cursor-wait bg-surface-3 text-muted'
              : 'bg-surface-2 text-fg hover:bg-accent hover:text-on-accent'
        "
        :disabled="state === 'adding' || state === 'added'"
        :title="t('playlists.suggestionsAddToPlaylist')"
        :aria-label="t('playlists.suggestionsAddToPlaylist')"
        @click="handleAdd"
      >
        <AppIcon
          v-if="state === 'adding'"
          name="refresh"
          :size="15"
          class="animate-spin"
        />
        <AppIcon v-else-if="state === 'added'" name="check" :size="15" />
        <AppIcon v-else name="plus" :size="15" />
        <span class="hidden sm:inline">
          {{
            state === 'added'
              ? t('playlists.suggestionsAdded')
              : t('playlists.suggestionsAddToPlaylist')
          }}
        </span>
      </button>

      <!-- Dismiss button -->
      <button
        type="button"
        class="flex size-9 items-center justify-center rounded-full text-muted transition-colors hover:bg-surface-3 hover:text-fg"
        :title="t('playlists.suggestionsDismiss')"
        :aria-label="t('playlists.suggestionsDismiss')"
        @click="handleDismiss"
      >
        <AppIcon name="x" :size="16" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import AppIcon from '/src/components/ui/AppIcon.vue'
import CoverArt from '/src/components/ui/CoverArt.vue'
import { formatDuration } from '/src/lib/format'
import { useSongPlay } from '/src/model/songPlay'
import { usePlayer } from '/src/model/player'
import { useLibrary } from '/src/model/library'
import { useDownloadManager } from '/src/model/download'
import { useUi } from '/src/model/ui'
import { useI18n } from '/src/i18n'
import API from '/src/model/api'

const props = defineProps({
  song: { type: Object, required: true },
  playlist: { type: Object, required: true },
  songs: { type: Array, default: () => [] },
  index: { type: Number, default: 0 },
})

const emit = defineEmits(['dismiss', 'added'])

const { t } = useI18n()
const player = usePlayer()
const library = useLibrary()
const dm = useDownloadManager()
const ui = useUi()

const state = ref('idle')

const artistName = computed(
  () =>
    (props.song.artists || []).join(', ') ||
    props.song.artist ||
    t('common.unknownArtist')
)

const play = useSongPlay(props)
const overlayIcon = computed(() =>
  play.isCurrent.value && player.isPlaying.value ? 'pause' : 'play'
)

async function handleAdd() {
  if (state.value === 'adding' || state.value === 'added') return
  state.value = 'adding'
  const plName = props.playlist.title || props.playlist.name

  try {
    const isLocal =
      props.song.in_library ||
      library.hasSong(artistName.value, props.song.name)
    const localTrack = isLocal
      ? library.findTrack(artistName.value, props.song.name)
      : null

    if (localTrack?.file || props.song.file) {
      // Track is already in local library: add file directly
      await API.addTrackToPlaylist(plName, props.song.file || localTrack.file)
      state.value = 'added'
      library.loadPlaylistTracks(props.playlist.name)
      emit('added', props.song)
    } else {
      // Track needs downloading on the server
      const res = await dm.download({
        ...props.song,
        playlist_name: plName,
        downtify_playlist_name: plName,
      })
      if (res?.filename) {
        state.value = 'added'
        library.loadPlaylistTracks(props.playlist.name)
        emit('added', props.song)
      } else {
        state.value = 'idle'
      }
    }
  } catch (err) {
    state.value = 'idle'
    ui.toast(
      err?.response?.data?.detail || err?.message || 'Failed adding song'
    )
  }
}

function handleDismiss() {
  emit('dismiss', props.song)
}
</script>
