<script setup>
import { ArrowUpRight, BarChart3, Images, ScanLine } from '@lucide/vue'

const features = [
  {
    index: '01 / 一键抓取',
    icon: ScanLine,
    title: '进一次招募页，\n它就记住了。',
    desc: '电脑版内置代理，捕获一次游戏请求后反复重放。\n不用自己抓包，也不用改网络设置。',
  },
  {
    index: '02 / 五池统计',
    icon: BarChart3,
    title: '抽数与保底，\n一次算清。',
    desc: '角色池、武器池、常驻池，加上自选角色与自选武器。\n每个池子分别计数，也看得到总投入。',
  },
  {
    index: '03 / 分享长图',
    icon: Images,
    title: '晒一晒运气，\n不用自己拼图。',
    desc: '竖版长图一键导出，暗金配色，出金记录一目了然。\n直接发微信、QQ 或存进相册。',
  },
]
</script>

<template>
  <section id="features" class="section features">
    <div class="shell">
      <div class="section-head">
        <div>
          <span class="eyebrow">YOUR RECORDS, YOUR WAY</span>
          <h2 class="section-title">
            工具安静地干活，<br />
            你只管抽卡。
          </h2>
        </div>
        <p class="lead section-lead">
          记录、统计、分享都留在自己设备上。<br />
          不登录、不上传、不打扰。
        </p>
      </div>

      <div class="feature-grid">
        <article v-for="feature in features" :key="feature.index" class="feature">
          <div class="feature-top">
            <span class="feature-icon"><component :is="feature.icon" :size="20" :stroke-width="2" /></span>
            <ArrowUpRight class="feature-arrow" :size="18" :stroke-width="2" />
          </div>
          <span class="feature-index">{{ feature.index }}</span>
          <h3 class="feature-title">{{ feature.title }}</h3>
          <p class="feature-desc">{{ feature.desc }}</p>
        </article>
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
  max-width: 38ch;
  text-align: right;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.feature {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 24px;
  border: 1px solid var(--stroke);
  border-radius: var(--r-md);
  background: var(--surface);
  transition: border-color 0.2s var(--ease), transform 0.2s var(--ease);
}

.feature:hover {
  border-color: var(--stroke-strong);
  transform: translateY(-2px);
}

.feature-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.feature-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: var(--r-sm);
  background: var(--accent-soft);
  color: var(--accent);
}

.feature-arrow {
  color: var(--text-faint);
}

.feature-index {
  color: var(--text-faint);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.feature-title {
  font-size: 20px;
  line-height: 1.35;
  font-weight: 700;
  white-space: pre-line;
}

.feature-desc {
  color: var(--text-dim);
  font-size: 14px;
  white-space: pre-line;
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

  .feature-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
