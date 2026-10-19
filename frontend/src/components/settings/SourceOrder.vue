<template>
  <ProviderOrder
    :model-value="modelValue"
    :providers="providers"
    :first-when-enabled="['slskd']"
    @update:model-value="(value) => $emit('update:modelValue', value)"
    @enabled="(id) => id === 'slskd' && $emit('enable-slskd')"
  >
    <template #badge="{ row }">
      <SourceBadge :source="row.id" />
    </template>
    <template #extra="{ row }">
      <div class="flex w-full flex-col gap-1.5">
        <div class="flex items-center justify-between pb-1">
          <span class="text-xs font-medium text-muted">
            {{ t('settings.sourceTargetsOrder') }}
          </span>
          <button
            type="button"
            class="flex items-center gap-1 text-xs font-medium text-accent hover:underline"
            @click="addTarget(row.id)"
          >
            <AppIcon name="plus" :size="12" />
            {{ t('settings.addTarget') }}
          </button>
        </div>
        <div
          v-for="(target, idx) in getTargets(row.id)"
          :key="idx"
          class="flex flex-wrap items-center gap-2 rounded-[8px] border border-line-2/40 bg-surface/50 px-2.5 py-1.5"
        >
          <span class="w-4 text-center text-xs font-semibold text-muted">
            {{ idx + 1 }}.
          </span>
          <UiSelect
            size="sm"
            :model-value="target.format"
            :options="formatOptions"
            :label="t('settings.formatLabel')"
            @update:model-value="(val) => setFormat(row.id, idx, val)"
          />
          <UiSelect
            size="sm"
            :model-value="target.format === 'flac' ? 'lossless' : target.bitrate"
            :options="
              target.format === 'flac'
                ? losslessBitrateOptions
                : lossyBitrateOptions
            "
            :disabled="target.format === 'flac'"
            :label="t('settings.bitrateLabel')"
            @update:model-value="(val) => setBitrate(row.id, idx, val)"
          />
          <div class="ml-auto flex items-center gap-0.5">
            <UiIconButton
              icon="chevron-up"
              size="sm"
              :disabled="idx === 0"
              :label="t('settings.moveUp')"
              @click="moveTarget(row.id, idx, -1)"
            />
            <UiIconButton
              icon="chevron-down"
              size="sm"
              :disabled="idx === getTargets(row.id).length - 1"
              :label="t('settings.moveDown')"
              @click="moveTarget(row.id, idx, 1)"
            />
            <UiIconButton
              icon="trash"
              size="sm"
              :disabled="getTargets(row.id).length <= 1"
              :label="t('settings.removeTarget')"
              @click="removeTarget(row.id, idx)"
            />
          </div>
        </div>
      </div>
    </template>
  </ProviderOrder>
</template>

<script setup>
import { computed } from 'vue'
import ProviderOrder from './ProviderOrder.vue'
import SourceBadge from '../ui/SourceBadge.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiIconButton from '../ui/UiIconButton.vue'
import AppIcon from '../ui/AppIcon.vue'
import { useI18n } from '/src/i18n'

const props = defineProps({
  modelValue: { type: Array, required: true },
  targets: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:modelValue', 'update:targets', 'enable-slskd'])
const { t } = useI18n()

const defaultTargets = {
  slskd: [
    { format: 'flac', bitrate: 'lossless' },
    { format: 'mp3', bitrate: '320' },
  ],
  'youtube-music': [{ format: 'mp3', bitrate: '320' }],
  youtube: [{ format: 'mp3', bitrate: '320' }],
}

const formatOptions = [
  { value: 'flac', label: 'FLAC' },
  { value: 'mp3', label: 'MP3' },
  { value: 'ogg', label: 'OGG' },
  { value: 'opus', label: 'Opus' },
  { value: 'm4a', label: 'M4A' },
]

const lossyBitrateOptions = [
  { value: '320', label: '320 kbps' },
  { value: '256', label: '256 kbps' },
  { value: '192', label: '192 kbps' },
  { value: '128', label: '128 kbps' },
]

const losslessBitrateOptions = computed(() => [
  { value: 'lossless', label: t('settings.losslessBitrate') },
])

function getTargets(id) {
  const current = props.targets && props.targets[id]
  if (Array.isArray(current) && current.length > 0) {
    return current
  }
  return defaultTargets[id] || [{ format: 'mp3', bitrate: '320' }]
}

function updateSourceTargets(id, list) {
  const current = props.targets ? { ...props.targets } : {}
  for (const prov of ['slskd', 'youtube-music', 'youtube']) {
    if (!current[prov]) {
      current[prov] = [
        ...(defaultTargets[prov] || [{ format: 'mp3', bitrate: '320' }]),
      ]
    }
  }
  current[id] = list
  emit('update:targets', current)
}

function addTarget(id) {
  const list = [...getTargets(id)]
  const hasFlac = list.some((t) => t.format === 'flac')
  const newTarget =
    id === 'slskd' && !hasFlac
      ? { format: 'flac', bitrate: 'lossless' }
      : { format: 'mp3', bitrate: '320' }
  list.push(newTarget)
  updateSourceTargets(id, list)
}

function removeTarget(id, index) {
  const list = [...getTargets(id)]
  if (list.length > 1) {
    list.splice(index, 1)
    updateSourceTargets(id, list)
  }
}

function moveTarget(id, index, offset) {
  const list = [...getTargets(id)]
  const targetIndex = index + offset
  if (targetIndex < 0 || targetIndex >= list.length) return
  const [item] = list.splice(index, 1)
  list.splice(targetIndex, 0, item)
  updateSourceTargets(id, list)
}

function setFormat(id, index, newFormat) {
  const list = getTargets(id).map((item, i) => {
    if (i !== index) return item
    const br =
      newFormat === 'flac'
        ? 'lossless'
        : item.bitrate === 'lossless'
          ? '320'
          : item.bitrate
    return { ...item, format: newFormat, bitrate: br }
  })
  updateSourceTargets(id, list)
}

function setBitrate(id, index, newBitrate) {
  const list = getTargets(id).map((item, i) => {
    if (i !== index) return item
    return { ...item, bitrate: newBitrate }
  })
  updateSourceTargets(id, list)
}

// slskd first: it's the only lossless source, so when it's on it leads.
const providers = computed(() => [
  {
    id: 'slskd',
    title: t('settings.sourceSlskd'),
    description: t('settings.sourceSlskdHint'),
  },
  {
    id: 'youtube-music',
    title: t('settings.sourceYtm'),
    description: t('settings.sourceYtmHint'),
  },
  {
    id: 'youtube',
    title: t('settings.sourceYt'),
    description: t('settings.sourceYtHint'),
  },
])
</script>
