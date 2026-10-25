<template>
  <button
    type="button"
    class="app-btn"
    :class="[variant, size, { 'is-loading': loading, 'is-disabled': disabled || loading }]"
    :disabled="disabled || loading"
    :aria-busy="loading || undefined"
  >
    <span v-if="loading" class="app-spinner" />
    <slot />
  </button>
</template>

<script setup>
defineProps({
  variant: { type: String, default: 'quiet' }, // primary | quiet | ghost | danger
  size: { type: String, default: 'md' },       // md | sm
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})
</script>

<style scoped>
.app-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  font-family: var(--font-ui);
  font-size: 12px;
  font-weight: 650;
  line-height: 1;
  letter-spacing: 0.35px;
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
  clip-path: polygon(0 0, calc(100% - 7px) 0, 100% 7px, 100% 100%, 7px 100%, 0 calc(100% - 7px));
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease, transform 0.08s ease, box-shadow 0.15s ease;
}
.app-btn:active:not(.is-disabled) { transform: translateY(1px); }
.app-btn.is-disabled { cursor: not-allowed; opacity: 0.45; }
.app-btn:focus-visible { box-shadow: 0 0 0 2px var(--ink-950), 0 0 0 4px var(--signal); outline: none; }
.app-btn .app-spinner { width: 12px; height: 12px; }

.app-btn.md { height: 38px; padding: 0 15px; }
.app-btn.sm { height: 30px; padding: 0 11px; font-size: 11px; }

.app-btn.primary {
  background: var(--signal);
  border-color: var(--signal);
  color: #fff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.2);
}
.app-btn.primary:hover:not(.is-disabled) { background: var(--signal-hi); border-color: var(--signal-hi); }
.app-btn.primary:focus-visible { box-shadow: 0 0 0 2px var(--ink-950), 0 0 0 4px var(--signal-hi); }

.app-btn.quiet {
  background: var(--button-quiet-bg);
  border-color: var(--button-quiet-border);
  color: #f1eee5;
}
.app-btn.quiet:hover:not(.is-disabled) { background: #30363b; border-color: #4a5258; }

.app-btn.ghost {
  background: transparent;
  border-color: transparent;
  color: var(--text-2);
}
.app-btn.ghost:hover:not(.is-disabled) { background: var(--bg-hover); color: var(--text-1); }
.app-btn.ghost.active { color: var(--signal); background: var(--signal-soft); }

.app-btn.danger {
  background: rgba(217, 81, 67, 0.1);
  border-color: rgba(217, 81, 67, 0.4);
  color: #e77b6f;
}
.app-btn.danger:hover:not(.is-disabled) { background: rgba(217, 81, 67, 0.18); border-color: rgba(217, 81, 67, 0.62); }
</style>