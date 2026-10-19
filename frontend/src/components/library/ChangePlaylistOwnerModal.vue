<template>
  <UiModal
    :open="open"
    :title="t('playlists.changeOwnerTitle')"
    :description="t('playlists.changeOwnerHint')"
    @close="close"
  >
    <div class="flex flex-col gap-4">
      <div v-if="loadingUsers" class="py-4 text-center text-sm text-muted">
        {{ t('common.loading') }}
      </div>
      <div v-else class="flex flex-col gap-2">
        <label class="text-xs font-semibold uppercase tracking-wider text-muted">
          {{ t('playlists.newOwner') }}
        </label>
        <UiSelect
          v-model="selectedUserId"
          :options="userOptions"
          :label="t('playlists.newOwner')"
          icon="user"
          block
        />
      </div>
    </div>
    <template #footer>
      <UiButton variant="ghost" @click="close">
        {{ t('common.cancel') }}
      </UiButton>
      <UiButton
        variant="primary"
        icon="user"
        :disabled="!canSave"
        :loading="saving"
        @click="submit"
      >
        {{ t('playlists.changeOwnerSubmit') }}
      </UiButton>
    </template>
  </UiModal>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import API from '/src/model/api'
import UiButton from '../ui/UiButton.vue'
import UiModal from '../ui/UiModal.vue'
import UiSelect from '../ui/UiSelect.vue'
import { usePlaylistActions } from '/src/model/playlistActions'
import { useI18n } from '/src/i18n'

const { t } = useI18n()
const actions = usePlaylistActions()

const open = actions.changeOwnerOpen
const playlist = computed(() => actions.changeOwnerPlaylist.value)

const users = ref([])
const loadingUsers = ref(false)
const selectedUserId = ref(null)
const saving = ref(false)

const userOptions = computed(() => {
  return users.value.map((u) => ({
    label: `${u.username}${u.role === 'admin' ? ' (Admin)' : ''}`,
    value: u.id,
  }))
})

const canSave = computed(() => {
  if (saving.value || loadingUsers.value) return false
  if (selectedUserId.value === null || selectedUserId.value === undefined) return false
  const currentOwnerId = playlist.value?.owner_id
  return selectedUserId.value !== currentOwnerId
})

watch(open, async (val) => {
  if (val) {
    selectedUserId.value = playlist.value?.owner_id ?? 0
    loadingUsers.value = true
    try {
      const res = await API.listUsers()
      users.value = res.data || []
      if (selectedUserId.value === 0 && users.value.length > 0) {
        const adminUser = users.value.find((u) => u.role === 'admin')
        if (adminUser) {
          selectedUserId.value = adminUser.id
        }
      }
    } catch {
      users.value = []
    } finally {
      loadingUsers.value = false
    }
  }
})

function close() {
  open.value = false
}

async function submit() {
  const current = playlist.value
  if (!current || selectedUserId.value === null || saving.value) return
  saving.value = true
  try {
    await actions.changeOwner(current, selectedUserId.value)
    close()
  } catch {
    /* toast in changeOwner */
  } finally {
    saving.value = false
  }
}
</script>
