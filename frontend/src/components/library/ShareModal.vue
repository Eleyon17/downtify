<template>
  <UiModal
    :open="shares.shareModalOpen.value"
    :title="
      shares.currentShare.value?.kind === 'playlist'
        ? t('share.titlePlaylist')
        : t('share.titleTrack')
    "
    :description="t('share.description')"
    @close="shares.closeShareModal"
  >
    <div class="flex flex-col gap-4">
      <div v-if="shares.currentShare.value?.title" class="flex items-center gap-3 rounded-[12px] bg-surface-2 p-3">
        <AppIcon
          :name="shares.currentShare.value?.kind === 'playlist' ? 'playlist' : 'music'"
          :size="22"
          class="text-accent shrink-0"
        />
        <div class="min-w-0 flex-1">
          <p class="truncate font-semibold text-sm">{{ shares.currentShare.value?.title }}</p>
          <p class="text-xs text-muted">{{ t('share.playingShared') }}</p>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <input
          type="text"
          readonly
          :value="shares.currentShare.value?.url || ''"
          class="h-10 min-w-0 flex-1 rounded-[10px] border border-line-2 bg-surface-1 px-3 text-sm text-fg select-all focus:border-accent focus:outline-none"
          @focus="$event.target.select()"
        />
        <UiButton
          variant="primary"
          :icon="copied ? 'check' : 'copy'"
          @click="handleCopy"
        >
          {{ copied ? t('share.linkCopied') : t('share.copyLink') }}
        </UiButton>
      </div>

      <div v-if="canNativeShare" class="pt-1">
        <UiButton
          variant="secondary"
          icon="share"
          class="w-full"
          @click="handleNativeShare"
        >
          {{ t('actions.share') }}...
        </UiButton>
      </div>
    </div>

    <template #footer>
      <UiButton variant="ghost" @click="shares.closeShareModal">
        {{ t('common.close') }}
      </UiButton>
    </template>
  </UiModal>
</template>

<script setup>
import { computed, ref } from 'vue'
import AppIcon from '../ui/AppIcon.vue'
import UiButton from '../ui/UiButton.vue'
import UiModal from '../ui/UiModal.vue'
import { useShares } from '/src/model/shares'
import { useI18n } from '/src/i18n'

const { t } = useI18n()
const shares = useShares()
const copied = ref(false)

const canNativeShare = computed(
  () => typeof navigator !== 'undefined' && !!navigator.share
)

async function handleCopy() {
  const url = shares.currentShare.value?.url
  if (!url) return
  const ok = await shares.copyToClipboard(url)
  if (ok) {
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2500)
  }
}

async function handleNativeShare() {
  const item = shares.currentShare.value
  if (!item || !navigator?.share) return
  try {
    await navigator.share({
      title: item.title,
      text: t('share.playingShared'),
      url: item.url,
    })
  } catch {
    // User aborted or unallowed
  }
}
</script>
