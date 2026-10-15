<script setup>
import { Monitor, Smartphone } from '@lucide/vue'

import { platforms } from '@/data/releases'

const emit = defineEmits(['select'])

const iconMap = {
  monitor: Monitor,
  smartphone: Smartphone,
}

function pick(id) {
  emit('select', id)
}
</script>

<template>
  <div class="strip">
    <div class="shell strip-inner">
      <span class="strip-label">在你喜欢的设备上</span>
      <div class="strip-links">
        <a
          v-for="item in platforms"
          :key="item.id"
          class="strip-link"
          :href="`#dl-${item.id}`"
          @click="pick(item.id)"
        >
          <component :is="iconMap[item.icon]" :size="18" :stroke-width="2" />
          <span>{{ item.label }}</span>
          <span class="strip-system">{{ item.system }}</span>
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.strip {
  border-top: 1px solid var(--stroke);
  border-bottom: 1px solid var(--stroke);
  background: var(--bg-soft);
}

.strip-inner {
  display: flex;
  align-items: center;
  gap: 24px;
  min-height: 72px;
  padding-top: 12px;
  padding-bottom: 12px;
}

.strip-label {
  color: var(--text-faint);
  font-size: 13px;
  white-space: nowrap;
}

.strip-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.strip-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 16px;
  border: 1px solid var(--stroke);
  border-radius: var(--r-pill);
  background: var(--surface);
  font-size: 14px;
  font-weight: 600;
  transition: border-color 0.2s var(--ease), background-color 0.2s var(--ease);
}

.strip-link:hover {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.strip-system {
  color: var(--text-faint);
  font-size: 12px;
  font-weight: 500;
}

@media (max-width: 900px) {
  .strip-inner {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
    padding-top: 16px;
    padding-bottom: 16px;
  }
}

@media (max-width: 520px) {
  .strip-links {
    width: 100%;
  }

  .strip-link {
    flex: 1;
    justify-content: center;
  }

  .strip-system {
    display: none;
  }
}

@media (pointer: coarse) {
  .strip-link {
    min-height: 44px;
  }
}
</style>
