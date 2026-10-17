<template>
  <UiPanel
    :title="t('playlists.suggestionsTitle')"
    :description="t('playlists.suggestionsHint')"
  >
    <template #actions>
      <UiIconButton
        icon="refresh"
        :label="t('playlists.suggestionsRefresh')"
        size="sm"
        :disabled="loading"
        @click="fetchSuggestions(true)"
      />
    </template>

    <!-- Initial loading state -->
    <div
      v-if="loading && !displayedSuggestions.length"
      class="flex flex-col gap-2 py-4"
    >
      <div
        v-for="i in 5"
        :key="i"
        class="flex h-16 animate-pulse items-center gap-3 rounded-[12px] px-3"
      >
        <div class="size-11 shrink-0 rounded-[8px] bg-surface-2" />
        <div class="flex-1 space-y-2">
          <div class="h-3.5 w-1/3 rounded bg-surface-2" />
          <div class="h-3 w-1/4 rounded bg-surface-2" />
        </div>
        <div class="h-9 w-24 rounded-full bg-surface-2" />
      </div>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="!displayedSuggestions.length"
      class="py-8 text-center text-sm text-muted"
    >
      <p>{{ t('playlists.suggestionsEmpty') }}</p>
      <button
        type="button"
        class="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-accent hover:underline"
        @click="fetchSuggestions(true)"
      >
        <AppIcon name="refresh" :size="14" />
        {{ t('playlists.suggestionsRefresh') }}
      </button>
    </div>

    <!-- Suggestions List -->
    <ul v-else class="-mx-2 flex flex-col gap-1">
      <li
        v-for="(song, idx) in displayedSuggestions"
        :key="song.song_id || song.name + '-' + song.artist"
      >
        <PlaylistSuggestionRow
          :song="song"
          :playlist="playlist"
          :songs="displayedSuggestions"
          :index="idx"
          @dismiss="handleDismiss(song)"
          @added="handleAdded(song)"
        />
      </li>
    </ul>
  </UiPanel>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import AppIcon from '/src/components/ui/AppIcon.vue'
import UiIconButton from '/src/components/ui/UiIconButton.vue'
import UiPanel from '/src/components/ui/UiPanel.vue'
import PlaylistSuggestionRow from './PlaylistSuggestionRow.vue'
import API from '/src/model/api'
import { useI18n } from '/src/i18n'

const props = defineProps({
  playlist: { type: Object, required: true },
})

const { t } = useI18n()

const loading = ref(false)
const fetchingMore = ref(false)
const pool = ref([]) // All fetched suggestions
const displayed = ref([]) // Currently displayed up to 10
const dismissedSet = ref(new Set())

const displayedSuggestions = computed(() => displayed.value)

function storageKey(name) {
  return `downtify_suggestions_dismissed_${name || ''}`
}

function loadDismissed(name) {
  try {
    const raw = localStorage.getItem(storageKey(name))
    const list = raw ? JSON.parse(raw) : []
    dismissedSet.value = new Set(list)
  } catch {
    dismissedSet.value = new Set()
  }
}

function persistDismissed(name) {
  try {
    localStorage.setItem(
      storageKey(name),
      JSON.stringify(Array.from(dismissedSet.value))
    )
  } catch {}
}

async function fetchSuggestions(forceRefresh = false) {
  const plName = props.playlist?.title || props.playlist?.name
  if (!plName) return

  if (forceRefresh) {
    loading.value = true
    displayed.value = []
    pool.value = []
  } else if (!pool.value.length && !displayed.value.length) {
    loading.value = true
  }

  loadDismissed(plName)

  try {
    const res = await API.getPlaylistSuggestions(
      plName,
      Array.from(dismissedSet.value),
      30
    )
    const items = res.data?.suggestions || []

    // Filter out any newly dismissed
    const fresh = items.filter(
      (s) =>
        !dismissedSet.value.has(s.song_id) &&
        !dismissedSet.value.has(s.name.toLowerCase())
    )

    if (forceRefresh || !displayed.value.length) {
      displayed.value = fresh.slice(0, 10)
      pool.value = fresh.slice(10)
    } else {
      // Append new items to pool
      const existingIds = new Set([
        ...displayed.value.map((s) => s.song_id || s.name),
        ...pool.value.map((s) => s.song_id || s.name),
      ])
      const toAdd = fresh.filter((s) => !existingIds.has(s.song_id || s.name))
      pool.value.push(...toAdd)
    }
  } catch {
    // Best-effort load
  } finally {
    loading.value = false
    fetchingMore.value = false
  }
}

function handleDismiss(song) {
  const plName = props.playlist?.title || props.playlist?.name
  const sid = song.song_id || song.name.toLowerCase()

  dismissedSet.value.add(sid)
  if (song.name) dismissedSet.value.add(song.name.toLowerCase())
  persistDismissed(plName)

  // Remove from displayed
  const idx = displayed.value.findIndex(
    (s) => (s.song_id && s.song_id === song.song_id) || s.name === song.name
  )
  if (idx !== -1) {
    displayed.value.splice(idx, 1)
  }

  // Backfill with next candidate from pool to keep at 10
  if (pool.value.length > 0) {
    const next = pool.value.shift()
    displayed.value.push(next)
  }

  // Pre-fetch more if pool is running low
  if (pool.value.length < 5 && !fetchingMore.value) {
    fetchingMore.value = true
    fetchSuggestions(false)
  }
}

function handleAdded(song) {
  // Once added, smoothly replace after 800ms
  setTimeout(() => {
    handleDismiss(song)
  }, 800)
}

watch(
  () => props.playlist?.name,
  (name, oldName) => {
    if (name && name !== oldName) {
      fetchSuggestions(true)
    }
  },
  { immediate: true }
)
</script>
