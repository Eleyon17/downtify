<template>
  <div class="flex min-w-0 flex-col gap-8">
    <!-- Header Controls -->
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h2 class="text-display text-xl font-bold">{{ t('nav.stats') }}</h2>
        <p class="text-xs text-muted">
          Separate Rolling (Last 30 Days) and Lifetime listening breakdowns across artists, tracks, albums, genres, and time
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2.5">
        <span v-if="lastUpdatedLabel" class="text-[11px] text-faint tabular">
          Updated {{ lastUpdatedLabel }}
        </span>
        <UiSegmented
          v-model="mode"
          show-labels
          :options="[
            { value: 'rolling', label: 'Rolling (30 Days)' },
            { value: 'lifetime', label: 'Lifetime' },
          ]"
        />
        <UiButton
          variant="ghost"
          size="sm"
          icon="refresh"
          :loading="refreshing"
          @click="fetchStats(true)"
        >
          {{ t('common.refresh') }}
        </UiButton>
        <UiButton
          v-if="lifetimeStats?.total_plays > 0 || rollingStats?.total_plays > 0"
          variant="danger"
          size="sm"
          icon="trash"
          :loading="clearing"
          @click="confirmClearStats"
        >
          Clear Data
        </UiButton>
      </div>
    </div>

    <!-- Initial Loading State -->
    <div v-if="loading && !rawResponse" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <UiSkeleton v-for="n in 8" :key="n" class="h-24 !rounded-panel" />
    </div>

    <!-- Empty State (no plays in lifetime at all) -->
    <div
      v-else-if="!lifetimeStats || (lifetimeStats.total_plays === 0 && rollingStats?.total_plays === 0)"
      class="flex flex-col items-center justify-center gap-3 rounded-panel border border-line-2 bg-surface p-12 text-center"
    >
      <AppIcon name="music" :size="36" class="text-muted" />
      <h3 class="text-base font-semibold">No listening data yet</h3>
      <p class="max-w-sm text-xs text-muted">
        Start playing songs from your library, and your Rolling (30-Day) and Lifetime listening breakdowns will appear here.
      </p>
    </div>

    <!-- Stats Content -->
    <template v-else>
      <!-- Side-by-Side Comparison: Rolling (Last 30 Days) vs Lifetime -->
      <div class="grid gap-4 lg:grid-cols-2">
        <!-- Rolling 30 Days Overview Card -->
        <button
          type="button"
          class="flex flex-col gap-4 rounded-panel border p-5 text-left transition-all"
          :class="
            mode === 'rolling'
              ? 'border-accent bg-accent/[0.06] shadow-sm'
              : 'border-line-2 bg-surface hover:border-line-1'
          "
          @click="mode = 'rolling'"
        >
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <span class="inline-flex size-2.5 rounded-full bg-accent" />
              <span class="text-xs font-bold uppercase tracking-wider text-fg">
                Rolling Stats · Last 30 Days
              </span>
            </div>
            <span
              class="rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
              :class="mode === 'rolling' ? 'bg-accent text-on-accent' : 'bg-surface-2 text-muted'"
            >
              {{ mode === 'rolling' ? 'Viewing' : 'Switch to 30d' }}
            </span>
          </div>
          <div class="grid grid-cols-3 gap-3">
            <div>
              <div class="text-[11px] text-muted">30d Plays</div>
              <div class="text-display text-2xl font-bold text-fg tabular">
                {{ rollingStats.total_plays || 0 }}
              </div>
              <div class="text-[11px] text-faint tabular">
                {{ rollingStats.rolling_daily_plays || 0 }}/day avg
              </div>
            </div>
            <div>
              <div class="text-[11px] text-muted">30d Time</div>
              <div class="text-display text-2xl font-bold text-accent tabular">
                {{ formatTime(rollingStats.total_duration) }}
              </div>
              <div class="text-[11px] text-faint tabular">
                {{ rollingStats.active_days || 0 }}/30 active days
              </div>
            </div>
            <div class="min-w-0">
              <div class="text-[11px] text-muted">30d Top Artist</div>
              <div class="truncate text-display text-base font-bold text-fg">
                {{ rollingStats.top_artists?.[0]?.artist || '—' }}
              </div>
              <div class="truncate text-[11px] text-faint">
                {{
                  rollingStats.top_artists?.[0]?.plays
                    ? `${rollingStats.top_artists[0].plays} plays · ${rollingStats.top_genres?.[0]?.genre || 'Mixed'}`
                    : 'No plays in last 30d'
                }}
              </div>
            </div>
          </div>
        </button>

        <!-- Lifetime Overview Card -->
        <button
          type="button"
          class="flex flex-col gap-4 rounded-panel border p-5 text-left transition-all"
          :class="
            mode === 'lifetime'
              ? 'border-accent bg-accent/[0.06] shadow-sm'
              : 'border-line-2 bg-surface hover:border-line-1'
          "
          @click="mode = 'lifetime'"
        >
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <span class="inline-flex size-2.5 rounded-full bg-fg" />
              <span class="text-xs font-bold uppercase tracking-wider text-fg">
                Lifetime Stats · All-Time History
              </span>
            </div>
            <span
              class="rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
              :class="mode === 'lifetime' ? 'bg-accent text-on-accent' : 'bg-surface-2 text-muted'"
            >
              {{ mode === 'lifetime' ? 'Viewing' : 'Switch to Lifetime' }}
            </span>
          </div>
          <div class="grid grid-cols-3 gap-3">
            <div>
              <div class="text-[11px] text-muted">Lifetime Plays</div>
              <div class="text-display text-2xl font-bold text-fg tabular">
                {{ lifetimeStats.total_plays || 0 }}
              </div>
              <div class="text-[11px] text-faint tabular">
                {{ lifetimeStats.unique_tracks || 0 }} unique songs
              </div>
            </div>
            <div>
              <div class="text-[11px] text-muted">Lifetime Time</div>
              <div class="text-display text-2xl font-bold text-accent tabular">
                {{ formatTime(lifetimeStats.total_duration) }}
              </div>
              <div class="text-[11px] text-faint tabular">
                {{ lifetimeStats.active_days || 0 }} total active days
              </div>
            </div>
            <div class="min-w-0">
              <div class="text-[11px] text-muted">All-Time Top Artist</div>
              <div class="truncate text-display text-base font-bold text-fg">
                {{ lifetimeStats.top_artists?.[0]?.artist || '—' }}
              </div>
              <div class="truncate text-[11px] text-faint">
                {{
                  lifetimeStats.top_artists?.[0]?.plays
                    ? `${lifetimeStats.top_artists[0].plays} plays · ${lifetimeStats.top_genres?.[0]?.genre || 'Mixed'}`
                    : '—'
                }}
              </div>
            </div>
          </div>
        </button>
      </div>

      <!-- Active Scope Banner -->
      <div class="flex items-center justify-between border-b border-line-2 pb-2">
        <div class="flex items-center gap-2">
          <h3 class="text-sm font-bold text-fg">
            {{ mode === 'rolling' ? 'Rolling 30-Day Breakdown' : 'Lifetime All-Time Breakdown' }}
          </h3>
          <span class="rounded-full bg-surface-2 px-2 py-0.5 text-[11px] font-medium text-muted">
            {{ mode === 'rolling' ? 'Last 30 Days of Activity' : 'Complete Listening History' }}
          </span>
        </div>
        <span v-if="stats.first_play_at" class="text-[11px] text-muted tabular">
          {{
            mode === 'lifetime'
              ? `Tracked since ${formatDateShort(stats.first_play_at)}`
              : 'Rolling 30-day window'
          }}
        </span>
      </div>

      <!-- Empty Rolling Window Notice -->
      <div
        v-if="stats.total_plays === 0"
        class="flex flex-col items-center justify-center gap-2 rounded-panel border border-line-2 bg-surface p-8 text-center"
      >
        <p class="text-sm font-semibold text-fg">No plays recorded in the last 30 days</p>
        <p class="text-xs text-muted">
          You have {{ lifetimeStats.total_plays }} lifetime plays on record. Switch to Lifetime to view your all-time history.
        </p>
        <UiButton variant="ghost" size="sm" @click="mode = 'lifetime'">
          View Lifetime Stats
        </UiButton>
      </div>

      <template v-else>
        <!-- Primary Summary Cards (Row 1) -->
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div class="flex flex-col gap-1 rounded-panel border border-line-2 bg-surface p-5 shadow-sm">
            <span class="text-xs font-medium text-muted">
              {{ mode === 'rolling' ? 'Rolling Plays (30d)' : 'Lifetime Plays' }}
            </span>
            <span class="text-display text-3xl font-bold text-fg tabular">{{ stats.total_plays }}</span>
            <span class="text-[11px] text-faint tabular">
              {{ stats.avg_daily_plays || 0 }} plays / active day ({{ stats.active_days || 0 }}d)
            </span>
          </div>
          <div class="flex flex-col gap-1 rounded-panel border border-line-2 bg-surface p-5 shadow-sm">
            <span class="text-xs font-medium text-muted">
              {{ mode === 'rolling' ? 'Time Listened (30d)' : 'Lifetime Time Listened' }}
            </span>
            <span class="text-display text-3xl font-bold text-accent tabular">
              {{ formatTime(stats.total_duration) }}
            </span>
            <span class="text-[11px] text-faint tabular">
              {{ formatTime(stats.avg_daily_duration) }} avg per active day
            </span>
          </div>
          <div class="flex flex-col gap-1 rounded-panel border border-line-2 bg-surface p-5 shadow-sm">
            <span class="text-xs font-medium text-muted">Top Artist</span>
            <span class="truncate text-display text-2xl font-bold text-fg">
              {{ stats.top_artists?.[0]?.artist || '—' }}
            </span>
            <span class="text-[11px] text-faint tabular">
              <template v-if="stats.top_artists?.[0]">
                {{ stats.top_artists[0].plays }} plays · {{ formatTime(stats.top_artists[0].duration) }}
              </template>
              <template v-else>—</template>
            </span>
          </div>
          <div class="flex flex-col gap-1 rounded-panel border border-line-2 bg-surface p-5 shadow-sm">
            <span class="text-xs font-medium text-muted">Top Genre</span>
            <span class="truncate text-display text-2xl font-bold text-fg">
              {{ stats.top_genres?.[0]?.genre || '—' }}
            </span>
            <span class="text-[11px] text-faint tabular">
              <template v-if="stats.top_genres?.[0]">
                {{ stats.top_genres[0].percentage }}% of plays ({{ stats.top_genres[0].plays }})
              </template>
              <template v-else>—</template>
            </span>
          </div>
        </div>

        <!-- Secondary Insight Cards (Row 2) -->
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div class="flex flex-col gap-1 rounded-panel border border-line-2 bg-surface p-4 shadow-sm">
            <span class="text-xs font-medium text-muted">Listening Streak</span>
            <div class="flex items-baseline gap-2">
              <span class="text-display text-2xl font-bold text-fg tabular">
                {{ stats.current_streak || 0 }}d
              </span>
              <span class="text-xs text-muted">current</span>
            </div>
            <span class="text-[11px] text-faint tabular">
              Longest streak: {{ stats.longest_streak || 0 }} {{ stats.longest_streak === 1 ? 'day' : 'days' }}
            </span>
          </div>

          <div class="flex flex-col gap-1 rounded-panel border border-line-2 bg-surface p-4 shadow-sm">
            <span class="text-xs font-medium text-muted">Variety & Discovery</span>
            <div class="flex items-baseline gap-2">
              <span class="text-display text-2xl font-bold text-fg tabular">
                {{ stats.unique_artists || 0 }}
              </span>
              <span class="text-xs text-muted">artists</span>
            </div>
            <span class="text-[11px] text-faint tabular">
              {{ stats.unique_tracks || 0 }} unique songs · {{ stats.unique_albums || 0 }} albums
            </span>
          </div>

          <div class="flex flex-col gap-1 rounded-panel border border-line-2 bg-surface p-4 shadow-sm">
            <span class="text-xs font-medium text-muted">Library Coverage</span>
            <div class="flex items-baseline gap-2">
              <span class="text-display text-2xl font-bold text-fg tabular">
                {{ stats.library_coverage?.artists_pct || 0 }}%
              </span>
              <span class="text-xs text-muted">of artists heard</span>
            </div>
            <span class="text-[11px] text-faint tabular">
              {{ stats.library_coverage?.tracks_played || 0 }} / {{ stats.library_coverage?.total_tracks || 0 }} library tracks ({{ stats.library_coverage?.tracks_pct || 0 }}%)
            </span>
          </div>

          <div class="flex flex-col gap-1 rounded-panel border border-line-2 bg-surface p-4 shadow-sm">
            <span class="text-xs font-medium text-muted">Peak Listening Window</span>
            <span class="truncate text-display text-xl font-bold text-fg">
              {{ stats.peak_hour?.persona || '—' }}
            </span>
            <span class="text-[11px] text-faint tabular">
              <template v-if="stats.peak_hour">
                Peak at {{ stats.peak_hour.label }} ({{ stats.peak_hour.plays }} plays)
              </template>
              <template v-if="stats.peak_day">
                · Best day: {{ stats.peak_day.plays }}
              </template>
            </span>
          </div>
        </div>

        <!-- Daily Activity Timeline -->
        <SettingGroup
          :title="mode === 'rolling' ? 'Rolling 30-Day Activity Timeline' : 'Lifetime Daily Activity Timeline'"
          :description="
            mode === 'rolling'
              ? 'Plays and listening duration across each of the last 30 calendar days'
              : 'Plays recorded per active day across your listening history'
          "
        >
          <div v-if="!dailySeries.length" class="p-5 text-xs text-muted">No daily activity</div>
          <div v-else class="p-5">
            <div class="flex h-36 items-end gap-1.5 overflow-x-auto pb-2 [scrollbar-width:thin]">
              <div
                v-for="d in dailySeries"
                :key="d.day"
                class="group relative flex h-full min-w-[14px] flex-1 flex-col items-center justify-end"
              >
                <!-- Bar -->
                <div
                  class="w-full rounded-t-[4px] transition-all duration-300"
                  :class="
                    d.plays > 0
                      ? 'bg-accent/80 hover:bg-accent'
                      : 'bg-surface-2/70 hover:bg-surface-2'
                  "
                  :style="{
                    height: d.plays > 0
                      ? `${Math.max(8, Math.min(100, (d.plays / maxDailyPlays) * 100))}%`
                      : '4px',
                  }"
                />
                <!-- Tooltip -->
                <div
                  class="pointer-events-none absolute bottom-full z-10 mb-1 hidden whitespace-nowrap rounded-[6px] bg-surface-2 px-2 py-1 text-[10px] text-fg shadow-md group-hover:block"
                >
                  {{ d.day }}: {{ d.plays }} {{ d.plays === 1 ? 'play' : 'plays' }}
                  <template v-if="d.duration"> ({{ formatTime(d.duration) }})</template>
                </div>
              </div>
            </div>
            <div class="flex justify-between pt-2 text-[11px] text-muted tabular">
              <span>{{ dailySeries[0]?.day }}</span>
              <span v-if="stats.peak_day" class="text-faint">
                Peak: {{ stats.peak_day.day }} ({{ stats.peak_day.plays }} plays)
              </span>
              <span>{{ dailySeries[dailySeries.length - 1]?.day }}</span>
            </div>
          </div>
        </SettingGroup>

        <!-- Day of Week & 24-Hour Time of Day Distribution -->
        <div class="grid gap-6 lg:grid-cols-2">
          <SettingGroup title="By Day of the Week" description="When you listen throughout the week">
            <div class="flex h-40 items-end justify-between gap-2 p-5">
              <div
                v-for="w in stats.by_weekday"
                :key="w.weekday"
                class="group relative flex h-full flex-1 flex-col items-center justify-end gap-1.5"
              >
                <span class="text-[10px] font-bold text-fg tabular">{{ w.plays }}</span>
                <div
                  class="w-full rounded-t-[4px] transition-all"
                  :class="w.plays > 0 ? 'bg-accent/75 group-hover:bg-accent' : 'bg-surface-2'"
                  :style="{
                    height: `${Math.max(4, Math.min(78, (w.plays / (maxWeekdayPlays || 1)) * 78))}%`,
                  }"
                />
                <span class="text-[11px] font-medium text-muted">{{ w.weekday }}</span>
                <div
                  v-if="w.duration"
                  class="pointer-events-none absolute bottom-full z-10 mb-1 hidden whitespace-nowrap rounded-[6px] bg-surface-2 px-2 py-1 text-[10px] text-fg shadow-md group-hover:block"
                >
                  {{ w.weekday }}: {{ w.plays }} plays · {{ formatTime(w.duration) }}
                </div>
              </div>
            </div>
          </SettingGroup>

          <SettingGroup title="By Time of Day (24h)" description="Your hourly listening rhythm from midnight to 11 PM">
            <div class="flex flex-col p-5">
              <div class="flex h-32 items-end justify-between gap-1">
                <div
                  v-for="h in stats.by_hour"
                  :key="h.hour"
                  class="group relative flex h-full flex-1 flex-col items-center justify-end"
                >
                  <div
                    class="w-full rounded-t-[3px] transition-all"
                    :class="h.plays > 0 ? 'bg-accent/75 group-hover:bg-accent' : 'bg-surface-2'"
                    :style="{
                      height: h.plays > 0
                        ? `${Math.max(8, Math.min(100, (h.plays / (maxHourPlays || 1)) * 100))}%`
                        : '4px',
                    }"
                  />
                  <div
                    class="pointer-events-none absolute bottom-full z-10 mb-1 hidden whitespace-nowrap rounded-[6px] bg-surface-2 px-2 py-1 text-[10px] text-fg shadow-md group-hover:block"
                  >
                    {{ h.label || `${h.hour}:00` }}: {{ h.plays }} plays
                    <template v-if="h.duration"> · {{ formatTime(h.duration) }}</template>
                  </div>
                </div>
              </div>
              <div class="flex justify-between pt-2 text-[10px] text-muted tabular">
                <span>12 AM</span>
                <span>6 AM</span>
                <span>12 PM</span>
                <span>6 PM</span>
                <span>11 PM</span>
              </div>
            </div>
          </SettingGroup>
        </div>

        <!-- Top Artists & Top Genres Grid -->
        <div class="grid gap-6 lg:grid-cols-2">
          <!-- Top Artists -->
          <SettingGroup
            :title="mode === 'rolling' ? 'Top Artists (Last 30 Days)' : 'Top Artists (Lifetime)'"
            description="Most played artists, unique songs heard, and listening time"
          >
            <div v-if="!stats.top_artists?.length" class="p-5 text-xs text-muted">No artists recorded yet</div>
            <ul v-else class="flex flex-col divide-y divide-line-2">
              <li
                v-for="(a, idx) in stats.top_artists.slice(0, 12)"
                :key="a.artist"
                class="flex flex-col gap-1.5 px-5 py-3 text-xs"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="flex min-w-0 items-center gap-3">
                    <span class="w-5 text-center font-bold text-muted tabular">{{ idx + 1 }}</span>
                    <span class="truncate text-sm font-semibold text-fg">{{ a.artist }}</span>
                    <span
                      v-if="a.unique_tracks"
                      class="shrink-0 rounded-full bg-surface-2 px-2 py-0.5 text-[10px] text-muted tabular"
                    >
                      {{ a.unique_tracks }} {{ a.unique_tracks === 1 ? 'song' : 'songs' }}
                    </span>
                  </div>
                  <div class="flex shrink-0 items-center gap-2 tabular">
                    <span class="font-semibold text-fg">{{ a.plays }} plays</span>
                    <span v-if="a.duration" class="text-muted">· {{ formatTime(a.duration) }}</span>
                  </div>
                </div>
                <div class="ml-8 h-1.5 overflow-hidden rounded-full bg-surface-2">
                  <div
                    class="h-full rounded-full bg-accent/80 transition-all duration-500"
                    :style="{
                      width: `${Math.min(100, Math.max(4, (a.plays / (stats.top_artists[0]?.plays || 1)) * 100))}%`,
                    }"
                  />
                </div>
              </li>
            </ul>
          </SettingGroup>

          <!-- Breakdown by Genre -->
          <SettingGroup
            :title="mode === 'rolling' ? 'Top Genres (Last 30 Days)' : 'Top Genres (Lifetime)'"
            description="Genres you listen to most by share and duration"
          >
            <div v-if="!stats.top_genres?.length" class="p-5 text-xs text-muted">No genre tags available</div>
            <div v-else class="flex flex-col gap-3.5 p-5">
              <div
                v-for="g in stats.top_genres"
                :key="g.genre"
                class="flex flex-col gap-1.5"
              >
                <div class="flex items-center justify-between text-xs">
                  <span class="font-semibold text-fg">{{ g.genre }}</span>
                  <span class="font-medium text-muted tabular">
                    {{ g.plays }} plays
                    <template v-if="g.duration"> · {{ formatTime(g.duration) }}</template>
                    ({{ g.percentage }}%)
                  </span>
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
        </div>

        <!-- Top Tracks & Top Albums Grid -->
        <div class="grid gap-6 lg:grid-cols-2">
          <!-- Top Tracks -->
          <SettingGroup
            :title="mode === 'rolling' ? 'Top Tracks (Last 30 Days)' : 'Top Tracks (Lifetime)'"
            description="Your most frequently played songs"
          >
            <div v-if="!stats.top_tracks?.length" class="p-5 text-xs text-muted">No tracks recorded yet</div>
            <ul v-else class="flex flex-col divide-y divide-line-2">
              <li
                v-for="(tr, idx) in stats.top_tracks.slice(0, 12)"
                :key="tr.track"
                class="flex items-center justify-between gap-3 px-5 py-2.5 text-xs"
              >
                <div class="flex min-w-0 items-center gap-3">
                  <span class="w-5 shrink-0 text-center font-bold text-muted tabular">{{ idx + 1 }}</span>
                  <div class="min-w-0">
                    <div class="truncate font-semibold text-fg">
                      {{ tr.title || tr.track }}
                    </div>
                    <div v-if="tr.artist || tr.album" class="truncate text-[11px] text-muted">
                      {{ [tr.artist, tr.album].filter(Boolean).join(' · ') }}
                    </div>
                  </div>
                </div>
                <div class="flex shrink-0 items-center gap-2 tabular">
                  <span class="font-semibold text-accent">{{ tr.plays }} plays</span>
                  <span v-if="tr.duration" class="text-muted">· {{ formatTime(tr.duration) }}</span>
                </div>
              </li>
            </ul>
          </SettingGroup>

          <!-- Top Albums -->
          <SettingGroup
            :title="mode === 'rolling' ? 'Top Albums (Last 30 Days)' : 'Top Albums (Lifetime)'"
            description="Albums with the most plays and listening time"
          >
            <div v-if="!stats.top_albums?.length" class="p-5 text-xs text-muted">No album plays recorded yet</div>
            <ul v-else class="flex flex-col divide-y divide-line-2">
              <li
                v-for="(alb, idx) in stats.top_albums.slice(0, 12)"
                :key="`${alb.artist}-${alb.album}`"
                class="flex items-center justify-between gap-3 px-5 py-2.5 text-xs"
              >
                <div class="flex min-w-0 items-center gap-3">
                  <span class="w-5 shrink-0 text-center font-bold text-muted tabular">{{ idx + 1 }}</span>
                  <div class="min-w-0">
                    <div class="truncate font-semibold text-fg">{{ alb.album }}</div>
                    <div v-if="alb.artist" class="truncate text-[11px] text-muted">{{ alb.artist }}</div>
                  </div>
                </div>
                <div class="flex shrink-0 items-center gap-2 tabular">
                  <span class="font-semibold text-fg">{{ alb.plays }} plays</span>
                  <span v-if="alb.duration" class="text-muted">· {{ formatTime(alb.duration) }}</span>
                </div>
              </li>
            </ul>
          </SettingGroup>
        </div>

        <!-- Recent Listening History -->
        <SettingGroup
          v-if="stats.recent_plays?.length"
          title="Recent Listening History"
          description="Latest songs played in this window"
        >
          <ul class="flex flex-col divide-y divide-line-2">
            <li
              v-for="(rp, idx) in stats.recent_plays.slice(0, 10)"
              :key="`${rp.at}-${idx}`"
              class="flex items-center justify-between gap-3 px-5 py-2.5 text-xs"
            >
              <div class="flex min-w-0 items-center gap-3">
                <AppIcon name="music" :size="14" class="shrink-0 text-muted" />
                <div class="min-w-0">
                  <span class="font-semibold text-fg">{{ rp.title }}</span>
                  <span v-if="rp.artist" class="text-muted"> — {{ rp.artist }}</span>
                  <span v-if="rp.album" class="text-faint"> · {{ rp.album }}</span>
                </div>
              </div>
              <div class="flex shrink-0 items-center gap-2.5 text-[11px] text-muted tabular">
                <span
                  v-if="rp.genre"
                  class="rounded-full bg-surface-2 px-2 py-0.5 text-[10px] font-medium text-fg"
                >
                  {{ rp.genre }}
                </span>
                <span v-if="rp.duration">{{ formatTime(rp.duration) }}</span>
                <span v-if="rp.at" :title="rp.at">{{ formatRelativeTime(rp.at) }}</span>
              </div>
            </li>
          </ul>
        </SettingGroup>
      </template>

      <!-- Per-User Listening Data Management -->
      <SettingGroup
        title="Listening Data & Privacy"
        description="Real playback time is tracked continuously as you listen; songs skipped within 15 seconds do not count toward your stats."
      >
        <div class="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div class="min-w-0">
            <div class="text-sm font-semibold text-fg">Clear all listening data</div>
            <div class="text-xs text-muted">
              Permanently reset your Rolling (30-Day) and Lifetime listening statistics and playback history for your account only. Your downloaded library, playlists, and liked songs are untouched.
            </div>
          </div>
          <UiButton
            variant="danger"
            size="sm"
            icon="trash"
            :loading="clearing"
            @click="confirmClearStats"
          >
            Clear Listening Data
          </UiButton>
        </div>
      </SettingGroup>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AppIcon from '../ui/AppIcon.vue'
import UiButton from '../ui/UiButton.vue'
import UiSegmented from '../ui/UiSegmented.vue'
import UiSkeleton from '../ui/UiSkeleton.vue'
import SettingGroup from './SettingGroup.vue'
import API from '/src/model/api'
import { useUi } from '/src/model/ui'
import { useI18n } from '/src/i18n'

const { t } = useI18n()
const ui = useUi()
const mode = ref('rolling') // 'rolling' (Last 30 Days) | 'lifetime' (All Time)
const loading = ref(true)
const refreshing = ref(false)
const clearing = ref(false)
const rawResponse = ref(null)
const lastUpdatedAt = ref(null)

const rollingStats = computed(() => {
  if (!rawResponse.value) return { total_plays: 0 }
  return rawResponse.value.rolling || rawResponse.value
})

const lifetimeStats = computed(() => {
  if (!rawResponse.value) return { total_plays: 0 }
  return rawResponse.value.lifetime || rawResponse.value
})

const stats = computed(() => {
  return mode.value === 'lifetime' ? lifetimeStats.value : rollingStats.value
})

const dailySeries = computed(() => {
  if (!stats.value) return []
  if (mode.value === 'rolling' && stats.value.by_day_series?.length) {
    return stats.value.by_day_series
  }
  return stats.value.by_day || []
})

const maxDailyPlays = computed(() => {
  if (!dailySeries.value.length) return 1
  return Math.max(...dailySeries.value.map((d) => d.plays || 0), 1)
})

const maxWeekdayPlays = computed(() => {
  if (!stats.value?.by_weekday?.length) return 1
  return Math.max(...stats.value.by_weekday.map((w) => w.plays || 0), 1)
})

const maxHourPlays = computed(() => {
  if (!stats.value?.by_hour?.length) return 1
  return Math.max(...stats.value.by_hour.map((h) => h.plays || 0), 1)
})

const lastUpdatedLabel = computed(() => {
  if (!lastUpdatedAt.value) return ''
  return lastUpdatedAt.value.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
})

function formatTime(seconds) {
  const secs = Math.round(Number(seconds) || 0)
  if (secs <= 0) return '0m'
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m`
  const hrs = Math.floor(mins / 60)
  const remMins = mins % 60
  if (hrs < 24) return `${hrs}h ${remMins}m`
  const daysCount = Math.floor(hrs / 24)
  const remHrs = hrs % 24
  return `${daysCount}d ${remHrs}h ${remMins}m`
}

function formatDateShort(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return String(iso).slice(0, 10)
  }
}

function formatRelativeTime(iso) {
  if (!iso) return ''
  try {
    const diffSec = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
    if (diffSec < 60) return 'just now'
    const mins = Math.floor(diffSec / 60)
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    const daysCount = Math.floor(hrs / 24)
    if (daysCount < 30) return `${daysCount}d ago`
    return formatDateShort(iso)
  } catch {
    return String(iso).slice(0, 10)
  }
}

async function fetchStats(isManualRefresh = false) {
  if (isManualRefresh) {
    refreshing.value = true
  } else {
    loading.value = true
  }
  try {
    const daysParam = mode.value === 'lifetime' ? 0 : 30
    const res = await API.getMyStats(daysParam)
    rawResponse.value = res.data
    lastUpdatedAt.value = new Date()
  } catch (err) {
    if (!isManualRefresh) rawResponse.value = null
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function confirmClearStats() {
  const ok = await ui.confirm({
    title: 'Clear all listening data?',
    body: 'Are you sure you want to permanently delete all of your Rolling (30-Day) and Lifetime listening statistics and playback history? This only clears data for your account — your library, playlists, and liked songs will not be affected.',
    confirmLabel: 'Clear my listening data',
    danger: true,
  })
  if (!ok) return
  clearing.value = true
  try {
    await API.clearMyStats()
    ui.toast('Listening data cleared', { kind: 'success' })
    await fetchStats(true)
  } catch (err) {
    ui.toast('Failed to clear listening data', { kind: 'error' })
  } finally {
    clearing.value = false
  }
}

onMounted(() => fetchStats(false))
</script>
