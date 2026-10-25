<template>
  <teleport to="body">
    <transition name="app-dialog-fade">
      <div v-if="modelValue" class="app-dialog-overlay" @mousedown.self="tryOutsideClose">
        <div ref="dialogRef" class="app-dialog" :style="{ width }" role="dialog" aria-modal="true" tabindex="-1">
          <div class="app-dialog-header">
            <slot name="header">
              <h3 class="app-dialog-title">{{ title }}</h3>
            </slot>
            <button v-if="showClose" type="button" class="app-dialog-close" aria-label="关闭" @click="close">
              <AppIcon name="close" :size="16" />
            </button>
          </div>
          <div class="app-dialog-body">
            <slot />
          </div>
          <div v-if="$slots.footer" class="app-dialog-footer">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  width: { type: String, default: '520px' },
  showClose: { type: Boolean, default: true },
  closeOnClickOutside: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue'])
const dialogRef = ref(null)

const close = () => emit('update:modelValue', false)
const tryOutsideClose = () => {
  if (props.closeOnClickOutside) close()
}

const onKeydown = (event) => {
  if (event.key === 'Escape' && props.modelValue && props.closeOnClickOutside) close()
}
watch(() => props.modelValue, async (visible) => {
  if (visible) {
    document.addEventListener('keydown', onKeydown)
    document.body.style.overflow = 'hidden'
    await nextTick()
    dialogRef.value?.focus()
  } else {
    document.removeEventListener('keydown', onKeydown)
    document.body.style.overflow = ''
  }
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.app-dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    repeating-linear-gradient(90deg, transparent 0 47px, rgba(255, 255, 255, 0.018) 47px 48px),
    rgba(7, 9, 11, 0.72);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
.app-dialog {
  position: relative;
  max-width: calc(100vw - 48px);
  max-height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-panel);
  color: var(--text-1);
  border: 1px solid var(--border-strong);
  border-top: 3px solid var(--signal);
  border-radius: var(--radius-panel);
  box-shadow: var(--shadow-dialog);
  outline: none;
}
.app-dialog::before {
  content: "";
  position: absolute;
  top: -3px;
  left: 22px;
  width: 70px;
  height: 3px;
  background: var(--signal-hi);
}
.app-dialog-header { position: relative; flex: none; padding: 17px 20px 0; }
.app-dialog-title {
  margin: 0;
  color: var(--text-1);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.6px;
}
.app-dialog-close {
  position: absolute;
  top: 12px;
  right: 13px;
  width: 29px;
  height: 29px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  background: transparent;
  color: var(--text-3);
  cursor: pointer;
  transition: background 0.14s ease, border-color 0.14s ease, color 0.14s ease;
}
.app-dialog-close:hover { border-color: var(--border); background: var(--bg-hover); color: var(--text-1); }
.app-dialog-close:focus-visible { outline: 2px solid var(--signal); outline-offset: 1px; }
.app-dialog-body {
  padding: 14px 20px 19px;
  overflow-y: auto;
  color: var(--text-1);
  font-size: 12.5px;
  line-height: 1.75;
}
.app-dialog-footer {
  flex: none;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 13px 20px 16px;
  border-top: 1px solid var(--border);
  background: rgba(0, 0, 0, 0.16);
}
.app-dialog-fade-enter-active,
.app-dialog-fade-leave-active { transition: opacity 0.16s ease; }
.app-dialog-fade-enter-active .app-dialog,
.app-dialog-fade-leave-active .app-dialog { transition: transform 0.16s ease; }
.app-dialog-fade-enter-from,
.app-dialog-fade-leave-to { opacity: 0; }
.app-dialog-fade-enter-from .app-dialog,
.app-dialog-fade-leave-to .app-dialog { transform: translateY(9px) scale(0.985); }
</style>