<template>
  <UiModal
    :open="open"
    :title="t('albumArt.title') || 'Choose Album Artwork'"
    :description="album ? `${album.artist} — ${album.title}` : ''"
    width="sm:max-w-3xl"
    @close="$emit('close')"
  >
    <div class="flex flex-col gap-5">
      <!-- Search and Custom Input -->
      <form class="flex gap-2" @submit.prevent="search">
        <label
          class="flex h-11 min-w-0 flex-1 items-center gap-2.5 rounded-control border border-line-3 bg-bg px-3.5 focus-within:border-accent"
        >
          <AppIcon
            :name="isUrlQuery ? 'link' : 'search'"
            :size="16"
            class="text-faint"
          />
          <input
            v-model="query"
            type="text"
            autocomplete="off"
            :placeholder="t('albumArt.searchPlaceholder') || 'Search album title or paste image URL...'"
            class="h-full min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-faint"
          />
        </label>
        <UiButton
          type="submit"
          variant="primary"
          icon="search"
          :loading="loading"
        >
          {{ t('search.searchButton') || 'Search' }}
        </UiButton>
      </form>

      <!-- Lock Setting & Status Banner -->
      <div
        class="flex flex-wrap items-center justify-between gap-3 rounded-control border border-line-2 bg-surface-2 p-3.5 text-sm"
      >
        <div class="flex items-center gap-2.5">
          <AppIcon
            :name="isLocked ? 'lock' : 'unlock'"
            :size="18"
            :class="isLocked ? 'text-accent' : 'text-muted'"
          />
          <div>
            <p class="font-medium text-fg">
              {{ t('albumArt.lockLabel') || 'Lock Artwork Against Upgrades' }}
            </p>
            <p class="text-xs text-muted">
              {{
                t('albumArt.lockHint') ||
                'Library Upgrade will never overwrite or change this album art.'
              }}
            </p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <UiSwitch
            v-model="shouldLock"
            :aria-label="t('albumArt.lockLabel') || 'Lock artwork'"
          />
          <UiButton
            v-if="isLocked"
            size="sm"
            variant="ghost"
            icon="unlock"
            :loading="unlocking"
            @click="unlock"
          >
            {{ t('albumArt.unlock') || 'Unlock' }}
          </UiButton>
        </div>
      </div>

      <!-- Error alert -->
      <p v-if="error" class="text-sm text-danger" role="alert">
        {{ error }}
      </p>

      <!-- Loading skeleton -->
      <div
        v-if="loading"
        class="grid grid-cols-2 gap-3.5 sm:grid-cols-3 md:grid-cols-4"
      >
        <div v-for="n in 8" :key="n" class="flex flex-col gap-2">
          <UiSkeleton class="aspect-square !rounded-cover" />
          <UiSkeleton class="h-4 w-2/3" />
        </div>
      </div>

      <!-- Empty state -->
      <div
        v-else-if="!candidates.length"
        class="flex flex-col items-center justify-center py-12 text-center text-muted"
      >
        <AppIcon name="disc" :size="36" class="mb-2 text-faint" />
        <p class="font-medium text-fg">
          {{ t('albumArt.noResults') || 'No album cover options found' }}
        </p>
        <p class="text-xs text-muted max-w-sm mt-1">
          {{
            t('albumArt.noResultsHint') ||
            'Try searching for artist and album name above, or paste an image URL directly.'
          }}
        </p>
      </div>

      <!-- Candidate cover grid -->
      <div
        v-else
        class="grid max-h-[55vh] grid-cols-2 gap-3.5 overflow-y-auto p-0.5 sm:grid-cols-3 md:grid-cols-4"
      >
        <button
          v-for="(cand, idx) in candidates"
          :key="`${cand.source}-${cand.url}-${idx}`"
          type="button"
          class="group relative flex flex-col overflow-hidden rounded-cover border-2 p-1.5 text-left transition-all"
          :class="
            selectedUrl === cand.url
              ? 'border-accent bg-accent/10 shadow-md ring-2 ring-accent/30'
              : 'border-line-2 bg-surface hover:border-line-3'
          "
          @click="selectedUrl = cand.url"
        >
          <div class="relative aspect-square w-full overflow-hidden rounded-[10px] bg-black/20">
            <img
              :src="cand.url"
              :alt="cand.title || 'Cover candidate'"
              loading="lazy"
              class="size-full object-cover transition-transform duration-200 group-hover:scale-105"
            />
            <div
              v-if="selectedUrl === cand.url"
              class="absolute top-2 right-2 flex size-6 items-center justify-center rounded-full bg-accent text-white shadow-md"
            >
              <AppIcon name="check" :size="14" />
            </div>
          </div>

          <div class="mt-2 flex flex-col gap-0.5 px-0.5">
            <div class="flex items-center justify-between gap-1 text-[11px]">
              <span
                class="rounded px-1.5 py-0.5 font-semibold uppercase tracking-wider text-[10px]"
                :class="sourceBadgeClass(cand.source)"
              >
                {{ cand.source_label || cand.source }}
              </span>
              <span class="font-mono text-muted">
                {{ cand.width ? `${cand.width}×${cand.height || cand.width}` : '' }}
              </span>
            </div>
            <p
              v-if="cand.title"
              class="truncate text-xs font-medium text-fg"
              :title="cand.title"
            >
              {{ cand.title }}
            </p>
          </div>
        </button>
      </div>
    </div>

    <template #footer>
      <div class="flex w-full items-center justify-between gap-3">
        <p class="text-xs text-muted truncate">
          <span v-if="selectedCandidate">
            {{ selectedCandidate.source_label }} • {{ selectedCandidate.width }}×{{ selectedCandidate.height || selectedCandidate.width }}px
          </span>
        </p>
        <div class="flex items-center gap-2">
          <UiButton variant="ghost" type="button" @click="$emit('close')">
            {{ t('common.cancel') || 'Cancel' }}
          </UiButton>
          <UiButton
            variant="primary"
            icon="wand"
            :loading="saving"
            :disabled="!selectedUrl"
            @click="applyCover"
          >
            {{ t('albumArt.apply') || 'Set Artwork & Lock' }}
          </UiButton>
        </div>
      </div>
    </template>
  </UiModal>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import AppIcon from '../ui/AppIcon.vue'
import UiButton from '../ui/UiButton.vue'
import UiModal from '../ui/UiModal.vue'
import UiSkeleton from '../ui/UiSkeleton.vue'
import UiSwitch from '../ui/UiSwitch.vue'
import API from '/src/model/api'
import { useUi } from '/src/model/ui'
import { useLibrary } from '/src/model/library'
import { useI18n } from '/src/i18n'

const props = defineProps({
  open: { type: Boolean, default: false },
  album: { type: Object, default: null },
})
const emit = defineEmits(['close', 'saved'])

const { t } = useI18n()
const ui = useUi()
const library = useLibrary()

const query = ref('')
const candidates = ref([])
const selectedUrl = ref('')
const loading = ref(false)
const saving = ref(false)
const unlocking = ref(false)
const isLocked = ref(false)
const shouldLock = ref(true)
const error = ref('')

const isUrlQuery = computed(() => {
  const q = query.value.trim()
  return q.startsWith('http://') || q.startsWith('https://')
})

const selectedCandidate = computed(() =>
  candidates.value.find((c) => c.url === selectedUrl.value)
)

function sourceBadgeClass(source) {
  switch (source) {
    case 'itunes':
      return 'bg-purple-500/15 text-purple-400 border border-purple-500/20'
    case 'deezer':
      return 'bg-orange-500/15 text-orange-400 border border-orange-500/20'
    case 'spotify':
      return 'bg-green-500/15 text-green-400 border border-green-500/20'
    case 'youtube-music':
      return 'bg-red-500/15 text-red-400 border border-red-500/20'
    default:
      return 'bg-surface-3 text-muted'
  }
}

async function loadCovers(overrideQuery = '') {
  if (!props.album) return
  loading.value = true
  error.value = ''
  try {
    const res = await API.getAlbumCoverCandidates(
      props.album.artist,
      props.album.title,
      overrideQuery,
      props.album.tracks?.[0]?.file || ''
    )
    candidates.value = res.data?.candidates || []
    isLocked.value = Boolean(res.data?.locked)
    shouldLock.value = true
    if (candidates.value.length && !selectedUrl.value) {
      selectedUrl.value = candidates.value[0].url
    }
  } catch (err) {
    error.value = err?.response?.data?.detail || t('toast.actionFailed') || 'Failed to search cover art'
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.album],
  ([isOpen, alb]) => {
    if (isOpen && alb) {
      query.value = `${alb.artist} ${alb.title}`.trim()
      selectedUrl.value = ''
      loadCovers()
    } else {
      candidates.value = []
      selectedUrl.value = ''
      error.value = ''
    }
  },
  { immediate: true }
)

async function search() {
  const q = query.value.trim()
  if (!q) return
  if (isUrlQuery.value) {
    // Treat as direct image candidate
    const existing = candidates.value.find((c) => c.url === q)
    if (!existing) {
      candidates.value.unshift({
        source: 'custom',
        source_label: 'Custom URL',
        url: q,
        width: 0,
        height: 0,
        title: props.album?.title || '',
        artist: props.album?.artist || '',
      })
    }
    selectedUrl.value = q
    return
  }
  await loadCovers(q)
}

async function applyCover() {
  if (!props.album || !selectedUrl.value || saving.value) return
  saving.value = true
  error.value = ''
  try {
    const res = await API.setAlbumCover(
      props.album.artist,
      props.album.title,
      selectedUrl.value,
      shouldLock.value,
      props.album.tracks?.[0]?.file || ''
    )
    isLocked.value = Boolean(res.data?.locked)
    ui.toast(
      shouldLock.value
        ? t('albumArt.appliedAndLocked') || 'Album artwork updated and locked against upgrades.'
        : t('albumArt.applied') || 'Album artwork updated.',
      { kind: 'success' }
    )
    await library.load({ force: true })
    emit('saved', res.data)
    emit('close')
  } catch (err) {
    error.value = err?.response?.data?.detail || t('toast.actionFailed') || 'Failed to apply album artwork'
  } finally {
    saving.value = false
  }
}

async function unlock() {
  if (!props.album || unlocking.value) return
  unlocking.value = true
  try {
    await API.unlockAlbumCover(props.album.artist, props.album.title)
    isLocked.value = false
    ui.toast(t('albumArt.unlocked') || 'Artwork unlocked. Future Library Upgrades may replace it.', {
      kind: 'neutral',
    })
    await library.load({ force: true })
  } catch (err) {
    error.value = err?.response?.data?.detail || t('toast.actionFailed') || 'Failed to unlock artwork'
  } finally {
    unlocking.value = false
  }
}
</script>
