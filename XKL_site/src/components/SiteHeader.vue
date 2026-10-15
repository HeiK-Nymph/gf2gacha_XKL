<script setup>
import { computed, markRaw, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  ArrowUpRight,
  BookOpen,
  Compass,
  Download,
  Moon,
  SlidersHorizontal,
  Sun,
} from '@lucide/vue'

import { REPO_URL } from '@/data/releases'
import GithubMark from '@/components/GithubMark.vue'
import { assetUrl } from '@/utils/asset'

const props = defineProps({
  theme: { type: String, default: 'dark' },
})

const emit = defineEmits(['toggle-theme'])

const navItems = [
  { id: 'home', label: '首页', icon: markRaw(Compass) },
  { id: 'download', label: '下载', icon: markRaw(Download) },
  { id: 'features', label: '功能', icon: markRaw(SlidersHorizontal) },
  { id: 'guide', label: '教程', icon: markRaw(BookOpen) },
]

const activeId = ref('home')
const scrolled = ref(false)

const isDark = computed(() => props.theme === 'dark')

function onScroll() {
  scrolled.value = window.scrollY > 8

  const offset = 140
  let current = navItems[0].id
  for (const item of navItems) {
    const element = document.getElementById(item.id)
    if (element && element.getBoundingClientRect().top <= offset) {
      current = item.id
    }
  }
  activeId.value = current
}

onMounted(() => {
  onScroll()
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('resize', onScroll)
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
  window.removeEventListener('resize', onScroll)
})
</script>

<template>
  <header class="header" :class="{ 'is-scrolled': scrolled }">
    <div class="header-inner shell">
      <a class="brand" href="#home" aria-label="回到首页">
        <img class="brand-mark" :src="assetUrl('favicon.png')" alt="" width="32" height="32" />
        <span class="brand-text">夏克里助手<span class="brand-dot">.</span></span>
      </a>

      <nav class="nav" aria-label="主导航">
        <a
          v-for="item in navItems"
          :key="item.id"
          class="nav-link nav-link--desktop"
          :class="{ 'is-active': activeId === item.id }"
          :href="`#${item.id}`"
          :aria-current="activeId === item.id ? 'true' : undefined"
        >
          <span class="nav-icon"><component :is="item.icon" :size="19" :stroke-width="2" /></span>
          <span>{{ item.label }}</span>
        </a>
      </nav>

      <div class="header-actions">
        <button
          class="icon-btn"
          type="button"
          :title="isDark ? '切换到浅色外观' : '切换到深色外观'"
          :aria-label="isDark ? '切换到浅色外观' : '切换到深色外观'"
          @click="emit('toggle-theme')"
        >
          <component :is="isDark ? Sun : Moon" :size="19" :stroke-width="2" />
        </button>
        <a class="source-link" :href="REPO_URL" target="_blank" rel="noopener noreferrer">
          <GithubMark :size="19" />
          <span class="source-text">GitHub</span>
          <ArrowUpRight class="source-arrow" :size="15" :stroke-width="2" />
        </a>
      </div>
    </div>
  </header>

  <!-- 移动端底部导航独立于 header：header 有 backdrop-filter，会让 fixed 子元素改锚点 -->
  <nav class="mobile-nav" aria-label="主导航（移动端）">
    <a
      v-for="item in navItems"
      :key="item.id"
      class="mobile-link"
      :class="{ 'is-active': activeId === item.id }"
      :href="`#${item.id}`"
    >
      <span class="mobile-icon"><component :is="item.icon" :size="20" :stroke-width="2" /></span>
      <span>{{ item.label }}</span>
    </a>
  </nav>
</template>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid transparent;
  transition: border-color 0.2s var(--ease);
}

.header.is-scrolled {
  border-bottom-color: var(--stroke);
}

.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  height: var(--header-h);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.brand-mark {
  width: 32px;
  height: 32px;
  border-radius: var(--r-md);
  border: 1px solid var(--stroke);
  object-fit: cover;
  flex-shrink: 0;
}

.brand-text {
  font-size: 19px;
  font-weight: 800;
  letter-spacing: -0.01em;
  white-space: nowrap;
}

.brand-dot {
  color: var(--accent);
}

.nav {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px;
  border-radius: var(--r-pill);
  background: var(--surface-2);
}

.nav-link {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 42px;
  padding: 0 18px;
  border-radius: var(--r-pill);
  color: var(--text-dim);
  font-size: 14px;
  font-weight: 600;
  transition: background-color 0.2s var(--ease), color 0.2s var(--ease);
}

.nav-link:hover {
  background: var(--surface-3);
  color: var(--text);
}

.nav-link.is-active {
  background: var(--accent);
  color: var(--accent-ink);
}

.nav-icon {
  display: flex;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mobile-nav {
  display: none;
}

.source-link {
  display: flex;
  align-items: center;
  gap: 7px;
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid var(--stroke);
  border-radius: var(--r-pill);
  background: var(--surface-2);
  font-size: 13px;
  font-weight: 600;
  transition: border-color 0.2s var(--ease), background-color 0.2s var(--ease);
}

.source-link:hover {
  border-color: var(--stroke-strong);
  background: var(--surface-3);
}

.source-arrow {
  color: var(--text-faint);
}

@media (max-width: 1000px) {
  .brand-text {
    font-size: 17px;
  }

  .nav-link {
    padding: 0 13px;
  }

  .source-text,
  .source-arrow {
    display: none;
  }

  .source-link {
    width: 40px;
    justify-content: center;
    padding: 0;
  }
}

@media (max-width: 760px) {
  .brand {
    gap: 8px;
  }

  .brand-text {
    font-size: 16px;
  }

  .nav {
    display: none;
  }

  .mobile-nav {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 120;
    display: flex;
    justify-content: space-around;
    gap: 2px;
    padding: 8px 10px calc(8px + env(safe-area-inset-bottom));
    border-radius: var(--r-md) var(--r-md) 0 0;
    border-top: 1px solid var(--stroke);
    background: var(--surface);
    box-shadow: 0 -6px 24px rgba(0, 0, 0, 0.24);
  }

  .mobile-link {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    min-height: 54px;
    padding: 0;
    border-radius: var(--r-md);
    color: var(--text-dim);
    font-size: 11px;
    font-weight: 600;
  }

  .mobile-link.is-active {
    color: var(--accent);
  }

  .mobile-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 28px;
    width: 52px;
    border-radius: var(--r-pill);
  }

  .mobile-link.is-active .mobile-icon {
    background: var(--accent-soft);
  }
}
</style>
