<template>
  <teleport to="body">
    <transition name="app-lightbox-fade">
      <div v-if="modelValue" class="app-lightbox" @click.self="close">
        <button type="button" class="app-lightbox-close" aria-label="关闭" @click="close">
          <AppIcon name="close" :size="18" />
        </button>
        <button
          v-if="images.length > 1"
          type="button"
          class="app-lightbox-nav"
          aria-label="上一张"
          @click.stop="step(-1)"
        >
          <AppIcon name="chevron-left" :size="22" />
        </button>
        <img class="app-lightbox-image" :src="current" alt="" @click.self="close" />
        <button
          v-if="images.length > 1"
          type="button"
          class="app-lightbox-nav"
          aria-label="下一张"
          @click.stop="step(1)"
        >
          <AppIcon name="chevron-right" :size="22" />
        </button>
        <div v-if="images.length > 1" class="app-lightbox-counter">{{ index + 1 }} / {{ images.length }}</div>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, watch } from 'vue'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  images: { type: Array, default: () => [] },
  index: { type: Number, default: 0 },
})
const emit = defineEmits(['update:modelValue', 'update:index'])

const current = computed(() => props.images[props.index] || '')
const close = () => emit('update:modelValue', false)
const step = (delta) => {
  const total = props.images.length
  if (!total) return
  emit('update:index', (props.index + delta + total) % total)
}

const onKeydown = (event) => {
  if (!props.modelValue) return
  if (event.key === 'Escape') close()
  if (event.key === 'ArrowLeft') step(-1)
  if (event.key === 'ArrowRight') step(1)
}
watch(() => props.modelValue, (visible) => {
  if (visible) document.addEventListener('keydown', onKeydown)
  else document.removeEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.app-lightbox {
  position: fixed;
  inset: 0;
  z-index: 2500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 42px;
  background: rgba(6, 8, 10, 0.92);
  backdrop-filter: blur(7px);
  -webkit-backdrop-filter: blur(7px);
}
.app-lightbox-image {
  max-width: calc(100vw - 160px);
  max-height: calc(100vh - 80px);
  object-fit: contain;
  border: 1px solid #42484d;
  box-shadow: 0 26px 90px rgba(0, 0, 0, 0.7);
}
.app-lightbox-close {
  position: absolute;
  top: 18px;
  right: 18px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid #3d4449;
  border-radius: var(--radius-control);
  background: #1d2226;
  color: var(--text-1);
  cursor: pointer;
}
.app-lightbox-close:hover { border-color: var(--signal); color: var(--signal-hi); }
.app-lightbox-nav {
  width: 40px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  padding: 0;
  border: 1px solid #3d4449;
  border-radius: var(--radius-control);
  background: #1d2226;
  color: var(--text-1);
  cursor: pointer;
}
.app-lightbox-nav:hover { border-color: var(--signal); color: var(--signal-hi); }
.app-lightbox-counter {
  position: absolute;
  bottom: 20px;
  left: 50%;
  padding: 5px 9px;
  transform: translateX(-50%);
  color: #c3c5c2;
  background: #1d2226;
  border: 1px solid #3d4449;
  font: 9px/1 var(--font-technical);
  letter-spacing: 1px;
}
.app-lightbox-fade-enter-active,
.app-lightbox-fade-leave-active { transition: opacity 0.16s ease; }
.app-lightbox-fade-enter-from,
.app-lightbox-fade-leave-to { opacity: 0; }
</style>