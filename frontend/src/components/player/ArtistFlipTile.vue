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
      </div>

      <!-- BACK: Artist Bio, Popular Songs & Albums -->
      <div
        class="absolute inset-0 flex size-full rotate-y-180 flex-col overflow-hidden rounded-[20px] border border-line-2 bg-surface/95 p-3.5 text-fg shadow-2xl backdrop-blur-2xl backface-hidden"
        @click.stop
      >
        <!-- Header -->
        <div class="flex shrink-0 items-center justify-between border-b border-line pb-2.5">
          <div class="flex min-w-0 items-center gap-2">
            <AppIcon name="user" :size="18" class="shrink-0 text-accent" />
            <h3 class="truncate text-sm font-bold text-fg">
              {{ currentArtist }}
            </h3>
          </div>
          <button
            type="button"
            class="flex size-7 shrink-0 items-center justify-center rounded-full bg-surface-2 text-muted transition-colors hover:bg-surface-3 hover:text-fg"
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
              <span class="text-[11px] font-bold tracking-wider text-muted uppercase">
                {{ t('artistBio.title') }}
              </span>
              <span
                v-if="overview?.bio_source === 'youtubemusic'"
                class="text-[10px] text-faint font-medium"
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
                class="text-xs leading-relaxed text-fg-2 whitespace-pre-line"
              >
                {{ visibleBio }}
              </p>
              <p v-else class="text-xs text-muted italic">
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

          <!-- Hit Songs Section -->
          <section v-if="overview?.top_songs?.length">
            <div class="mb-1.5 flex items-center justify-between">
              <span class="text-[11px] font-bold tracking-wider text-muted uppercase">
                Hit Songs
              </span>
            </div>
            <div class="space-y-1">
              <div
                v-for="song in overview.top_songs"
                :key="song.video_id || song.name"
                class="group flex items-center gap-2.5 rounded-[10px] p-1.5 transition-colors hover:bg-surface-2 cursor-pointer border border-transparent hover:border-line"
                @click="queueSong(song)"
              >
                <CoverArt
                  :src="songCover(song)"
                  :fallback="songFallbackCovers(song)"
                  :name="song.album_name || song.name"
                  rounded="rounded-[6px]"
                  :letter-size="12"
                  :icon-size="14"
                  class="size-9 shrink-0"
                />
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-1.5">
                    <span class="truncate text-xs font-semibold text-fg">
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
                  <p class="truncate text-[11px] text-muted">
                    {{ [song.album_name, song.duration ? formatDuration(song.duration) : ''].filter(Boolean).join(' · ') }}
                  </p>
                </div>
                <button
                  type="button"
                  class="flex size-7 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-surface-3 hover:text-fg"
                  :title="t('actions.playNext')"
                  @click.stop="queueSong(song)"
                >
                  <AppIcon name="play-next" :size="15" />
                </button>
              </div>
            </div>
          </section>

          <!-- Hit Albums Section -->
          <section v-if="overview?.top_albums?.length">
            <div class="mb-1.5 flex items-center justify-between">
              <span class="text-[11px] font-bold tracking-wider text-muted uppercase">
                Hit Albums
              </span>
            </div>
            <div class="space-y-1">
              <div
                v-for="album in overview.top_albums"
                :key="album.album_id || album.name"
                class="group flex items-center gap-2.5 rounded-[10px] p-1.5 transition-colors hover:bg-surface-2 cursor-pointer border border-transparent hover:border-line"
                @click="queueAlbum(album)"
              >
                <CoverArt
                  :src="albumCover(album)"
                  :fallback="albumFallbackCovers(album)"
                  :name="album.name"
                  rounded="rounded-[6px]"
                  :letter-size="12"
                  :icon-size="14"
                  class="size-9 shrink-0"
                />
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-1.5">
                    <span class="truncate text-xs font-semibold text-fg">
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
                  <p class="truncate text-[11px] text-muted">
                    {{ [album.release_type, album.year].filter(Boolean).join(' · ') }}
                  </p>
                </div>
                <button
                  type="button"
                  class="flex size-7 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-surface-3 hover:text-fg"
                  :title="t('actions.playNext')"
                  @click.stop="queueAlbum(album)"
                >
                  <AppIcon name="play-next" :size="15" />
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
  if (library?.loadArtistTracks) {
    library.loadArtistTracks(name)
  }
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
  if (isFlipped.value) {
    if (library?.loadArtistTracks && currentArtist.value) {
      library.loadArtistTracks(currentArtist.value)
    }
    if (!overview.value && !loading.value) {
      fetchOverview(currentArtist.value)
    }
  }
}

function normalizeAlbumTitle(title) {
  if (!title || typeof title !== 'string') return ''
  return title
    .toLowerCase()
    .replace(/\s*[\(\[][^\)\]]*(edition|deluxe|version|bonus|remaster|anniversary|revisited|expanded|explicit|single|ep)[^\)\]]*[\)\]]/gi, ' ')
    .replace(/\b(deluxe|edition|version|remastered|remaster|anniversary|revisited|expanded|explicit|single|ep)\b/gi, ' ')
    .replace(/[^\p{L}\p{N}\s]/gu, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function songCoverCandidates(song) {
  const candidates = []
  const add = (url) => {
    if (url && typeof url === 'string' && !candidates.includes(url)) {
      candidates.push(url)
    }
  }

  // 1. Direct song cover URL (remote YouTube/provider)
  add(song.cover_url || song.cover)

  // 2. Local library track cover
  const localTrack = library.findTrack(songArtist(song) || currentArtist.value, song.name)
  if (localTrack?.hasCover && localTrack?.cover) {
    add(localTrack.cover)
  }

  const normSongAlbum = normalizeAlbumTitle(song.album_name)

  // 3. Local library album cover
  if (song.album_name) {
    const localAlbum =
      library.findAlbum(songArtist(song), song.album_name) ||
      library.findAlbum(currentArtist.value, song.album_name)
    if (localAlbum?.cover) {
      add(localAlbum.cover)
    }
    if (normSongAlbum && library.albums?.value) {
      const fuzzyAlbum = library.albums.value.find((a) => {
        const aNorm = normalizeAlbumTitle(a.title)
        return aNorm && (aNorm === normSongAlbum || aNorm.includes(normSongAlbum) || normSongAlbum.includes(aNorm))
      })
      if (fuzzyAlbum?.cover) {
        add(fuzzyAlbum.cover)
      }
    }
  }

  // 4. Matching album from overview top_albums
  if (song.album_name && overview.value?.top_albums) {
    const match = overview.value.top_albums.find((a) => {
      if (!a.name) return false
      if (a.name.toLowerCase() === song.album_name.toLowerCase()) return true
      const aNorm = normalizeAlbumTitle(a.name)
      return aNorm && normSongAlbum && aNorm === normSongAlbum
    })
    if (match?.cover_url) {
      add(match.cover_url)
    }
  }

  // 5. Playing track if same song or album
  if (props.track?.hasCover && props.track?.cover) {
    if (
      (props.track.title && song.name && props.track.title.toLowerCase() === song.name.toLowerCase()) ||
      (props.track.album && song.album_name && props.track.album.toLowerCase() === song.album_name.toLowerCase())
    ) {
      add(props.track.cover)
    }
  }

  // 6. YouTube video thumbnail
  const vid = song.song_id || song.video_id
  if (vid) {
    add(`https://i.ytimg.com/vi/${vid}/hqdefault.jpg`)
  }

  // 7. Artist photo from overview
  if (overview.value?.cover_url) {
    add(overview.value.cover_url)
  }

  // 8. Currently playing track cover
  if (props.track?.hasCover && props.track?.cover) {
    add(props.track.cover)
  }

  return candidates
}

function songCover(song) {
  const c = songCoverCandidates(song)
  return c[0] || ''
}

function songFallbackCovers(song) {
  const c = songCoverCandidates(song)
  return c.slice(1)
}

function songFallbackCover(song) {
  const c = songCoverCandidates(song)
  return c[1] || ''
}

function albumCoverCandidates(album) {
  const candidates = []
  const add = (url) => {
    if (url && typeof url === 'string' && !candidates.includes(url)) {
      candidates.push(url)
    }
  }

  // 1. Direct album cover URL
  add(album.cover_url || album.cover)

  const normAlbumName = normalizeAlbumTitle(album.name)

  // 2. Local library exact album match
  const localAlbum =
    library.findAlbum(album.artist, album.name) ||
    library.findAlbum(currentArtist.value, album.name)
  if (localAlbum?.cover) {
    add(localAlbum.cover)
  }

  // 3. Fuzzy match in library albums
  if (normAlbumName && library.albums?.value) {
    const fuzzyAlbum = library.albums.value.find((a) => {
      const aNorm = normalizeAlbumTitle(a.title)
      return aNorm && (aNorm === normAlbumName || aNorm.includes(normAlbumName) || normAlbumName.includes(aNorm))
    })
    if (fuzzyAlbum?.cover) {
      add(fuzzyAlbum.cover)
    }
  }

  // 4. Fuzzy match in library tracks
  if (normAlbumName && library.tracks?.value) {
    const trackWithCover = library.tracks.value.find((t) => {
      if (!t.hasCover || !t.cover) return false
      const tNorm = normalizeAlbumTitle(t.album)
      return tNorm && (tNorm === normAlbumName || tNorm.includes(normAlbumName) || normAlbumName.includes(tNorm))
    })
    if (trackWithCover?.cover) {
      add(trackWithCover.cover)
    }
  }

  // 5. Matching song from overview top_songs
  if (album.name && overview.value?.top_songs) {
    const match = overview.value.top_songs.find((s) => {
      if (!s.album_name) return false
      if (s.album_name.toLowerCase() === album.name.toLowerCase()) return true
      const sNorm = normalizeAlbumTitle(s.album_name)
      return sNorm && normAlbumName && sNorm === normAlbumName
    })
    if (match?.cover_url || match?.cover) {
      add(match.cover_url || match.cover)
    }
    const matchVid = match?.song_id || match?.video_id
    if (matchVid) {
      add(`https://i.ytimg.com/vi/${matchVid}/hqdefault.jpg`)
    }
  }

  // 6. Currently playing track if matching album
  if (props.track?.hasCover && props.track?.cover) {
    const trackAlbumNorm = normalizeAlbumTitle(props.track.album)
    if (
      (props.track.album && album.name && props.track.album.toLowerCase() === album.name.toLowerCase()) ||
      (trackAlbumNorm && normAlbumName && trackAlbumNorm === normAlbumName)
    ) {
      add(props.track.cover)
    }
  }

  // 7. Any track in the user's library by this artist that has a cover
  if (library.tracks?.value) {
    const anyArtistTrack = library.tracks.value.find((t) => {
      const artist = t.albumArtist || (t.artists || [])[0] || t.artist || ''
      return artist.toLowerCase() === currentArtist.value.toLowerCase() && t.hasCover && t.cover
    })
    if (anyArtistTrack?.cover) {
      add(anyArtistTrack.cover)
    }
  }

  // 8. Artist photo from overview
  if (overview.value?.cover_url) {
    add(overview.value.cover_url)
  }

  // 9. Any top song video thumbnails from overview
  if (overview.value?.top_songs) {
    for (const s of overview.value.top_songs) {
      if (s.cover_url || s.cover) add(s.cover_url || s.cover)
      const vid = s.song_id || s.video_id
      if (vid) {
        add(`https://i.ytimg.com/vi/${vid}/hqdefault.jpg`)
      }
    }
  }

  // 10. Currently playing track cover
  if (props.track?.hasCover && props.track?.cover) {
    add(props.track.cover)
  }

  return candidates
}

function albumCover(album) {
  const c = albumCoverCandidates(album)
  return c[0] || ''
}

function albumFallbackCovers(album) {
  const c = albumCoverCandidates(album)
  return c.slice(1)
}

function albumFallbackCover(album) {
  const c = albumCoverCandidates(album)
  return c[1] || ''
}

function queueSong(song) {
  const resolvedSong = song.cover_url ? song : { ...song, cover_url: songCover(song) }
  const playerTrack = songToPlayerTrack(resolvedSong, library.findTrack)
  actions.playNext([playerTrack])
}

async function queueAlbum(album) {
  const local = library.findAlbum(album.artist || currentArtist.value, album.name)
  if (local?.tracks?.length) {
    actions.playNext(local.tracks)
    return
  }
  if (album.url) {
    try {
      const res = await API.resolveUrl(album.url)
      const tracks = (res.data?.tracks || []).map((s) =>
        songToPlayerTrack(s, library.findTrack)
      )
      if (tracks.length) {
        actions.playNext(tracks)
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
