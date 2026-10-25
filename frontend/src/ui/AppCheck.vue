<template>
  <div
    class="app-check"
    :class="{ checked: modelValue, disabled }"
    role="checkbox"
    :aria-checked="modelValue"
    :tabindex="disabled ? -1 : 0"
    @click="toggle"
    @keydown.enter.prevent="toggle"
    @keydown.space.prevent="toggle"
  >
    <span class="app-check-box">
      <svg v-if="modelValue" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
    </span>
    <span class="app-check-label"><slot /></span>
  </div>
</template>

<script setup>
const props = defineProps({
  modelValue: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'change'])

const toggle = () => {
  if (props.disabled) return
  emit('update:modelValue', !props.modelValue)
  emit('change', !props.modelValue)
}
</script>

<style scoped>
.app-check {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  color: var(--text-1);
  font-size: 12px;
  cursor: pointer;
  user-select: none;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.app-check:hover { border-color: var(--border-strong) !important; }
.app-check:focus-visible { outline: 2px solid var(--signal); outline-offset: 2px; }
.app-check.disabled { opacity: 0.42; cursor: not-allowed; }
.app-check-box {
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  border: 1px solid var(--border-strong);
  border-radius: 1px;
  background: var(--bg-input);
  color: #fff;
  transition: background 0.14s ease, border-color 0.14s ease, box-shadow 0.14s ease;
}
.app-check-box svg { width: 10px; height: 10px; }
.app-check.checked .app-check-box { background: var(--signal); border-color: var(--signal); box-shadow: 0 0 0 3px var(--signal-soft); }
.app-check.disabled .app-check-box { color: rgba(255, 255, 255, 0.65); }
</style>