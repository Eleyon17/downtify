<template>
  <div
    class="relative isolate shrink-0 overflow-hidden"
    :class="[round ? 'rounded-full' : rounded, shadow ? 'shadow-cover' : '']"
    :style="{ background: placeholder }"
  >
    <div
      v-if="mosaic.length >= 2"
      class="grid size-full"
      :class="mosaic.length === 2 ? 'grid-cols-2' : 'grid-cols-2 grid-rows-2'"
    >
      <img
        v-for="(url, i) in mosaic.slice(0, 4)"
        :key="i"
        :src="url"
        alt=""
        loading="lazy"
        decoding="async"
        referrerpolicy="no-referrer"
        class="size-full min-h-0 min-w-0 object-cover"
        :class="i === 0 && mosaic.length === 3 ? 'row-span-2' : ''"
      />
    </div>
    <img
      v-else-if="imageSrc && !failed"
      :src="imageSrc"
      :alt="alt"
      :loading="letterSize <= 24 ? 'eager' : 'lazy'"
      decoding="async"
      referrerpolicy="no-referrer"
      class="size-full object-cover transition-opacity duration-300"
      :class="ready ? 'opacity-100' : 'opacity-0'"
      @load="ready = true"
      @error="onImageError"
    />
    <div
      v-if="showFallback"
      class="absolute inset-0 flex items-center justify-center"
      :class="round || symbol ? '' : 'items-end justify-start p-[8%]'"
    >
      <AppIcon
        v-if="!letters"
        :name="icon"
        :size="iconSize"
        :class="symbol ? 'text-white/90' : 'text-white/35'"
      />
      <span
        v-else
        class="text-display leading-none font-bold text-white/25 select-none"
        :style="{ fontSize: `${letterSize}px` }"
        >{{ letters }}</span
      >
    </div>
    <slot />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import { hueFor, initials } from '/src/lib/format'

const props = defineProps({
  src: { type: String, default: '' },
  covers: { type: Array, default: () => [] },
  alt: { type: String, default: '' },
  name: { type: String, default: '' },
  icon: { type: String, default: 'music' },
  round: { type: Boolean, default: false },
  rounded: { type: String, default: 'rounded-cover' },
  shadow: { type: Boolean, default: false },
  letterSize: { type: Number, default: 48 },
  iconSize: { type: Number, default: 28 },
  // The icon on a fixed tile, whatever art or name there is — for
  // collections that are recognised by what they are, like liked songs.
  symbol: { type: Boolean, default: false },
  // Optional image or list of images tried when `src` fails to load,
  // before falling back to initials.
  fallback: { type: [String, Array], default: '' },
})

const failed = ref(false)
const ready = ref(false)
const fallbackIndex = ref(0)
const currentSrc = ref('')

const fallbackList = computed(() => {
  if (Array.isArray(props.fallback)) {
    return props.fallback.filter((u) => u && typeof u === 'string')
  }
  if (props.fallback && typeof props.fallback === 'string') {
    return [props.fallback]
  }
  return []
})

const fallbackKey = computed(() =>
  Array.isArray(props.fallback)
    ? props.fallback.filter(Boolean).join('|')
    : String(props.fallback || '')
)

watch(
  () => [props.src, fallbackKey.value],
  () => {
    failed.value = false
    ready.value = false
    const initialSrc = props.src || fallbackList.value[0] || ''
    currentSrc.value = initialSrc
    fallbackIndex.value = props.src ? 0 : 1
  },
  { immediate: true }
)

function onImageError() {
  while (fallbackIndex.value < fallbackList.value.length) {
    const nextCandidate = fallbackList.value[fallbackIndex.value++]
    if (nextCandidate && nextCandidate !== currentSrc.value) {
      currentSrc.value = nextCandidate
      ready.value = false
      return
    }
  }
  failed.value = true
}

// A real cover always wins: a playlist with its own artwork shows it
// instead of a grid of the tracks it happens to contain.
const mosaic = computed(() =>
  props.symbol || props.src || fallbackList.value.length ? [] : props.covers.filter(Boolean)
)
const imageSrc = computed(() => {
  if (props.symbol) return ''
  return currentSrc.value || mosaic.value[0] || ''
})
const letters = computed(() => (props.symbol ? '' : initials(props.name)))
const showFallback = computed(
  () => mosaic.value.length < 2 && (!imageSrc.value || failed.value)
)
// Placeholder tint derived from the name, so an album without art keeps
// the same colour everywhere.
const placeholder = computed(() =>
  props.symbol
    ? 'linear-gradient(135deg, oklch(0.5 0.17 305), oklch(0.62 0.14 245))'
    : `oklch(0.42 0.07 ${hueFor(props.name || props.alt)})`
)
</script>
