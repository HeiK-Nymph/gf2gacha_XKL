<script setup>
import { ArrowUpRight, BookOpen, MessageSquareWarning, PlayCircle } from '@lucide/vue'

import { GUIDE_URL, RELEASES_URL, REPO_URL, platforms } from '@/data/releases'

const helpLinks = [
  {
    icon: PlayCircle,
    label: '需要一点指引？',
    action: '打开视频教程',
    href: GUIDE_URL,
    external: true,
  },
  {
    icon: MessageSquareWarning,
    label: '遇到问题想反馈？',
    action: '去 GitHub 提 Issue',
    href: `${REPO_URL}/issues`,
    external: true,
  },
  {
    icon: BookOpen,
    label: '想看实现细节？',
    action: '浏览源代码与说明',
    href: RELEASES_URL,
    external: true,
  },
]
</script>

<template>
  <section id="guide" class="section guide">
    <div class="shell">
      <div class="section-head">
        <div>
          <span class="eyebrow">HOW TO START</span>
          <h2 class="section-title">
            三步，<br />
            拿到你的记录。
          </h2>
        </div>
        <p class="lead section-lead">
          两个版本的操作方式不一样，选自己那台设备照着做就行。<br />
          第一次配置完，之后每次只用点一下。
        </p>
      </div>

      <div class="guide-grid">
        <article v-for="item in platforms" :key="item.id" class="guide-col">
          <header class="guide-head">
            <h3>{{ item.label }} · {{ item.system }}</h3>
            <span class="guide-file mono">{{ item.fileName }}</span>
          </header>
          <ol class="guide-steps">
            <li v-for="(step, index) in item.steps" :key="step">
              <span class="step-index">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="step-text">{{ step }}</span>
            </li>
          </ol>
        </article>
      </div>

      <div class="help-links">
        <a
          v-for="link in helpLinks"
          :key="link.action"
          class="help-link"
          :href="link.href"
          :target="link.external ? '_blank' : undefined"
          :rel="link.external ? 'noopener noreferrer' : undefined"
        >
          <span class="help-icon"><component :is="link.icon" :size="18" :stroke-width="2" /></span>
          <span class="help-text">
            {{ link.label }}
            <strong>{{ link.action }}</strong>
          </span>
          <ArrowUpRight :size="17" :stroke-width="2" />
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

.guide-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.guide-col {
  padding: 24px;
  border: 1px solid var(--stroke);
  border-radius: var(--r-md);
  background: var(--surface);
}

.guide-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--stroke);
}

.guide-head h3 {
  font-size: 16px;
  font-weight: 700;
}

.guide-file {
  color: var(--text-faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.guide-steps {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 18px;
}

.guide-steps li {
  display: flex;
  gap: 14px;
}

.step-index {
  flex-shrink: 0;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  padding-top: 2px;
}

.step-text {
  color: var(--text-dim);
  font-size: 14.5px;
}

.help-links {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-top: 32px;
}

.help-link {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  border: 1px solid var(--stroke);
  border-radius: var(--r-md);
  background: var(--bg-soft);
  transition: border-color 0.2s var(--ease), background-color 0.2s var(--ease);
}

.help-link:hover {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.help-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border-radius: var(--r-sm);
  background: var(--surface-2);
  color: var(--accent);
}

.help-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  color: var(--text-faint);
  font-size: 13px;
}

.help-text strong {
  color: var(--text);
  font-size: 15px;
  font-weight: 700;
}

.help-link > svg {
  color: var(--text-faint);
  flex-shrink: 0;
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

  .guide-grid,
  .help-links {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
