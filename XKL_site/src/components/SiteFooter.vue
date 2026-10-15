<script setup>
import { ArrowUpRight } from '@lucide/vue'

import { REPO_URL } from '@/data/releases'
import GithubMark from '@/components/GithubMark.vue'

const footerLinks = [
  { label: '首页', href: '#home' },
  { label: '下载', href: '#download' },
  { label: '功能', href: '#features' },
  { label: '教程', href: '#guide' },
]

const year = new Date().getFullYear()
</script>

<template>
  <footer class="footer">
    <div class="shell">
      <div class="footer-top">
        <div class="footer-brand">
          <a class="footer-name" href="#home">夏克里助手<span>.</span></a>
          <p>记录每次招募，留住每一份运气。</p>
        </div>
        <nav class="footer-nav" aria-label="页脚导航">
          <a v-for="link in footerLinks" :key="link.href" :href="link.href">{{ link.label }}</a>
        </nav>
        <a class="footer-repo" :href="REPO_URL" target="_blank" rel="noopener noreferrer">
          <GithubMark :size="18" />
          在 GitHub 查看
          <ArrowUpRight :size="15" :stroke-width="2" />
        </a>
      </div>
      <div class="footer-bottom">
        <span>记录与令牌只保存在你自己的设备上</span>
        <span>© {{ year }} 夏克里助手 · gf2gacha_XKL</span>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.footer {
  margin-top: 24px;
  border-top: 1px solid var(--stroke);
  background: var(--bg-soft);
}

.footer-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 32px;
  padding: 48px 0 24px;
}

.footer-name {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.01em;
}

.footer-name span {
  color: var(--accent);
}

.footer-brand p {
  margin-top: 8px;
  color: var(--text-faint);
  font-size: 13px;
}

.footer-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
}

.footer-nav a {
  display: inline-flex;
  align-items: center;
  min-height: 40px;
  color: var(--text-dim);
  font-size: 14px;
}

.footer-nav a:hover {
  color: var(--accent);
}

.footer-repo {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 16px;
  border: 1px solid var(--stroke);
  border-radius: var(--r-pill);
  background: var(--surface);
  font-size: 13px;
  font-weight: 600;
  transition: border-color 0.2s var(--ease);
}

.footer-repo:hover {
  border-color: var(--accent);
}

.footer-repo svg:last-child {
  color: var(--text-faint);
}

.footer-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 0 24px;
  border-top: 1px solid var(--stroke);
  color: var(--text-faint);
  font-size: 12px;
}

@media (max-width: 900px) {
  .footer-top {
    flex-direction: column;
    gap: 20px;
    padding-top: 36px;
  }
}

@media (max-width: 700px) {
  .footer-bottom {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
    padding-bottom: 16px;
  }
}
</style>
