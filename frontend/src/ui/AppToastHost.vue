<template>
  <teleport to="body">
    <transition-group name="app-toast" tag="div" class="app-toast-host" aria-live="polite">
      <div v-for="item in state.items" :key="item.id" class="app-toast" :class="item.type">
        <span v-if="item.type === 'loading'" class="app-spinner" />
        <span v-else class="app-toast-sign" :class="item.type" />
        <span class="app-toast-text">{{ item.message }}</span>
      </div>
    </transition-group>
  </teleport>
</template>

<script setup>
import { useToastState } from './toast'

const state = useToastState()
</script>

<style scoped>
.app-toast-host {
  position: fixed;
  top: 84px;
  right: 22px;
  z-index: 3000;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  pointer-events: none;
}
.app-toast {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  max-width: 520px;
  padding: 11px 14px 11px 16px;
  overflow: hidden;
  color: var(--text-1);
  background: var(--bg-panel);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-control);
  box-shadow: var(--shadow-dialog);
  font-size: 11.5px;
  line-height: 1.55;
}
.app-toast::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--ink-500);
}
.app-toast.success::before { background: var(--ok); }
.app-toast.error::before { background: var(--bad); }
.app-toast.warning::before { background: var(--signal); }
.app-toast.loading::before { background: var(--cyan); }
.app-toast-sign {
  width: 6px;
  height: 6px;
  margin-top: 5px;
  flex: none;
  border-radius: 50%;
}
.app-toast-sign.success { background: var(--ok); box-shadow: 0 0 7px rgba(89, 183, 122, 0.55); }
.app-toast-sign.error { background: var(--bad); box-shadow: 0 0 7px rgba(217, 81, 67, 0.55); }
.app-toast-sign.warning { background: var(--signal); box-shadow: 0 0 7px var(--signal-glow); }
.app-toast-sign.info { background: var(--text-3); }
.app-toast-text { word-break: break-word; }
.app-toast-enter-active,
.app-toast-leave-active { transition: opacity 0.18s ease, transform 0.18s ease; }
.app-toast-enter-from,
.app-toast-leave-to { opacity: 0; transform: translateX(9px); }
</style>