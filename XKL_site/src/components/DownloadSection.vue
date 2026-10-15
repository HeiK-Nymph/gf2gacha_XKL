<script setup>
import { computed, ref } from 'vue'
import { ArrowUpRight, Check, Copy, Download, Link, Monitor, RefreshCw, Smartphone } from '@lucide/vue'

import { RELEASES_URL, formatSize, shortHash } from '@/data/releases'
import { copyText } from '@/utils/clipboard'

const props = defineProps({
  releases: { type: Array, required: true },
  highlight: { type: String, default: '' },
})

const iconMap = {
  monitor: Monitor,
  smartphone: Smartphone,
}

const copiedKey = ref('')
let resetTimer = 0

const liveCount = computed(() => props.releases.filter((item) => item.live).length)

async function copy(value, key) {
  const ok = await copyText(value)
  if (!ok) return
  copiedKey.value = key
  window.clearTimeout(resetTimer)
  resetTimer = window.setTimeout(() => {
    copiedKey.value = ''
  }, 1800)
}
</script>

<template>
  <section id="download" class="section download">
    <div class="shell">
      <div class="section-head">
        <div>
          <span class="eyebrow">GET THE TOOL</span>
          <h2 class="section-title">
            选一个版本，<br />
            装上就能用。
          </h2>
        </div>
        <p class="lead section-lead">
          两个客户端任选：电脑版走代理抓包，手机版只要一部安卓机。<br />
          记录格式一致，导出的文件可以互相导入。
        </p>
      </div>

      <div class="download-grid">
        <article
          v-for="item in releases"
          :key="item.id"
          :id="`dl-${item.id}`"
          class="dl-card"
          :class="[`dl-card--${item.accent}`, { 'is-highlight': highlight === item.id }]"
        >
          <header class="dl-head">
            <span class="dl-icon"><component :is="iconMap[item.icon]" :size="22" :stroke-width="2" /></span>
            <div class="dl-title">
              <h3>{{ item.label }}</h3>
              <span class="dl-system">{{ item.system }}</span>
            </div>
            <span class="dl-version">v{{ item.version }}</span>
          </header>

          <p class="dl-summary">{{ item.summary }}</p>

          <dl class="dl-specs">
            <div class="spec-row">
              <dt>文件名</dt>
              <dd class="mono">{{ item.fileName }}</dd>
            </div>
            <div class="spec-row">
              <dt>大小</dt>
              <dd>{{ formatSize(item.size) }}</dd>
            </div>
            <div class="spec-row">
              <dt>sha256</dt>
              <dd>
                <button
                  class="copy-inline"
                  type="button"
                  title="复制完整校验值"
                  @click="copy(item.sha256, `hash-${item.id}`)"
                >
                  <span class="mono">{{ shortHash(item.sha256) }}</span>
                  <component :is="copiedKey === `hash-${item.id}` ? Check : Copy" :size="14" :stroke-width="2" />
                </button>
              </dd>
            </div>
          </dl>

          <div class="dl-actions">
            <a class="btn btn--primary dl-btn" :href="item.downloadUrl" download>
              <Download :size="18" :stroke-width="2.2" />
              下载{{ item.label }}
            </a>
            <button
              class="icon-btn"
              type="button"
              :title="`复制${item.label}R2 直链`"
              :aria-label="`复制${item.label} R2 直链`"
              @click="copy(item.downloadUrl, `url-${item.id}`)"
            >
              <component :is="copiedKey === `url-${item.id}` ? Check : Link" :size="18" :stroke-width="2" />
            </button>
          </div>

          <ul class="dl-req">
            <li v-for="req in item.requirements" :key="req">
              <Check :size="15" :stroke-width="2.4" />
              <span>{{ req }}</span>
            </li>
          </ul>
        </article>
      </div>

      <div class="dl-foot">
        <span class="dl-live">
          <RefreshCw :size="15" :stroke-width="2" />
          {{ liveCount ? '版本信息已从 R2 读取' : '版本信息来自最近一次发布' }}
        </span>
        <a class="dl-more" :href="RELEASES_URL" target="_blank" rel="noopener noreferrer">
          历史版本与更新记录
          <ArrowUpRight :size="16" :stroke-width="2" />
        </a>
      </div>
    </div>
  </section>
</template>

<style scoped>
.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 40px;
  margin-bottom: 40px;
}

.section-title {
  margin-top: 14px;
  font-size: clamp(26px, 3.2vw, 38px);
  line-height: 1.2;
  font-weight: 800;
  letter-spacing: -0.01em;
}

.section-lead {
  max-width: 42ch;
  text-align: right;
}

.download-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  align-items: start;
}

.dl-card {
  /* 平台条直接落到卡片时，别被吸顶头部挡住 */
  scroll-margin-top: calc(var(--header-h) + 16px);
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 24px;
  border: 1px solid var(--stroke);
  border-radius: var(--r-md);
  background: var(--surface);
  box-shadow: var(--shadow-soft);
  transition: border-color 0.25s var(--ease), box-shadow 0.25s var(--ease);
}

.dl-card--gold {
  --card-accent: var(--accent);
  --card-accent-soft: var(--accent-soft);
}

.dl-card--green {
  --card-accent: var(--green);
  --card-accent-soft: var(--green-soft);
}

.dl-card.is-highlight {
  border-color: var(--card-accent);
  box-shadow: 0 0 0 3px var(--card-accent-soft), var(--shadow);
}

.dl-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dl-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  flex-shrink: 0;
  border-radius: var(--r-sm);
  background: var(--card-accent-soft);
  color: var(--card-accent);
}

.dl-title {
  flex: 1;
  min-width: 0;
}

.dl-title h3 {
  font-size: 19px;
  font-weight: 700;
  line-height: 1.3;
}

.dl-system {
  color: var(--text-faint);
  font-size: 13px;
}

.dl-version {
  padding: 4px 10px;
  border: 1px solid var(--stroke);
  border-radius: var(--r-pill);
  background: var(--surface-2);
  color: var(--text-dim);
  font-size: 12.5px;
  font-weight: 700;
  white-space: nowrap;
}

.dl-summary {
  color: var(--text-dim);
  font-size: 14.5px;
}

.dl-specs {
  margin: 0;
  padding: 14px 0;
  border-top: 1px solid var(--stroke);
  border-bottom: 1px solid var(--stroke);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.spec-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-width: 0;
}

.spec-row dt {
  color: var(--text-faint);
  font-size: 13px;
  flex-shrink: 0;
}

.spec-row dd {
  margin: 0;
  min-width: 0;
  color: var(--text);
  font-size: 13.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.copy-inline {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 3px 8px;
  border: 1px solid transparent;
  border-radius: var(--r-xs);
  background: var(--surface-2);
  color: var(--text-dim);
  cursor: pointer;
  transition: color 0.2s var(--ease), border-color 0.2s var(--ease);
}

.copy-inline:hover {
  color: var(--text);
  border-color: var(--stroke-strong);
}

.dl-actions {
  display: flex;
  gap: 10px;
}

.dl-btn {
  flex: 1;
  background: var(--card-accent);
  color: var(--accent-ink);
}

.dl-card--green .dl-btn {
  color: #06210f;
}

[data-theme='light'] .dl-card--green .dl-btn {
  color: #ffffff;
}

.dl-btn:hover {
  filter: brightness(1.08);
  background: var(--card-accent);
}

.dl-actions .icon-btn {
  flex-shrink: 0;
  width: 46px;
  height: 46px;
}

.dl-req {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dl-req li {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  color: var(--text-dim);
  font-size: 13.5px;
}

.dl-req svg {
  flex-shrink: 0;
  margin-top: 3px;
  color: var(--card-accent);
}

.dl-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid var(--stroke);
  color: var(--text-faint);
  font-size: 13px;
}

.dl-live {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.dl-more {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 36px;
  color: var(--text-dim);
  font-weight: 600;
}

.dl-more:hover {
  color: var(--accent);
}

@media (max-width: 900px) {
  .section-head {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .section-lead {
    text-align: left;
  }

  .download-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 760px) {
  .dl-card {
    padding: 20px;
  }

  .dl-foot {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
}

@media (pointer: coarse) {
  .dl-btn,
  .dl-actions .icon-btn {
    min-height: 48px;
  }

  .copy-inline {
    padding: 6px 10px;
  }

  /* 视觉上保持小巧，触摸区域撑到 44px 高 */
  .copy-inline::after {
    content: '';
    position: absolute;
    inset: -6px -8px;
  }

  .dl-more {
    min-height: 44px;
  }
}
</style>
