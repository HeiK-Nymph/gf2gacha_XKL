<script setup>
import { ArrowUpRight, Download, PlayCircle, Sparkles } from '@lucide/vue'

import { GUIDE_URL } from '@/data/releases'
import { assetUrl } from '@/utils/asset'
</script>

<template>
  <section id="home" class="section section--hero hero">
    <div class="shell hero-grid">
      <div class="hero-copy">
        <span class="eyebrow"><span class="status-dot"></span>夏克里助手 · 记录只存本机</span>
        <h1 class="display">
          抽卡记录，<br />
          <span class="accent-word">看得明明白白。</span>
        </h1>
        <p class="lead hero-lead">
          从口袋里的手机，到桌面上的电脑。<br class="lead-break" />
          五个池子的抽数、保底与出金，一次算清。
        </p>
        <div class="hero-actions">
          <a class="btn btn--primary btn--lg" href="#download">
            <Download :size="19" :stroke-width="2.2" />
            下载工具
          </a>
          <a class="btn btn--ghost btn--lg" :href="GUIDE_URL" target="_blank" rel="noopener noreferrer">
            <PlayCircle :size="19" :stroke-width="2" />
            看视频教程
          </a>
        </div>
        <div class="hero-meta">
          <span>免费使用</span>
          <span>双端支持</span>
          <span>检查更新</span>
          <span>分享长图</span>
        </div>
      </div>

      <div class="hero-art">
        <div class="art-top">
          <span>HELLO, 指挥官</span>
          <Sparkles :size="17" :stroke-width="2" />
        </div>
        <img
          class="mascot"
          :src="assetUrl('mascot.png')"
          width="512"
          height="512"
          alt="夏克里助手的应用图标：一位绿挑染的 Q 版角色"
          fetchpriority="high"
        />
        <div class="art-bottom">
          <span>
            记录每次相遇，<br />
            <strong>该出金就会出金。</strong>
          </span>
          <a class="art-link" href="#download" aria-label="前往下载" title="前往下载">
            <ArrowUpRight :size="18" :stroke-width="2.2" />
          </a>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: 56px;
  align-items: center;
}

.hero-copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 20px;
}

.accent-word {
  color: var(--accent);
}

.hero-lead {
  max-width: 44ch;
  text-wrap: pretty;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 4px;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 22px;
  margin-top: 6px;
  color: var(--text-faint);
  font-size: 13px;
}

.hero-meta span {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.hero-meta span::before {
  content: '';
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--accent);
}

.hero-art {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px;
  border: 1px solid var(--stroke);
  border-radius: var(--r-md);
  background: linear-gradient(180deg, var(--surface) 0%, var(--bg-soft) 100%);
  box-shadow: var(--shadow);
}

.art-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--text-faint);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
}

.art-top svg {
  color: var(--accent);
}

.mascot {
  width: 100%;
  aspect-ratio: 1 / 1;
  height: auto;
  object-fit: cover;
  border-radius: var(--r-sm);
  background: var(--surface-3);
}

.art-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-top: 4px;
  color: var(--text-dim);
  font-size: 14px;
  line-height: 1.5;
}

.art-bottom strong {
  color: var(--text);
  font-weight: 700;
}

.art-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border: 1px solid var(--stroke);
  border-radius: var(--r-pill);
  background: var(--surface-2);
  color: var(--accent);
  transition: background-color 0.2s var(--ease), border-color 0.2s var(--ease);
}

.art-link:hover {
  border-color: var(--accent);
  background: var(--accent-soft);
}

@media (max-width: 1000px) {
  .hero-grid {
    gap: 36px;
  }
}

@media (max-width: 860px) {
  .hero-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 32px;
  }

  .hero-art {
    max-width: 420px;
  }
}

@media (max-width: 700px) {
  .hero-art {
    max-width: none;
    padding: 12px;
    gap: 10px;
  }

  .hero-actions .btn {
    flex: 1 1 auto;
  }
}

@media (max-width: 520px) {
  .hero-copy {
    gap: 12px;
  }

  .hero-lead {
    font-size: 15px;
    line-height: 1.55;
  }

  /* 窄屏不再强制换行，避免断出孤字 */
  .lead-break {
    display: none;
  }

  .hero-actions {
    gap: 10px;
  }

  .hero-actions .btn {
    min-height: 48px;
    padding: 0 18px;
  }

  .hero-meta {
    gap: 6px 16px;
    font-size: 12.5px;
  }

  .mascot {
    aspect-ratio: 5 / 4;
    max-height: 260px;
    object-position: center 32%;
  }

  .art-bottom {
    font-size: 13px;
  }
}
</style>
