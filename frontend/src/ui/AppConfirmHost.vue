<template>
  <AppDialog
    :model-value="state.visible"
    :title="state.title"
    width="440px"
    :close-on-click-outside="false"
    @update:model-value="settleConfirm(false)"
  >
    <p class="app-confirm-message">{{ state.message }}</p>
    <template #footer>
      <AppButton variant="quiet" @click="settleConfirm(false)">{{ state.cancelText }}</AppButton>
      <AppButton :variant="state.danger ? 'danger' : 'primary'" @click="settleConfirm(true)">
        {{ state.confirmText }}
      </AppButton>
    </template>
  </AppDialog>
</template>

<script setup>
import AppButton from './AppButton.vue'
import AppDialog from './AppDialog.vue'
import { settleConfirm, useConfirmState } from './confirm'

const state = useConfirmState()
</script>

<style scoped>
.app-confirm-message {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
