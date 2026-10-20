<template>
  <div class="relative flex h-full min-h-0 flex-col">
    <!-- Quick translate toggle button -->
    <div
      v-if="hasTranslations"
      class="absolute top-2 right-2 z-10"
    >
      <button
        type="button"
        class="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-all backdrop-blur-md"
        :class="
          translateLyrics
            ? 'border border-accent/40 bg-accent/25 text-white'
            : 'border border-white/10 bg-white/10 text-white/50 hover:text-white'
        "
        :title="t('settings.translateLyrics')"
        @click="translateLyrics = !translateLyrics"
      >
        <AppIcon name="globe" :size="13" />
        <span v-if="!compact">{{ t('player.translate') }}</span>
      </button>
    </div>

    <div
      v-if="loading"
      class="flex flex-1 flex-col justify-center gap-5 px-2"
      aria-hidden="true"
    >
      <div
        v-for="n in 6"
        :key="n"
        class="h-7 animate-pulse rounded-lg bg-white/10"
        :style="{ width: `${50 + ((n * 37) % 45)}%` }"
      />
    </div>

    <div
      v-else-if="lines.length"
      ref="scroller"
      class="relative flex-1 overflow-y-auto overscroll-contain px-2 py-[min(30vh,9rem)] [mask-image:linear-gradient(transparent,#000_18%,#000_82%,transparent)] [scrollbar-width:none]"
      @wheel.passive="userScrolled"
      @touchmove.passive="userScrolled"
    >
      <button
        v-for="(line, i) in lines"
        :key="i"
        :ref="(el) => (lineEls[i] = el)"
        type="button"
        class="text-display block w-full origin-left py-2 text-left leading-tight font-semibold transition-all duration-300"
        :class="[
          compact ? 'now-playing-lyric-compact' : 'now-playing-lyric',
          i === active
            ? 'scale-100 text-white'
            : i < active
              ? 'scale-[0.97] text-white/35 hover:text-white/60'
              : 'scale-[0.97] text-white/55 hover:text-white/75',
        ]"
        @click="player.seek(line.time)"
      >
        <span class="block">{{ line.text || '♪' }}</span>
        <span
          v-if="translateLyrics && line.translation && line.translation !== line.text"
          class="mt-1 block font-normal tracking-normal text-white/65"
          :class="compact ? 'text-xs text-white/55' : 'text-sm text-white/65'"
        >
          {{ line.translation }}
        </span>
      </button>
    </div>

    <div
      v-else-if="plain"
      class="flex-1 overflow-y-auto px-2 py-6 [scrollbar-width:thin]"
    >
      <div v-if="translateLyrics && pairedPlainLines.length" class="space-y-4">
        <div
          v-for="(item, idx) in pairedPlainLines"
          :key="idx"
          class="leading-relaxed"
        >
          <p class="now-playing-lyric text-display font-medium text-white/80">
            {{ item.original }}
          </p>
          <p
            v-if="item.translation && item.translation !== item.original"
            class="mt-1 font-normal tracking-normal text-white/60"
            :class="compact ? 'text-xs' : 'text-sm'"
          >
            {{ item.translation }}
          </p>
        </div>
      </div>
      <p
        v-else
        class="now-playing-lyric text-display leading-relaxed font-medium whitespace-pre-line text-white/80"
      >
        {{ plain }}
      </p>
      <p class="mt-6 text-xs text-white/45">
        {{ t('player.lyricsNotSynced') }}
      </p>
    </div>

    <div
      v-else
      class="flex flex-1 flex-col items-center justify-center gap-3 text-center"
    >
      <AppIcon name="lyrics" :size="32" class="text-white/35" />
      <p class="text-sm text-white/60">{{ t('player.noLyrics') }}</p>
      <p class="max-w-xs text-xs text-white/40">
        {{ t('player.noLyricsHint') }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import AppIcon from '../ui/AppIcon.vue'
import { usePlayer } from '/src/model/player'
import { usePlayerPrefs } from '/src/model/playerPrefs'
import { loadLyrics } from '/src/model/lyrics'
import { activeLineIndex } from '/src/lib/lrc'
import { useI18n, currentLocale } from '/src/i18n'

const props = defineProps({
  compact: { type: Boolean, default: false },
})

const player = usePlayer()
const { translateLyrics } = usePlayerPrefs()
const { t } = useI18n()
const loading = ref(false)
const lines = ref([])
const plain = ref('')
const translatedPlain = ref('')
const scroller = ref(null)
const lineEls = ref([])
let manualUntil = 0

watch(
  [() => player.currentTrack.value?.file, () => currentLocale.value],
  async ([file, locale]) => {
    lines.value = []
    plain.value = ''
    translatedPlain.value = ''
    lineEls.value = []
    if (!file) return
    loading.value = true
    const result = await loadLyrics(file, locale)
    if (player.currentTrack.value?.file !== file) return
    lines.value = result.lines
    plain.value = result.plain
    translatedPlain.value = result.translatedPlain || ''
    loading.value = false
  },
  { immediate: true }
)

const hasTranslations = computed(() => {
  return (
    lines.value.some((l) => Boolean(l.translation)) ||
    Boolean(translatedPlain.value)
  )
})

const pairedPlainLines = computed(() => {
  if (!plain.value) return []
  const orig = plain.value.split(/\r?\n/)
  const trans = (translatedPlain.value || '').split(/\r?\n/)
  return orig.map((line, idx) => ({
    original: line,
    translation: trans[idx] || '',
  }))
})

const active = computed(() =>
  activeLineIndex(lines.value, player.currentTime.value + 0.25)
)

function userScrolled() {
  // Leave the user's scroll position alone for a moment.
  manualUntil = Date.now() + 4000
}

watch(active, async (index) => {
  if (index < 0 || Date.now() < manualUntil) return
  await nextTick()
  lineEls.value[index]?.scrollIntoView({ block: 'center', behavior: 'smooth' })
})
</script>
