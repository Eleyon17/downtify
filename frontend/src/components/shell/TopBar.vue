<template>
  <!-- Thin trigger zone at top of viewport so hovering top edge reveals the header -->
  <div
    v-if="!isAlwaysVisible && !isRevealed"
    class="fixed top-0 inset-x-0 h-3 z-40 pointer-events-auto"
    @mouseenter="isHovered = true"
  />

  <header
    class="sticky top-0 z-30 transition-[height,max-height,opacity,background-color,border-color] duration-300 ease-in-out border-b"
    :class="
      isRevealed
        ? 'h-16 md:h-[72px] max-h-20 border-line bg-bg/85 backdrop-blur-xl supports-[backdrop-filter]:bg-bg/70 opacity-100 pointer-events-auto'
        : 'h-0 max-h-0 border-transparent bg-transparent opacity-0 overflow-hidden pointer-events-none'
    "
    @mouseenter="isHovered = true"
    @mouseleave="isHovered = false"
  >
    <div
      class="mx-auto flex h-16 max-w-[1680px] items-center gap-2 px-4 sm:gap-3 sm:px-6 md:h-[72px] lg:px-10 transition-transform duration-300"
      :class="isRevealed ? 'translate-y-0' : '-translate-y-2'"
    >
      <RouterLink
        :to="{ name: 'Home' }"
        class="md:hidden"
        :title="t('nav.home')"
      >
        <AppLogo :size="30" />
      </RouterLink>
      <div class="hidden items-center gap-1 md:flex">
        <UiIconButton
          icon="chevron-left"
          :label="t('nav.back')"
          size="sm"
          :disabled="!canGoBack"
          @click="router.back()"
        />
        <UiIconButton
          icon="chevron-right"
          :label="t('nav.forward')"
          size="sm"
          :disabled="!canGoForward"
          @click="router.forward()"
        />
      </div>
      <GlobalSearch
        class="min-w-0 flex-1 md:max-w-xl"
        :is-hovered="isHovered"
        @focus="isSearchFocused = true"
        @blur="isSearchFocused = false"
      />
      <div class="ml-auto hidden items-center gap-1 sm:flex">
        <UiIconButton
          icon="keyboard"
          :label="t('shortcuts.title')"
          class="hidden lg:inline-flex"
          @click="openShortcuts"
        />
        <UiIconButton
          :icon="theme.resolved.value === 'dark' ? 'sun' : 'moon'"
          :label="
            theme.resolved.value === 'dark'
              ? t('settings.themeLight')
              : t('settings.themeDark')
          "
          @click="theme.toggle()"
        />
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLogo from '../ui/AppLogo.vue'
import UiIconButton from '../ui/UiIconButton.vue'
import GlobalSearch from './GlobalSearch.vue'
import { useTheme } from '/src/model/theme'
import { useI18n } from '/src/i18n'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const theme = useTheme()
const isHovered = ref(false)
const isSearchFocused = ref(false)

const isAlwaysVisible = computed(
  () => route.name === 'Search' || String(route.path || '').startsWith('/search')
)

const isRevealed = computed(
  () => isAlwaysVisible.value || isHovered.value || isSearchFocused.value
)

function handleGlobalKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    isSearchFocused.value = true
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
})

// vue-router records where history can go in history.state.
const canGoBack = computed(() => {
  route.fullPath
  return !!window.history.state?.back
})
const canGoForward = computed(() => {
  route.fullPath
  return !!window.history.state?.forward
})

function openShortcuts() {
  window.dispatchEvent(new KeyboardEvent('keydown', { key: '?' }))
}
</script>
