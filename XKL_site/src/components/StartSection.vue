<script setup>
import { ArrowRight } from '@lucide/vue'
</script>

<template>
  <section class="section start">
    <div class="shell start-inner">
      <div class="start-copy">
        <span class="eyebrow">READY WHEN YOU ARE</span>
        <h2 class="start-title">下一次招募，<br />就让它替你记着。</h2>
        <p class="lead">装好工具，进一次招募页面，剩下的交给它。</p>
      </div>
      <a class="btn btn--primary btn--lg" href="#download">
        选择你的版本
        <ArrowRight :size="19" :stroke-width="2.2" />
      </a>
    </div>
  </section>
</template>

<style scoped>
.start-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 40px;
  padding: 44px;
  border: 1px solid var(--stroke);
  border-radius: var(--r-md);
  background:
    radial-gradient(120% 140% at 100% 0%, var(--accent-soft) 0%, transparent 55%),
    var(--surface);
}

.start-copy {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.start-title {
  font-size: clamp(24px, 3vw, 34px);
  line-height: 1.24;
  font-weight: 800;
  letter-spacing: -0.01em;
}

@media (max-width: 900px) {
  .start-inner {
    flex-direction: column;
    align-items: flex-start;
    padding: 28px;
  }
}

@media (max-width: 520px) {
  .start-inner {
    padding: 24px 20px;
  }
}
</style>
