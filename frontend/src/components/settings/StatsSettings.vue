<template>
  <div class="flex min-w-0 flex-col gap-8">
    <!-- Header Controls -->
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h2 class="text-display text-xl font-bold">{{ t('nav.stats') }}</h2>
        <p class="text-xs text-muted">Your listening trends across artists, genres, and days</p>
      </div>
      <div class="flex items-center gap-2">
        <UiSegmented
          v-model="days"
          :options="[
            { value: 30, label: '30 Days' },
            { value: 90, label: '90 Days' },
            { value: 365, label: '1 Year' },
          ]"
        />
        <UiButton variant="ghost" icon="refresh" :loading="loading" @click="fetchStats" />
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <UiSkeleton v-for="n in 4" :key="n" class="h-24 !rounded-panel" />
    </div>

    <!-- Empty State -->
    <div
      v-else-if="!stats || stats.total_plays === 0"
      class="flex flex-col items-center justify-center gap-3 rounded-panel border border-line-2 bg-surface p-12 text-center"
    >
      <AppIcon name="music" :size="36" class="text-muted" />
      <h3 class="text-base font-semibold">No listening data yet</h3>
      <p class="max-w-sm text-xs text-muted">
        Start playing songs from your library, and your listening breakdown by genre, artist, and daily activity will appear here.
      </p>
    </div>

    <!-- Stats Content -->
    <template v-else>
      <!-- Summary Cards -->
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div class="flex flex-col gap-1 rounded-panel border border-line-2 bg-surface p-5 shadow-sm">
          <span class="text-xs font-medium text-muted">Total Plays</span>
          <span class="text-display text-3xl font-bold text-fg">{{ stats.total_plays }}</span>
          <span class="text-[11px] text-faint">tracks started</span>
        </div>
        <div class="flex flex-col gap-1 rounded-panel border border-line-2 bg-surface p-5 shadow-sm">
          <span class="text-xs font-medium text-muted">Time Listened</span>
          <span class="text-display text-3xl font-bold text-accent">{{ formatTime(stats.total_duration) }}</span>
          <span class="text-[11px] text-faint">approx. listening time</span>
        </div>
        <div class="flex flex-col gap-1 rounded-panel border border-line-2 bg-surface p-5 shadow-sm">
          <span class="text-xs font-medium text-muted">Top Artist</span>
          <span class="truncate text-display text-2xl font-bold text-fg">
            {{ stats.top_artists?.[0]?.artist || '—' }}
          </span>
          <span class="text-[11px] text-faint">
            {{ stats.top_artists?.[0]?.plays ? `${stats.top_artists[0].plays} plays` : '' }}
          </span>
        </div>
        <div class="flex flex-col gap-1 rounded-panel border border-line-2 bg-surface p-5 shadow-sm">
          <span class="text-xs font-medium text-muted">Top Genre</span>
          <span class="truncate text-display text-2xl font-bold text-fg">
            {{ stats.top_genres?.[0]?.genre || '—' }}
          </span>
          <span class="text-[11px] text-faint">
            {{ stats.top_genres?.[0]?.percentage ? `${stats.top_genres[0].percentage}% of total` : '' }}
          </span>
        </div>
      </div>

      <!-- Genres & Artists Grid -->
      <div class="grid gap-6 lg:grid-cols-2">
        <!-- Breakdown by Genre -->
        <SettingGroup title="Top Genres" description="Genres you listen to most">
          <div v-if="!stats.top_genres?.length" class="p-5 text-xs text-muted">No genre tags available</div>
          <div v-else class="flex flex-col gap-3.5 p-5">
            <div
              v-for="g in stats.top_genres"
              :key="g.genre"
              class="flex flex-col gap-1.5"
            >
              <div class="flex items-center justify-between text-xs">
                <span class="font-semibold text-fg">{{ g.genre }}</span>
                <span class="tabular font-medium text-muted">{{ g.plays }} plays ({{ g.percentage }}%)</span>
              </div>
              <div class="h-2 w-full overflow-hidden rounded-full bg-surface-2">
                <div
                  class="h-full rounded-full bg-accent transition-all duration-500"
                  :style="{ width: `${Math.min(100, Math.max(4, g.percentage))}%` }"
                />
              </div>
            </div>
          </div>
        </SettingGroup>

        <!-- Top Artists -->
        <SettingGroup title="Top Artists" description="Most played artists and listening time">
          <div v-if="!stats.top_artists?.length" class="p-5 text-xs text-muted">No artists recorded yet</div>
          <ul v-else class="flex flex-col divide-y divide-line-2">
            <li
              v-for="(a, idx) in stats.top_artists"
              :key="a.artist"
              class="flex items-center justify-between px-5 py-3 text-xs"
            >
              <div class="flex items-center gap-3 min-w-0">
                <span class="w-5 text-center font-bold text-muted tabular">{{ idx + 1 }}</span>
                <span class="truncate font-semibold text-fg text-sm">{{ a.artist }}</span>
              </div>
              <div class="flex items-center gap-3 shrink-0 tabular">
                <span class="font-medium text-fg">{{ a.plays }} plays</span>
                <span v-if="a.duration" class="text-muted">· {{ formatTime(a.duration) }}</span>
              </div>
            </li>
          </ul>
        </SettingGroup>
      </div>

      <!-- Daily Activity Timeline -->
      <SettingGroup title="Listening Activity by Day" description="Plays recorded per day">
        <div v-if="!stats.by_day?.length" class="p-5 text-xs text-muted">No daily activity</div>
        <div v-else class="p-5">
          <div class="flex h-36 items-end gap-1.5 overflow-x-auto pb-2 [scrollbar-width:thin]">
            <div
              v-for="d in stats.by_day"
              :key="d.day"
              class="group relative flex flex-1 min-w-[18px] flex-col items-center justify-end h-full"
            >
              <!-- Bar -->
              <div
                class="w-full rounded-t-[4px] bg-accent/80 hover:bg-accent transition-all duration-300"
                :style="{ height: `${Math.max(6, Math.min(100, (d.plays / maxDailyPlays) * 100))}%` }"
              />
              <!-- Tooltip -->
              <div
                class="pointer-events-none absolute bottom-full mb-1 hidden whitespace-nowrap rounded-[6px] bg-surface-2 px-2 py-1 text-[10px] text-fg shadow-md group-hover:block z-10"
              >
                {{ d.day }}: {{ d.plays }} plays
              </div>
            </div>
          </div>
          <div class="flex justify-between pt-2 text-[11px] text-muted">
            <span>{{ stats.by_day[0]?.day }}</span>
            <span>{{ stats.by_day[stats.by_day.length - 1]?.day }}</span>
          </div>
        </div>
      </SettingGroup>

      <!-- Day of Week & Hour Distribution -->
      <div class="grid gap-6 lg:grid-cols-2">
        <SettingGroup title="By Day of the Week" description="When you listen throughout the week">
          <div class="flex items-end justify-between gap-2 p-5 h-36">
            <div
              v-for="w in stats.by_weekday"
              :key="w.weekday"
              class="flex flex-1 flex-col items-center gap-1.5 h-full justify-end"
            >
              <span class="text-[10px] font-bold text-fg tabular">{{ w.plays }}</span>
              <div
                class="w-full rounded-t-[4px] bg-accent/75"
                :style="{ height: `${Math.max(4, Math.min(80, (w.plays / (maxWeekdayPlays || 1)) * 80))}%` }"
              />
              <span class="text-[11px] font-medium text-muted">{{ w.weekday }}</span>
            </div>
          </div>
        </SettingGroup>

        <!-- Top Tracks -->
        <SettingGroup title="Top Tracks" description="Your most frequently played songs">
          <div v-if="!stats.top_tracks?.length" class="p-5 text-xs text-muted">No tracks recorded yet</div>
          <ul v-else class="flex flex-col divide-y divide-line-2">
            <li
              v-for="(t, idx) in stats.top_tracks.slice(0, 10)"
              :key="t.track"
              class="flex items-center justify-between px-5 py-2.5 text-xs"
            >
              <div class="flex items-center gap-2.5 min-w-0">
                <span class="w-4 text-center font-bold text-muted tabular">{{ idx + 1 }}</span>
                <span class="truncate font-medium text-fg">{{ t.track }}</span>
              </div>
              <span class="shrink-0 font-semibold text-accent tabular">{{ t.plays }} plays</span>
            </li>
          </ul>
        </SettingGroup>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import AppIcon from '../ui/AppIcon.vue'
import UiButton from '../ui/UiButton.vue'
import UiSegmented from '../ui/UiSegmented.vue'
import UiSkeleton from '../ui/UiSkeleton.vue'
import SettingGroup from './SettingGroup.vue'
import API from '/src/model/api'
import { useI18n } from '/src/i18n'

const { t } = useI18n()
const days = ref(90)
const loading = ref(true)
const stats = ref(null)

const maxDailyPlays = computed(() => {
  if (!stats.value?.by_day?.length) return 1
  return Math.max(...stats.value.by_day.map((d) => d.plays), 1)
})

const maxWeekdayPlays = computed(() => {
  if (!stats.value?.by_weekday?.length) return 1
  return Math.max(...stats.value.by_weekday.map((w) => w.plays), 1)
})

function formatTime(seconds) {
  const secs = Math.round(Number(seconds) || 0)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m`
  const hrs = Math.floor(mins / 60)
  const remMins = mins % 60
  return `${hrs}h ${remMins}m`
}

async function fetchStats() {
  loading.value = true
  try {
    const res = await API.getMyStats(days.value)
    stats.value = res.data
  } catch (err) {
    stats.value = null
  } finally {
    loading.value = false
  }
}

watch(days, fetchStats)
onMounted(fetchStats)
</script>
