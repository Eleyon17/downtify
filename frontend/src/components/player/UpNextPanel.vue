<template>
  <div class="flex h-full min-h-0 flex-col">
    <div class="flex items-center justify-between gap-3 px-2 pb-3">
      <div class="min-w-0">
        <p class="text-sm font-semibold text-white">{{ t('player.upNext') }}</p>
        <p class="truncate text-xs text-white/55">
          {{ summary }}
        </p>
      </div>
      <button
        v-if="upcoming.length"
        type="button"
        class="shrink-0 rounded-control px-2.5 py-1.5 text-xs font-semibold text-white/70 hover:bg-white/10 hover:text-white"
        @click="player.clearUpcoming()"
      >
        {{ t('player.clearUpcoming') }}
      </button>
    </div>

    <div
      class="min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1 [scrollbar-width:thin]"
    >
      <div
        v-if="current"
        class="mb-1 flex h-14 items-center gap-3 rounded-[10px] bg-white/10 px-2.5"
      >
        <CoverArt
          :src="current.hasCover ? current.cover : ''"
          :name="current.album || current.title"
          rounded="rounded-[6px]"
          :letter-size="12"
          :icon-size="14"
          class="size-10"
        />
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-semibold text-accent flex items-center gap-1.5">
            <span class="truncate">{{ current.title }}</span>
            <AppIcon
              v-if="!current.stream || library.hasSong(current.artist, current.title)"
              name="cloud"
              :size="14"
              class="text-accent shrink-0 inline-block"
              :title="t('search.inLibrary')"
            />
          </p>
          <p class="truncate text-xs text-white/55">{{ current.artist }}</p>
        </div>
        <EqBars :size="12" :playing="player.isPlaying.value" />
      </div>

      <TransitionGroup name="list" tag="ol">
        <li
          v-for="(item, position) in upcoming"
          :key="`${item.track.file}-${item.index}`"
          :data-position="position"
          class="group flex h-14 items-center gap-3 rounded-[10px] px-2.5 transition-colors hover:bg-white/8 select-none"
          :class="[
            dragOver === position ? 'bg-white/15 ring-1 ring-white/25' : '',
            dragFromPos === position ? 'opacity-40' : '',
          ]"
          draggable="true"
          @dragstart="onDragStart($event, position)"
          @dragover.prevent="onDragOver(position)"
          @drop.prevent="onDrop(position)"
          @dragend="onDragEnd"
        >
          <button
            type="button"
            class="flex min-w-0 flex-1 items-center gap-3 text-left"
            @click="player.playUpcoming(position)"
          >
            <CoverArt
              :src="item.track.hasCover ? item.track.cover : ''"
              :name="item.track.album || item.track.title"
              rounded="rounded-[6px]"
              :letter-size="12"
              :icon-size="14"
              class="size-10"
            />
            <span class="min-w-0 flex-1">
              <span class="flex items-center gap-1.5 text-sm font-medium text-white">
                <span class="truncate">{{ item.track.title }}</span>
                <AppIcon
                  v-if="!item.track.stream || library.hasSong(item.track.artist, item.track.title)"
                  name="cloud"
                  :size="14"
                  class="text-accent shrink-0 inline-block"
                  :title="t('search.inLibrary')"
                />
              </span>
              <span class="block truncate text-xs text-white/55">{{
                item.track.artist
              }}</span>
            </span>
          </button>
          <span class="tabular text-xs text-white/45 group-hover:hidden">
            {{ item.track.duration ? formatDuration(item.track.duration) : '' }}
          </span>
          <button
            type="button"
            class="hidden size-8 items-center justify-center rounded-full text-white/60 hover:bg-white/10 hover:text-white group-hover:flex"
            :aria-label="t('player.removeFromQueue')"
            @click="player.removeAt(item.index)"
          >
            <AppIcon name="x" :size="16" />
          </button>
          <button
            type="button"
            class="flex size-8 items-center justify-center rounded-full text-white/40 hover:text-white cursor-grab active:cursor-grabbing touch-none select-none"
            aria-label="Reorder"
            title="Drag to reorder"
            @pointerdown="onPointerDown($event, position)"
            @pointermove="onPointerMove"
            @pointerup="onPointerUp"
            @pointercancel="onPointerCancel"
          >
            <AppIcon
              name="grip"
              :size="16"
            />
          </button>
        </li>
      </TransitionGroup>

      <p
        v-if="!upcoming.length"
        class="px-2 py-8 text-center text-sm text-white/50"
      >
        {{ t('player.queueEnds') }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import AppIcon from '../ui/AppIcon.vue'
import CoverArt from '../ui/CoverArt.vue'
import EqBars from '../ui/EqBars.vue'
import { usePlayer } from '/src/model/player'
import { useLibrary } from '/src/model/library'
import { formatDuration, splitLength } from '/src/lib/format'
import { useI18n } from '/src/i18n'

const player = usePlayer()
const library = useLibrary()
const { t } = useI18n()
const dragFromPos = ref(-1)
const dragOver = ref(-1)
let pointerActive = false
let pointerId = null

const current = computed(() => player.currentTrack.value)
// Long queues render the first stretch only; the rest is still queued.
const upcoming = computed(() => player.upcoming.value.slice(0, 200))

const summary = computed(() => {
  const rest = player.upcoming.value
  const length = splitLength(
    rest.reduce((sum, item) => sum + (item.track.duration || 0), 0)
  )
  const parts = [t('common.tracks', { count: rest.length })]
  if (length.hours || length.minutes) {
    parts.push(
      length.hours
        ? t('common.lengthHours', length)
        : t('common.lengthMinutes', length)
    )
  }
  return parts.join(' · ')
})

function onDragStart(event, pos) {
  dragFromPos.value = pos
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', String(pos))
}

function onDragOver(pos) {
  dragOver.value = pos
}

function onDrop(pos) {
  if (dragFromPos.value >= 0 && dragFromPos.value !== pos) {
    player.moveUpcoming(dragFromPos.value, pos)
  }
  onDragEnd()
}

function onDragEnd() {
  dragFromPos.value = -1
  dragOver.value = -1
}

function onPointerDown(event, pos) {
  if (event.button !== 0 && event.pointerType === 'mouse') return
  pointerActive = true
  pointerId = event.pointerId
  dragFromPos.value = pos
  dragOver.value = pos
  try {
    event.currentTarget.setPointerCapture(event.pointerId)
  } catch {}
}

function onPointerMove(event) {
  if (!pointerActive) return
  const el = document.elementFromPoint(event.clientX, event.clientY)
  const itemEl = el?.closest?.('[data-position]')
  if (itemEl) {
    const pos = parseInt(itemEl.getAttribute('data-position'), 10)
    if (!Number.isNaN(pos)) {
      dragOver.value = pos
    }
  }
}

function onPointerUp(event) {
  if (!pointerActive) return
  if (dragFromPos.value >= 0 && dragOver.value >= 0 && dragFromPos.value !== dragOver.value) {
    player.moveUpcoming(dragFromPos.value, dragOver.value)
  }
  onPointerCancel(event)
}

function onPointerCancel(event) {
  pointerActive = false
  if (pointerId !== null && event?.currentTarget?.releasePointerCapture) {
    try {
      event.currentTarget.releasePointerCapture(pointerId)
    } catch {}
  }
  pointerId = null
  dragFromPos.value = -1
  dragOver.value = -1
}
</script>
