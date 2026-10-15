<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

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
  }, 3000)
}

/**
 * 页内锚点统一自己接管滚动。
 * 浏览器原生行为有个坑：hash 已经是同一个值时再点不会滚动
 * （「下载工具」和平台条「手机版」都指向 #download），
 * 而且平台条需要落到具体那张卡片，而不是区块顶部。
 */
function onPageClick(event) {
  if (event.defaultPrevented || event.button !== 0) return
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
  const link = event.target instanceof Element ? event.target.closest('a[href^="#"]') : null
  if (!link) return
  const hash = link.getAttribute('href') || ''
  if (hash.length < 2) return
  const target = document.getElementById(decodeURIComponent(hash.slice(1)))
  if (!target) return

  event.preventDefault()
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  target.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
  window.history.replaceState(null, '', hash)
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
  document.addEventListener('click', onPageClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onPageClick)
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
