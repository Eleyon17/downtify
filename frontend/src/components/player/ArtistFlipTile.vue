<template>
  <div
    class="relative aspect-square size-full min-h-0 min-w-0 perspective-1000 select-none"
    :class="canFlip ? 'cursor-pointer' : ''"
  >
    <!-- 3D Flippable card inner -->
    <div
      class="relative size-full transform-style-3d transition-transform duration-500 ease-out-soft"
      :class="isFlipped ? 'rotate-y-180' : ''"
    >
      <!-- FRONT: Cover Art -->
      <div
        class="absolute inset-0 size-full backface-hidden"
        :title="canFlip ? t('artistBio.title') : undefined"
        @click="onFrontClick"
      >
        <CoverArt
          :src="track.hasCover ? track.cover : ''"
          :name="track.album || track.title"
          rounded="rounded-[20px]"
          :letter-size="140"
          :icon-size="72"
          class="aspect-square size-full min-h-0 min-w-0 transition-transform duration-500 ease-out-soft"
          :class="isPlaying ? 'scale-100' : 'scale-[0.94]'"
        />

        <!-- Flip Hint Badge -->
        <button
          v-if="canFlip"
          type="button"
          class="group/flip absolute bottom-3 right-3 flex items-center gap-1.5 rounded-full bg-black/60 px-3 py-1.5 text-xs font-semibold text-white/90 shadow-lg backdrop-blur-md transition-all duration-200 hover:scale-105 hover:bg-black/80 hover:text-white"
          :aria-label="t('artistBio.title')"
          @click.stop="toggleFlip"
        >
          <AppIcon name="user" :size="14" class="text-accent" />
          <span>{{ currentArtist }}</span>
        </button>
      </div>

      <!-- BACK: Artist Bio, Popular Songs & Albums -->
      <div
        class="absolute inset-0 flex size-full rotate-y-180 flex-col overflow-hidden rounded-[20px] border border-white/15 bg-[#090b10]/95 p-3.5 text-white shadow-2xl backdrop-blur-2xl backface-hidden"
        @click.stop
      >
        <!-- Header -->
        <div class="flex shrink-0 items-center justify-between border-b border-white/10 pb-2.5">
          <div class="flex min-w-0 items-center gap-2">
            <AppIcon name="user" :size="18" class="shrink-0 text-accent" />
            <h3 class="truncate text-sm font-bold text-white">
              {{ currentArtist }}
            </h3>
          </div>
          <button
            type="button"
            class="flex size-7 shrink-0 items-center justify-center rounded-full bg-white/10 text-white/70 transition-colors hover:bg-white/20 hover:text-white"
            :aria-label="t('common.close')"
            @click="toggleFlip"
          >
            <AppIcon name="x" :size="16" />
          </button>
        </div>

        <!-- Scrollable Content -->
        <div class="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain pr-1 pt-2.5 [scrollbar-width:thin]">
          <!-- Biography Section -->
          <section>
            <div class="mb-1.5 flex items-center justify-between">
              <span class="text-[11px] font-bold tracking-wider text-accent uppercase">
                {{ t('artistBio.title') }}
              </span>
              <span
                v-if="overview?.bio_source === 'youtubemusic'"
                class="text-[10px] text-white/40 font-medium"
              >
                YouTube Music
              </span>
            </div>

            <!-- Loading Spinner -->
            <div
              v-if="loading"
              class="flex items-center justify-center py-4 text-accent"
            >
              <AppIcon name="refresh" :size="20" class="animate-spin" />
            </div>

            <!-- Bio Text -->
            <div v-else>
              <p
                v-if="overview?.bio"
                class="text-xs leading-relaxed text-white/80 whitespace-pre-line"
              >
                {{ visibleBio }}
              </p>
              <p v-else class="text-xs text-white/45 italic">
                {{ t('artistBio.empty') }}
              </p>
              <button
                v-if="hasMoreBio"
                type="button"
                class="mt-1.5 inline-block text-xs font-semibold text-accent hover:underline cursor-pointer"
                @click="bioLimit += BIO_CHUNK"
              >
                {{ t('artistBio.showMore') }}
              </button>
            </div>
          </section>

          <!-- Popular Songs Section -->
          <section v-if="overview?.top_songs?.length">
            <div class="mb-1.5 flex items-center justify-between">
              <span class="text-[11px] font-bold tracking-wider text-accent uppercase">
                {{ t('artist.topSongs') }}
              </span>
            </div>
            <div class="space-y-1">
              <div
                v-for="song in overview.top_songs"
                :key="song.video_id || song.name"
                class="group flex items-center gap-2.5 rounded-[8px] p-1.5 transition-colors hover:bg-white/10 cursor-pointer"
                @click="queueSong(song)"
              >
                <CoverArt
                  :src="song.cover_url"
                  :name="song.album_name || song.name"
                  rounded="rounded-[6px]"
                  :letter-size="12"
                  :icon-size="14"
                  class="size-9 shrink-0"
                />
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-1.5">
                    <span class="truncate text-xs font-semibold text-white">
                      {{ song.name }}
                    </span>
                    <AppIcon
                      v-if="library.hasSong(songArtist(song), song.name)"
                      name="cloud"
                      :size="12"
                      class="shrink-0 text-accent"
                      :title="t('search.inLibrary')"
                    />
                  </div>
                  <p class="truncate text-[11px] text-white/50">
                    {{ [song.album_name, song.duration ? formatDuration(song.duration) : ''].filter(Boolean).join(' · ') }}
                  </p>
                </div>
                <button
                  type="button"
                  class="flex size-7 shrink-0 items-center justify-center rounded-full text-white/50 transition-colors hover:bg-white/15 hover:text-white"
                  :title="t('actions.addToQueue')"
                  @click.stop="queueSong(song)"
                >
                  <AppIcon name="plus" :size="15" />
                </button>
              </div>
            </div>
          </section>

          <!-- Albums Section -->
          <section v-if="overview?.top_albums?.length">
            <div class="mb-1.5 flex items-center justify-between">
              <span class="text-[11px] font-bold tracking-wider text-accent uppercase">
                {{ t('search.albums') }}
              </span>
            </div>
            <div class="space-y-1">
              <div
                v-for="album in overview.top_albums"
                :key="album.album_id || album.name"
                class="group flex items-center gap-2.5 rounded-[8px] p-1.5 transition-colors hover:bg-white/10 cursor-pointer"
                @click="queueAlbum(album)"
              >
                <CoverArt
                  :src="album.cover_url"
                  :name="album.name"
                  rounded="rounded-[6px]"
                  :letter-size="12"
                  :icon-size="14"
                  class="size-9 shrink-0"
                />
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-1.5">
                    <span class="truncate text-xs font-semibold text-white">
                      {{ album.name }}
                    </span>
                    <AppIcon
                      v-if="library.findAlbum(album.artist || currentArtist, album.name)"
                      name="cloud"
                      :size="12"
                      class="shrink-0 text-accent"
                      :title="t('search.inLibrary')"
                    />
                  </div>
                  <p class="truncate text-[11px] text-white/50">
                    {{ [album.release_type, album.year].filter(Boolean).join(' · ') }}
                  </p>
                </div>
                <button
                  type="button"
                  class="flex size-7 shrink-0 items-center justify-center rounded-full text-white/50 transition-colors hover:bg-white/15 hover:text-white"
                  :title="t('actions.addToQueue')"
                  @click.stop="queueAlbum(album)"
                >
                  <AppIcon name="plus" :size="15" />
                </button>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import AppIcon from '../ui/AppIcon.vue'
import CoverArt from '../ui/CoverArt.vue'
import API from '/src/model/api'
import { useLibrary } from '/src/model/library'
import { useTrackActions } from '/src/model/trackActions'
import { songToPlayerTrack } from '/src/model/songPlay'
import { songArtist } from '/src/model/streamResolve'
import { formatDuration } from '/src/lib/format'
import { useUi } from '/src/model/ui'
import { useI18n } from '/src/i18n'

const BIO_CHUNK = 200

const props = defineProps({
  track: { type: Object, required: true },
  isPlaying: { type: Boolean, default: false },
})

const { t } = useI18n()
const library = useLibrary()
const actions = useTrackActions()
const ui = useUi()

const isFlipped = ref(false)
const loading = ref(false)
const overview = ref(null)
const bioLimit = ref(BIO_CHUNK)

// Cache overviews across artist flips
const cache = new Map()

const canFlip = computed(() => !props.track?.isPodcast && !!currentArtist.value)

const currentArtist = computed(() => {
  const tr = props.track
  if (!tr) return ''
  return tr.albumArtist || (tr.artists || [])[0] || tr.artist || ''
})

const visibleBio = computed(() => {
  const bio = overview.value?.bio || ''
  if (!bio) return ''
  return bio.length > bioLimit.value
    ? `${bio.slice(0, bioLimit.value).trimEnd()}…`
    : bio
})

const hasMoreBio = computed(() => {
  const bio = overview.value?.bio || ''
  return bio.length > bioLimit.value
})

async function fetchOverview(name) {
  if (!name) return
  if (cache.has(name)) {
    overview.value = cache.get(name)
    return
  }
  loading.value = true
  try {
    const res = await API.getArtistOverview(name)
    overview.value = res.data
    cache.set(name, res.data)
  } catch {
    overview.value = {
      name,
      channel_id: '',
      url: '',
      cover_url: '',
      bio: '',
      bio_source: '',
      top_songs: [],
      top_albums: [],
    }
  } finally {
    loading.value = false
  }
}

function onFrontClick() {
  if (!canFlip.value) return
  toggleFlip()
}

function toggleFlip() {
  if (!canFlip.value) return
  isFlipped.value = !isFlipped.value
  if (isFlipped.value && !overview.value && !loading.value) {
    fetchOverview(currentArtist.value)
  }
}

function queueSong(song) {
  const playerTrack = songToPlayerTrack(song, library.findTrack)
  actions.enqueue([playerTrack])
}

async function queueAlbum(album) {
  const local = library.findAlbum(album.artist || currentArtist.value, album.name)
  if (local?.tracks?.length) {
    actions.enqueue(local.tracks)
    return
  }
  if (album.url) {
    try {
      const res = await API.resolveUrl(album.url)
      const tracks = (res.data?.tracks || []).map((s) =>
        songToPlayerTrack(s, library.findTrack)
      )
      if (tracks.length) {
        actions.enqueue(tracks)
      } else {
        ui.toast(t('toast.actionFailed'), { kind: 'error' })
      }
    } catch {
      ui.toast(t('toast.actionFailed'), { kind: 'error' })
    }
  }
}

// Reset flipped state and load fresh artist overview when artist changes
watch(
  currentArtist,
  (newArtist, oldArtist) => {
    if (newArtist !== oldArtist) {
      isFlipped.value = false
      bioLimit.value = BIO_CHUNK
      overview.value = null
    }
  }
)
</script>

<style scoped>
.perspective-1000 {
  perspective: 1000px;
}
.transform-style-3d {
  transform-style: preserve-3d;
}
.backface-hidden {
  -webkit-backface-visibility: hidden;
  backface-visibility: hidden;
}
.rotate-y-180 {
  transform: rotateY(180deg);
}
</style>
