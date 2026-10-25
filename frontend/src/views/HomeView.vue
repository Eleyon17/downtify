<template>
  <div
    class="mx-auto flex max-w-[1680px] flex-col gap-10 px-4 pt-6 sm:px-6 md:pt-8 lg:px-10"
  >
    <!-- Active downloads (only when items are downloading) -->
    <section
      v-if="pending"
      class="flex flex-col gap-3 rounded-panel border border-line-2 bg-surface p-4 sm:p-5 animate-rise"
    >
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <AppIcon name="download" :size="18" class="text-accent animate-pulse" />
          <h2 class="text-sm font-semibold">{{ t('home.downloading') }}</h2>
        </div>
        <RouterLink
          :to="{ name: 'Queue' }"
          class="text-[13px] font-semibold text-accent hover:text-accent-hi"
        >
          {{ t('home.openQueue') }}
        </RouterLink>
      </div>

      <ul class="flex flex-col gap-2.5">
        <li
          v-for="item in activeItems"
          :key="item.key"
          class="flex items-center gap-3"
        >
          <CoverArt
            :src="item.song.cover_url"
            :name="item.song.album_name || item.song.name"
            rounded="rounded-[8px]"
            :letter-size="13"
            class="size-10 shrink-0"
          />
          <div class="min-w-0 flex-1">
            <div class="flex items-center justify-between gap-2">
              <span class="truncate text-[13px] font-semibold">{{
                item.song.name
              }}</span>
              <SourceBadge
                v-if="item.provider"
                :source="item.provider"
                compact
              />
            </div>
            <UiProgress
              class="mt-1.5"
              :value="item.progress"
              :indeterminate="!item.progress"
            />
          </div>
        </li>
      </ul>
      <p
        v-if="waiting"
        class="border-t border-line pt-2 text-xs text-muted"
      >
        {{ t('home.waiting', { count: waiting }) }}
      </p>
    </section>

    <!-- Daily Mix Hero -->
    <section
      v-if="suggestedMix && suggestedMix.tracks?.length"
      class="relative overflow-hidden rounded-panel border border-line-2 bg-gradient-to-br from-surface via-surface-2/60 to-surface p-6 sm:p-8 md:p-10 animate-rise shadow-lg"
    >
      <!-- Background ambient glow -->
      <div
        class="pointer-events-none absolute -top-24 -right-24 size-80 rounded-full bg-accent/15 blur-3xl"
        aria-hidden="true"
      />
      <div
        class="pointer-events-none absolute -bottom-24 -left-24 size-72 rounded-full bg-accent-2/10 blur-3xl"
        aria-hidden="true"
      />

      <div class="relative flex flex-col-reverse items-center justify-between gap-8 md:flex-row md:gap-12">
        <!-- Left: Text and Play Button -->
        <div class="flex flex-col items-center gap-4 text-center md:items-start md:text-left min-w-0">
          <div class="flex flex-col gap-1.5">
            <h1 class="text-display text-3xl font-extrabold tracking-tight sm:text-4xl lg:text-5xl text-fg">
              Daily Mix
            </h1>
            <p class="text-sm sm:text-base text-muted max-w-lg line-clamp-2">
              {{ mixSubtitle }}
            </p>
          </div>

          <div class="pt-2">
            <UiButton
              variant="primary"
              size="lg"
              icon="play"
              class="!h-13 !px-7 text-base font-semibold shadow-lg shadow-accent/25 hover:shadow-accent/40 hover:scale-[1.02] active:scale-[0.98] transition-all cursor-pointer"
              @click="playSuggestedMix"
            >
              Play
            </UiButton>
          </div>
        </div>

        <!-- Right: Stylized Album Art Orbs -->
        <div class="relative flex items-center justify-center shrink-0 py-4 px-2">
          <!-- Central ambient glow behind orbs -->
          <div
            class="pointer-events-none absolute size-48 sm:size-64 rounded-full bg-gradient-to-tr from-accent/20 to-accent-2/20 blur-2xl"
            aria-hidden="true"
          />

          <!-- Orb cluster -->
          <div class="relative flex items-center -space-x-5 sm:-space-x-7 md:-space-x-8">
            <div
              v-for="(orb, idx) in orbs"
              :key="idx"
              :title="orb.artist"
              class="group relative shrink-0 overflow-hidden rounded-full bg-surface-3 shadow-xl ring-2 ring-surface border border-line-2 transition-all duration-200 hover:scale-110 hover:z-40 hover:ring-accent cursor-pointer select-none"
              :class="[orb.sizeClass, orb.zIndex]"
              @click="playSuggestedMix"
            >
              <img
                :src="orb.photo"
                class="size-full object-cover transition-transform duration-300 group-hover:scale-105"
                :alt="orb.artist"
                loading="lazy"
                @error="onOrbImageError($event, orb.fallbackCover)"
              />
              <!-- Quick Fade-in Artist Name Overlay -->
              <div
                class="pointer-events-none absolute inset-0 flex items-center justify-center rounded-full bg-black/60 p-2 text-center opacity-0 transition-opacity duration-150 group-hover:opacity-100"
              >
                <span class="text-xs sm:text-sm font-bold text-white drop-shadow-md line-clamp-2 px-1 leading-snug">
                  {{ orb.artist }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Jump back in -->
    <section
      v-if="jumpBackIn.length"
      class="flex flex-col gap-4 animate-rise [animation-delay:80ms]"
    >
      <h2 class="text-display text-xl font-semibold">
        {{ t('home.jumpBackIn') }}
      </h2>
      <div class="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
        <RouterLink
          v-for="entry in jumpBackIn"
          :key="entry.id"
          :to="entry.route || { name: 'Home' }"
          class="group flex h-16 items-center gap-3 overflow-hidden rounded-[12px] bg-surface pr-3 transition-colors hover:bg-surface-2"
        >
          <CoverArt
            :src="entry.cover"
            :covers="entry.covers"
            :name="entry.title"
            :icon="
              entry.type === 'artist'
                ? 'user'
                : entry.type === 'playlist'
                  ? 'playlist'
                  : 'disc'
            "
            rounded="rounded-none"
            :letter-size="18"
            :icon-size="20"
            class="size-16"
          />
          <span class="flex min-w-0 flex-1 flex-col">
            <span class="truncate text-sm font-semibold">{{
              entry.title
            }}</span>
            <span class="truncate text-xs text-muted">
              {{ t(`home.kind.${entry.type}`)
              }}<template v-if="entry.subtitle">
                · {{ entry.subtitle }}</template
              >
            </span>
          </span>
          <EqBars v-if="isPlaying(entry)" :size="12" />
        </RouterLink>
      </div>
    </section>

    <!-- Recently added -->
    <section
      v-if="recentAlbums.length"
      class="flex flex-col gap-4 animate-rise [animation-delay:160ms]"
    >
      <div class="flex items-baseline justify-between gap-4">
        <h2 class="text-display text-xl font-semibold">
          {{ t('home.recentlyAdded') }}
        </h2>
        <RouterLink
          :to="{ name: 'Library', params: { tab: 'albums' } }"
          class="text-[13px] font-semibold text-muted hover:text-fg"
          >{{ t('common.seeAll') }}</RouterLink
        >
      </div>
      <div
        class="grid grid-cols-2 gap-x-5 gap-y-7 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 2xl:grid-cols-6"
      >
        <MediaTile
          v-for="album in recentAlbums"
          :key="album.key"
          :to="{
            name: 'Album',
            query: { artist: album.artist, title: album.title },
          }"
          :title="album.title"
          :subtitle="[album.artist, album.year].filter(Boolean).join(' · ')"
          :cover="album.cover"
          :name="album.title"
          @play="playAlbum(album)"
        />
      </div>
    </section>

    <!-- Playlists -->
    <section
      v-if="recentPlaylists.length"
      class="flex flex-col gap-4 animate-rise [animation-delay:240ms]"
    >
      <div class="flex items-baseline justify-between gap-4">
        <h2 class="text-display text-xl font-semibold">
          {{ t('home.playlists') }}
        </h2>
        <RouterLink
          :to="{ name: 'Library', params: { tab: 'playlists' } }"
          class="text-[13px] font-semibold text-muted hover:text-fg"
          >{{ t('common.seeAll') }}</RouterLink
        >
      </div>
      <div
        class="grid grid-cols-2 gap-x-5 gap-y-7 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 2xl:grid-cols-6"
      >
        <MediaTile
          v-for="playlist in recentPlaylists"
          :key="playlist.key"
          :to="{ name: 'Playlist', query: { name: playlist.name } }"
          :title="playlist.title"
          :subtitle="t('common.tracks', { count: itemTrackCount(playlist) })"
          :cover="playlist.cover"
          :covers="playlist.covers"
          :name="playlist.title"
          :icon="playlist.liked ? 'heart' : 'playlist'"
          :symbol="playlist.liked"
          @play="playlistActions.play(playlist)"
        />
      </div>
    </section>

    <!-- First run -->
    <section
      v-if="library.loaded.value && !library.trackCount.value"
      class="grid gap-4 md:grid-cols-3"
    >
      <div
        v-for="(step, i) in onboarding"
        :key="step.title"
        class="flex flex-col gap-2 rounded-panel border border-dashed border-line-3 p-5"
      >
        <span class="text-display tabular text-sm font-semibold text-accent"
          >0{{ i + 1 }}</span
        >
        <p class="text-[15px] font-semibold">{{ step.title }}</p>
        <p class="text-[13px] text-pretty text-muted">{{ step.body }}</p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import API from '/src/model/api'
import AppIcon from '/src/components/ui/AppIcon.vue'
import CoverArt from '/src/components/ui/CoverArt.vue'
import EqBars from '/src/components/ui/EqBars.vue'
import SourceBadge from '/src/components/ui/SourceBadge.vue'
import UiButton from '/src/components/ui/UiButton.vue'
import UiProgress from '/src/components/ui/UiProgress.vue'
import MediaTile from '/src/components/library/MediaTile.vue'
import { useProgressTracker } from '/src/model/download'
import { useHistory } from '/src/model/history'
import { useLibrary } from '/src/model/library'
import { usePlayer } from '/src/model/player'
import { usePlaylistActions } from '/src/model/playlistActions'
import { useTrackActions } from '/src/model/trackActions'
import { itemTrackCount, normalizeTrack } from '/src/lib/library'
import { proxiedArtistPhotoUrl } from '/src/lib/artistPhotoProxy'
import { useI18n } from '/src/i18n'

const { t } = useI18n()
const library = useLibrary()
const history = useHistory()
const player = usePlayer()
const tracker = useProgressTracker()
const actions = useTrackActions()
const playlistActions = usePlaylistActions()

const queueItems = computed(() => {
  tracker.queueVersion.value
  return tracker.downloadQueue.value
})
const activeItems = computed(() =>
  queueItems.value.filter((item) => item.state === 'active').slice(0, 3)
)
const waiting = computed(
  () => queueItems.value.filter((item) => item.state === 'queued').length
)
const pending = computed(() => activeItems.value.length + waiting.value)

const recentAlbums = computed(() =>
  [...library.albums.value].sort((a, b) => b.added - a.added).slice(0, 12)
)
const recentPlaylists = computed(() =>
  [...library.playlists.value]
    .filter((playlist) => itemTrackCount(playlist))
    .sort((a, b) => b.added - a.added)
    .slice(0, 6)
)

const jumpBackIn = computed(() =>
  history.recent.value
    .map((entry) => {
      if (entry.type !== 'playlist') return entry
      const name = String(entry.route?.query?.name || entry.title || '')
      const live = library.findPlaylist(name)
      if (!live) return null
      return {
        ...entry,
        title: live.title,
        cover: live.cover || live.covers[0] || entry.cover || '',
        covers: live.covers,
        route: { name: 'Playlist', query: { name: live.name } },
      }
    })
    .filter(Boolean)
    .slice(0, 6)
)

function isPlaying(entry) {
  const ctx = player.context.value
  return (
    player.isPlaying.value &&
    ctx?.type === entry.type &&
    ctx?.title === entry.title
  )
}

async function playAlbum(album) {
  await library.loadArtistTracks(album.artist)
  const live = library.findAlbum(album.artist, album.title) || album
  if (!live.tracks.length) return
  actions.play(live.tracks, 0, {
    type: 'album',
    title: live.title,
    subtitle: live.artist,
    cover: live.cover,
    route: {
      name: 'Album',
      query: { artist: live.artist, title: live.title },
    },
  })
}

const onboarding = computed(() => [
  { title: t('home.step1Title'), body: t('home.step1Body') },
  { title: t('home.step2Title'), body: t('home.step2Body') },
  { title: t('home.step3Title'), body: t('home.step3Body') },
])

const suggestedMix = ref(null)

const topArtists = computed(() => {
  if (!suggestedMix.value?.tracks?.length) return []
  const counts = new Map()
  for (const track of suggestedMix.value.tracks) {
    const artist = String(track.artist || '').trim()
    if (!artist) continue
    counts.set(artist, (counts.get(artist) || 0) + 1)
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([artist]) => artist)
})

const mixSubtitle = computed(() => {
  if (!suggestedMix.value?.tracks?.length) return ''
  const artists = topArtists.value
  if (!artists.length) {
    return `Your personalized mix from your library`
  }
  if (artists.length === 1) {
    return `Your personalized mix including ${artists[0]}...`
  }
  if (artists.length === 2) {
    return `Your personalized mix including ${artists[0]} and ${artists[1]}...`
  }
  return `Your personalized mix including ${artists[0]}, ${artists[1]}, and ${artists[2]}...`
})

function getArtistFallbackCover(artist) {
  if (!suggestedMix.value?.tracks?.length) return ''
  const track = suggestedMix.value.tracks.find(
    (t) => String(t.artist || '').trim().toLowerCase() === artist.toLowerCase()
  )
  if (!track) return ''
  return (
    track.cover ||
    track.cover_url ||
    (track.has_cover && track.file
      ? `/cover?file=${encodeURIComponent(track.file)}`
      : '')
  )
}

function onOrbImageError(event, fallback) {
  if (fallback && event.target.src !== fallback) {
    event.target.src = fallback
  }
}

const orbs = computed(() => {
  const artists = topArtists.value
  if (!artists.length) return []

  const list = artists.slice(0, 5).map((artist) => ({
    artist,
    photo: proxiedArtistPhotoUrl(artist),
    fallbackCover: getArtistFallbackCover(artist),
  }))

  if (list.length === 1) {
    return [
      {
        ...list[0],
        sizeClass: 'size-28 sm:size-36 md:size-40',
        zIndex: 'z-30',
      },
    ]
  }
  if (list.length === 2) {
    return [
      {
        ...list[0],
        sizeClass: 'size-26 sm:size-32 md:size-36',
        zIndex: 'z-30',
      },
      {
        ...list[1],
        sizeClass: 'size-20 sm:size-24 md:size-28',
        zIndex: 'z-20',
      },
    ]
  }
  if (list.length === 3) {
    return [
      {
        ...list[1],
        sizeClass: 'size-20 sm:size-24 md:size-28',
        zIndex: 'z-20',
      },
      {
        ...list[0],
        sizeClass: 'size-28 sm:size-36 md:size-40',
        zIndex: 'z-30',
      },
      {
        ...list[2],
        sizeClass: 'size-20 sm:size-24 md:size-28',
        zIndex: 'z-20',
      },
    ]
  }
  if (list.length === 4) {
    return [
      {
        ...list[2],
        sizeClass: 'size-16 sm:size-20 md:size-22',
        zIndex: 'z-10',
      },
      {
        ...list[0],
        sizeClass: 'size-28 sm:size-36 md:size-40',
        zIndex: 'z-30',
      },
      {
        ...list[1],
        sizeClass: 'size-22 sm:size-26 md:size-28',
        zIndex: 'z-20',
      },
      {
        ...list[3],
        sizeClass: 'size-16 sm:size-20 md:size-22',
        zIndex: 'z-10',
      },
    ]
  }
  // 5 artists: layout order [2, 1, 0, 3, 4] with #0 at center
  return [
    {
      ...list[2],
      sizeClass: 'size-16 sm:size-20 md:size-22',
      zIndex: 'z-10',
    },
    {
      ...list[1],
      sizeClass: 'size-22 sm:size-26 md:size-28',
      zIndex: 'z-20',
    },
    {
      ...list[0],
      sizeClass: 'size-28 sm:size-36 md:size-40',
      zIndex: 'z-30',
    },
    {
      ...list[3],
      sizeClass: 'size-22 sm:size-26 md:size-28',
      zIndex: 'z-20',
    },
    {
      ...list[4],
      sizeClass: 'size-16 sm:size-20 md:size-22',
      zIndex: 'z-10',
    },
  ]
})

async function loadSuggestedMix() {
  try {
    const res = await API.getSuggestedMix()
    suggestedMix.value = res.data
  } catch {
    suggestedMix.value = null
  }
}

function playSuggestedMix() {
  if (!suggestedMix.value?.tracks?.length) return
  const tracks = suggestedMix.value.tracks.map(normalizeTrack)
  actions.play(tracks, 0, {
    type: 'playlist',
    title: 'Daily Mix',
    subtitle: suggestedMix.value.date,
    cover:
      orbs.value[0]?.fallbackCover ||
      orbs.value[0]?.photo ||
      suggestedMix.value.covers?.[0],
  })
}

onMounted(loadSuggestedMix)
</script>
