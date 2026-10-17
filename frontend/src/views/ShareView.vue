<template>
  <div class="flex min-h-dvh flex-col bg-bg text-fg">
    <!-- Clean top header -->
    <header class="flex h-16 items-center border-b border-line-2 px-4 sm:px-8">
      <div class="flex items-center gap-2.5">
        <AppLogo :size="30" />
        <span class="font-bold tracking-tight text-lg">Downtify</span>
      </div>
    </header>

    <!-- Main Content -->
    <main class="flex-1 pb-32">
      <!-- Loading State -->
      <div v-if="loading" class="flex min-h-[50vh] flex-col items-center justify-center gap-3">
        <div class="size-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        <p class="text-sm text-muted">{{ t('common.loading') }}...</p>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="mx-auto flex min-h-[50vh] max-w-md flex-col items-center justify-center gap-4 px-4 text-center">
        <div class="flex size-14 items-center justify-center rounded-2xl bg-surface-2 text-muted">
          <AppIcon name="link" :size="28" />
        </div>
        <h2 class="text-xl font-bold">{{ t('share.notFound') }}</h2>
        <p class="text-sm text-muted">
          {{ t('share.description') }}
        </p>
        <a href="/" class="mt-2 rounded-[10px] bg-accent px-4 py-2 text-sm font-semibold text-accent-fg hover:opacity-90">
          {{ t('nav.home') }}
        </a>
      </div>

      <!-- Loaded Shared Item -->
      <div v-else-if="share" class="mx-auto max-w-4xl px-4 py-8 sm:px-8">
        <!-- Hero Section -->
        <div class="flex flex-col items-center gap-6 text-center sm:flex-row sm:items-end sm:text-left">
          <div class="relative size-44 shrink-0 overflow-hidden rounded-[18px] border border-line-3 bg-surface-2 shadow-2xl sm:size-52">
            <img
              v-if="share.has_cover && share.cover_url"
              :src="share.cover_url"
              :alt="share.title"
              class="h-full w-full object-cover"
              @error="onCoverError"
            />
            <div v-else class="flex h-full w-full items-center justify-center bg-surface-2 text-muted">
              <AppIcon :name="share.kind === 'playlist' ? 'playlist' : 'music'" :size="48" />
            </div>
          </div>

          <div class="flex min-w-0 flex-1 flex-col gap-2">
            <div class="flex items-center justify-center gap-2 sm:justify-start">
              <span class="rounded-full bg-surface-2 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider text-accent">
                {{ share.kind === 'playlist' ? t('share.titlePlaylist') : t('share.titleTrack') }}
              </span>
            </div>
            <h1 class="text-2xl font-bold tracking-tight sm:text-4xl text-fg break-words">
              {{ share.title }}
            </h1>
            <p class="text-sm text-muted">
              {{ subtitle }}
            </p>

            <div class="mt-4 flex flex-wrap items-center justify-center gap-3 sm:justify-start">
              <UiButton
                variant="primary"
                :icon="isCurrentPlaying ? 'pause' : 'play'"
                size="lg"
                class="min-w-[120px]"
                @click="togglePlay"
              >
                {{ isCurrentPlaying ? t('actions.pause') : t('actions.play') }}
              </UiButton>
            </div>
          </div>
        </div>

        <!-- Queue / Tracks Section -->
        <div class="mt-12">
          <div class="mb-4 flex items-center justify-between">
            <div>
              <h2 class="text-lg font-bold">{{ t('share.queue') }}</h2>
              <p class="text-xs text-muted">
                {{ shareTracks.length }} {{ shareTracks.length === 1 ? 'track' : 'tracks' }}
              </p>
            </div>
          </div>

          <div class="flex flex-col gap-1.5 rounded-[16px] border border-line-2 bg-surface-1 p-2 sm:p-3">
            <div
              v-for="(track, idx) in shareTracks"
              :key="track.file || idx"
              class="group flex items-center gap-3 rounded-[10px] px-3 py-2 text-sm transition-colors hover:bg-surface-2"
              :class="{ 'bg-surface-2': isPlayingThis(idx) }"
            >
              <!-- Track index (desktop) -->
              <span class="tabular w-5 text-center text-xs text-muted max-sm:hidden">
                {{ idx + 1 }}
              </span>

              <!-- Album Art thumbnail with Play / EqBars Overlay -->
              <button
                type="button"
                class="relative size-10 shrink-0 overflow-hidden rounded-[8px] focus:outline-none"
                :aria-label="isPlayingThis(idx) && player.isPlaying.value ? t('actions.pause') : t('actions.play')"
                @click="playTrack(idx)"
              >
                <CoverArt
                  :src="track.cover"
                  :name="track.album || track.title"
                  rounded="rounded-[8px]"
                  :letter-size="12"
                  :icon-size="14"
                  class="size-10"
                />
                <span
                  class="absolute inset-0 flex items-center justify-center bg-black/50 text-white transition-opacity"
                  :class="isPlayingThis(idx) ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'"
                >
                  <EqBars v-if="isPlayingThis(idx) && player.isPlaying.value" :size="12" />
                  <AppIcon
                    v-else
                    :name="isPlayingThis(idx) && player.isPlaying.value ? 'pause' : 'play'"
                    :size="15"
                  />
                </span>
              </button>

              <!-- Track info -->
              <div class="min-w-0 flex-1 cursor-pointer" @click="playTrack(idx)">
                <p
                  class="truncate font-medium text-sm"
                  :class="isPlayingThis(idx) ? 'text-accent font-semibold' : 'text-fg'"
                >
                  {{ track.title }}
                </p>
                <p class="truncate text-xs text-muted">
                  {{ track.artist || track.album }}
                </p>
              </div>

              <!-- Duration -->
              <span class="shrink-0 text-xs text-muted font-mono">
                {{ formatDuration(track.duration) }}
              </span>

              <!-- Queue Actions: Move Up / Down, Remove -->
              <div class="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  :disabled="idx === 0"
                  class="flex size-7 items-center justify-center rounded text-muted hover:text-fg disabled:opacity-20"
                  title="Move Up"
                  @click.stop="moveTrack(idx, idx - 1)"
                >
                  <AppIcon name="chevron-up" :size="15" />
                </button>
                <button
                  type="button"
                  :disabled="idx === shareTracks.length - 1"
                  class="flex size-7 items-center justify-center rounded text-muted hover:text-fg disabled:opacity-20"
                  title="Move Down"
                  @click.stop="moveTrack(idx, idx + 1)"
                >
                  <AppIcon name="chevron-down" :size="15" />
                </button>
                <button
                  type="button"
                  class="flex size-7 items-center justify-center rounded text-muted hover:text-danger"
                  :title="t('share.removeFromQueue')"
                  @click.stop="removeTrack(idx)"
                >
                  <AppIcon name="close" :size="14" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- Persistent Bottom Music Player -->
    <footer
      v-if="currentPlayingTrack"
      class="fixed inset-x-2 bottom-2 z-50 rounded-[18px] border border-line-3 bg-glass p-3 shadow-float backdrop-blur-xl md:inset-x-6 md:bottom-5 md:p-4"
    >
      <!-- Progress Bar (Scrubber) -->
      <div class="mb-2 flex items-center gap-3">
        <span class="text-xs font-mono text-muted w-10 text-right">
          {{ formatDuration(scrub ?? player.currentTime.value) }}
        </span>
        <div class="flex-1">
          <SliderBar
            :model-value="scrub ?? player.currentTime.value"
            :max="player.duration.value || 1"
            :label="t('player.seek')"
            :value-text="formatDuration(player.currentTime.value)"
            :hit-height="16"
            :playing="player.isPlaying.value"
            fill-class="bg-accent"
            thumb-class="bg-accent"
            @update:model-value="(v) => (scrub = v)"
            @commit="commitSeek"
          />
        </div>
        <span class="text-xs font-mono text-muted w-10">
          {{ formatDuration(player.duration.value) }}
        </span>
      </div>

      <div class="flex items-center justify-between gap-3">
        <!-- Track info & cover -->
        <div class="flex min-w-0 flex-1 items-center gap-3 md:max-w-xs">
          <CoverArt
            :src="currentPlayingTrack.cover"
            :name="currentPlayingTrack.album || currentPlayingTrack.title"
            rounded="rounded-[10px]"
            :letter-size="14"
            class="size-11 shrink-0"
          />
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-semibold text-fg">{{ currentPlayingTrack.title }}</p>
            <p class="truncate text-xs text-muted">{{ currentPlayingTrack.artist || currentPlayingTrack.album }}</p>
          </div>
        </div>

        <!-- Center Controls: Prev, Play/Pause, Next -->
        <div class="flex items-center gap-2 sm:gap-3">
          <UiIconButton
            icon="prev"
            :label="t('player.previous')"
            @click="player.prev()"
          />
          <button
            type="button"
            class="flex size-11 items-center justify-center rounded-full bg-accent text-accent-fg shadow hover:scale-105 active:scale-95 transition-transform"
            :aria-label="player.isPlaying.value ? t('actions.pause') : t('actions.play')"
            @click="player.toggle()"
          >
            <AppIcon :name="player.isPlaying.value ? 'pause' : 'play'" :size="20" />
          </button>
          <UiIconButton
            icon="next"
            :label="t('player.next')"
            @click="player.next()"
          />
        </div>

        <!-- Right side: Cast & Volume -->
        <div class="flex items-center gap-2 md:w-48 justify-end">
          <UiIconButton
            :icon="cast.isConnected.value ? 'cast-connected' : 'cast'"
            :label="cast.isConnected.value ? t('player.castingTo', { device: cast.deviceName.value }) : t('player.cast')"
            :active="cast.isConnected.value"
            @click="cast.toggleCast()"
          />
          <div class="hidden items-center gap-2 md:flex flex-1">
            <UiIconButton
              :icon="player.isMuted.value || player.volume.value === 0 ? 'volume-x' : 'volume-2'"
              :label="t('player.mute')"
              @click="player.toggleMute()"
            />
            <div class="flex-1">
              <SliderBar
                :model-value="player.isMuted.value ? 0 : player.volume.value"
                :max="1"
                :step="0.05"
                :label="t('player.volume')"
                fill-class="bg-fg group-hover:bg-accent"
                thumb-class="bg-fg"
                @update:model-value="player.setVolume"
                @commit="player.setVolume"
              />
            </div>
          </div>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import API from '/src/model/api'
import AppIcon from '/src/components/ui/AppIcon.vue'
import AppLogo from '/src/components/ui/AppLogo.vue'
import CoverArt from '/src/components/ui/CoverArt.vue'
import UiButton from '/src/components/ui/UiButton.vue'
import UiIconButton from '/src/components/ui/UiIconButton.vue'
import SliderBar from '/src/components/player/SliderBar.vue'
import EqBars from '/src/components/ui/EqBars.vue'
import { usePlayer } from '/src/model/player'
import { useCast } from '/src/model/cast'
import { formatDuration } from '/src/lib/format'
import { useI18n } from '/src/i18n'

const route = useRoute()
const { t } = useI18n()
const player = usePlayer()
const cast = useCast()

const loading = ref(true)
const error = ref('')
const share = ref(null)
const scrub = ref(null)

const shareTracks = computed(() => {
  return player.playlist.value
})

const currentPlayingTrack = computed(() => {
  if (player.currentIndex.value >= 0 && player.playlist.value.length) {
    return player.playlist.value[player.currentIndex.value]
  }
  return null
})

const isCurrentPlaying = computed(() => {
  return player.isPlaying.value && player.currentIndex.value >= 0
})

const subtitle = computed(() => {
  if (!share.value) return ''
  if (share.value.kind === 'track') {
    const t0 = share.value.tracks?.[0]
    return [t0?.artist, t0?.album].filter(Boolean).join(' · ')
  }
  const count = share.value.count || share.value.tracks?.length || 0
  const totalSecs = (share.value.tracks || []).reduce(
    (sum, tr) => sum + (tr.duration || 0),
    0
  )
  const durationText = totalSecs > 0 ? ` · ${formatDuration(totalSecs)}` : ''
  return `${count} ${count === 1 ? 'track' : 'tracks'}${durationText}`
})

function isPlayingThis(idx) {
  return player.currentIndex.value === idx
}

function commitSeek(sec) {
  player.seek(sec)
  scrub.value = null
}

function onCoverError(evt) {
  if (evt.target) {
    evt.target.style.display = 'none'
  }
}

function playTrack(idx) {
  if (player.currentIndex.value === idx) {
    player.toggle()
  } else {
    player.playAt(idx)
  }
}

function togglePlay() {
  if (player.isPlaying.value) {
    player.pause()
  } else if (player.currentIndex.value >= 0) {
    player.play()
  } else if (shareTracks.value.length > 0) {
    player.playAt(0)
  }
}

function moveTrack(from, to) {
  player.moveTrack(from, to)
}

function removeTrack(idx) {
  player.removeAt(idx)
}

onMounted(async () => {
  const shareId = route.params.id
  if (!shareId) {
    error.value = 'No share id provided'
    loading.value = false
    return
  }
  try {
    const res = await API.getPublicShare(shareId)
    share.value = res.data

    // Normalize track items for player
    const tracks = (res.data.tracks || []).map((tr) => ({
      title: tr.title,
      artist: tr.artist,
      album: tr.album,
      duration: tr.duration || 0,
      hasCover: tr.has_cover,
      cover: tr.cover_url,
      url: tr.stream_url,
      file: `share:${shareId}:${tr.index}`,
    }))

    // Load into player without autoplaying
    player.setPlaylist(tracks, { autoplay: false, context: { type: 'share', title: res.data.title } })
  } catch (err) {
    error.value = err?.response?.data?.detail || 'Share not found'
  } finally {
    loading.value = false
  }
})
</script>
