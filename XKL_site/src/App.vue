<script setup>
import { onMounted, ref } from 'vue'

import DownloadSection from '@/components/DownloadSection.vue'
import FeatureGrid from '@/components/FeatureGrid.vue'
import GuideSection from '@/components/GuideSection.vue'
import HeroSection from '@/components/HeroSection.vue'
import PlatformStrip from '@/components/PlatformStrip.vue'
import SiteFooter from '@/components/SiteFooter.vue'
import SiteHeader from '@/components/SiteHeader.vue'
import StartSection from '@/components/StartSection.vue'
import { loadReleases, useReleases } from '@/composables/useReleases'

const THEME_KEY = 'xkl-theme'

const releases = useReleases()
const theme = ref('dark')
const highlight = ref('')
let highlightTimer = 0

function applyTheme(value) {
  theme.value = value
  document.documentElement.setAttribute('data-theme', value)
  try {
    localStorage.setItem(THEME_KEY, value)
  } catch (error) {
    // 隐私模式下写不了 localStorage，忽略即可
  }
}

function toggleTheme() {
  applyTheme(theme.value === 'dark' ? 'light' : 'dark')
}

function focusPlatform(id) {
  highlight.value = id
  window.clearTimeout(highlightTimer)
  highlightTimer = window.setTimeout(() => {
    highlight.value = ''
  }, 2400)
}

onMounted(() => {
  let saved = 'dark'
  try {
    saved = localStorage.getItem(THEME_KEY) || 'dark'
  } catch (error) {
    saved = 'dark'
  }
  applyTheme(saved === 'light' ? 'light' : 'dark')
  loadReleases()
})
</script>

<template>
  <a class="skip-link" href="#main">跳到主要内容</a>
  <SiteHeader :theme="theme" @toggle-theme="toggleTheme" />
  <main id="main">
    <HeroSection />
    <PlatformStrip @select="focusPlatform" />
    <DownloadSection :releases="releases" :highlight="highlight" />
    <FeatureGrid />
    <GuideSection />
    <StartSection />
  </main>
  <SiteFooter />
</template>
