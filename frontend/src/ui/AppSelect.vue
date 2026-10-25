<template>
  <div ref="rootRef" class="app-select" :class="{ open, disabled }">
    <button
      type="button"
      class="app-select-trigger"
      :disabled="disabled"
      aria-haspopup="listbox"
      :aria-expanded="open"
      @click="toggle"
      @keydown.down.prevent="openMenu"
      @keydown.up.prevent="openMenu"
      @keydown.enter.prevent="open ? selectActive() : openMenu()"
      @keydown.space.prevent="open ? selectActive() : openMenu()"
      @keydown.esc.prevent="open = false"
    >
      <span class="app-select-value" :class="{ placeholder: !hasValue }">{{ labelText }}</span>
      <AppIcon name="chevron-down" :size="13" class="app-select-caret" />
    </button>
    <transition name="app-select-drop">
      <ul v-if="open" class="app-select-menu" role="listbox">
        <li
          v-for="(option, index) in normalizedOptions"
          :key="option.value"
          class="app-select-option"
          :class="{ selected: option.value === modelValue, active: index === activeIndex }"
          role="option"
          :aria-selected="option.value === modelValue"
          @mouseenter="activeIndex = index"
          @click="pick(option.value)"
        >
          {{ option.label }}
        </li>
        <li v-if="normalizedOptions.length === 0" class="app-select-empty">暂无可用记录</li>
      </ul>
    </transition>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, default: () => [] },   // 字符串数组或 {label, value}
  placeholder: { type: String, default: '请选择' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'change'])

const rootRef = ref(null)
const open = ref(false)
const activeIndex = ref(-1)

const normalizedOptions = computed(() =>
  props.options.map((item) =>
    typeof item === 'object' && item !== null ? item : { label: String(item), value: item }
  )
)
const hasValue = computed(() => props.modelValue !== '' && props.modelValue !== null && props.modelValue !== undefined)
const labelText = computed(() => {
  const hit = normalizedOptions.value.find((option) => option.value === props.modelValue)
  return hit ? hit.label : props.placeholder
})

const openMenu = () => {
  if (props.disabled) return
  if (normalizedOptions.value.length === 0) {
    open.value = true
    activeIndex.value = -1
    return
  }
  const selected = normalizedOptions.value.findIndex((option) => option.value === props.modelValue)
  activeIndex.value = selected >= 0 ? selected : 0
  open.value = true
}

const toggle = () => {
  if (open.value) {
    open.value = false
    return
  }
  openMenu()
}

const pick = (value) => {
  open.value = false
  if (value === props.modelValue) return
  emit('update:modelValue', value)
  emit('change', value)
}

const selectActive = () => {
  const option = normalizedOptions.value[activeIndex.value]
  if (option) pick(option.value)
}

const onArrow = (delta) => {
  if (!open.value) {
    openMenu()
    return
  }
  const length = normalizedOptions.value.length
  if (!length) return
  activeIndex.value = (activeIndex.value + delta + length) % length
}
const onOutside = (event) => {
  if (open.value && rootRef.value && !rootRef.value.contains(event.target)) open.value = false
}
onMounted(() => document.addEventListener('mousedown', onOutside))
onBeforeUnmount(() => document.removeEventListener('mousedown', onOutside))
</script>

<style scoped>
.app-select { position: relative; width: 230px; }
.app-select.disabled { opacity: 0.45; pointer-events: none; }

.app-select-trigger {
  width: 100%;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 9px;
  padding: 0 10px 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--bg-input);
  color: var(--text-1);
  font-family: var(--font-ui);
  font-size: 11.5px;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}
.app-select-trigger:hover { border-color: var(--border-strong); background: #1a1f22; }
.app-select.open .app-select-trigger { border-color: var(--signal); box-shadow: 0 0 0 2px var(--signal-soft); }
.app-select-trigger:focus-visible { outline: none; box-shadow: 0 0 0 2px var(--signal); }

.app-select-value { min-width: 0; overflow: hidden; color: #ece9e0; white-space: nowrap; text-overflow: ellipsis; }
.app-select-value.placeholder { color: #737a7f; }
.app-select-caret { flex: none; color: #7d858a; transition: transform 0.16s ease, color 0.16s ease; }
.app-select.open .app-select-caret { color: var(--signal-hi); transform: rotate(180deg); }

.app-select-menu {
  position: absolute;
  top: calc(100% + 5px);
  left: 0;
  right: 0;
  z-index: 1200;
  max-height: 280px;
  margin: 0;
  padding: 4px;
  overflow-y: auto;
  list-style: none;
  background: var(--bg-panel);
  border: 1px solid var(--border-strong);
  border-top: 2px solid var(--signal);
  box-shadow: var(--shadow-dialog);
}
.app-select-option {
  padding: 9px 10px;
  color: var(--text-2);
  font-size: 11.5px;
  cursor: pointer;
}
.app-select-option:hover,
.app-select-option.active { background: var(--bg-hover); color: var(--text-1); }
.app-select-option.selected { color: var(--signal-hi); }
.app-select-option.selected::after { content: "●"; float: right; font-size: 6px; line-height: 16px; }
.app-select-empty { padding: 12px 10px; color: var(--text-3); font-size: 10.5px; text-align: center; }

.app-select-drop-enter-active,
.app-select-drop-leave-active { transition: opacity 0.13s ease, transform 0.13s ease; }
.app-select-drop-enter-from,
.app-select-drop-leave-to { opacity: 0; transform: translateY(-4px); }
</style>