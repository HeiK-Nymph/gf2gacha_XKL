<template>
  <article class="analytics-card">
    <header class="analytics-head">
      <div><span class="analytics-code">{{ pool.code }}</span><h4>{{ pool.label }}</h4></div>
      <span class="analytics-type">{{ pool.type }}</span>
    </header>

    <div class="analytics-chart-row">
      <div class="donut-wrap" :aria-label="`${pool.label}星级分布`">
        <svg class="donut" viewBox="0 0 120 120" role="img" :class="{ scanning: hoveredKey !== null }">
          <circle class="donut-track" cx="60" cy="60" r="43" />
          <circle
            v-for="segment in donutSegments"
            :key="segment.key"
            class="donut-segment"
            :class="{ active: hoveredKey === segment.key, muted: hoveredKey !== null && hoveredKey !== segment.key }"
            cx="60"
            cy="60"
            r="43"
            tabindex="0"
            :stroke="segment.color"
            :stroke-dasharray="segment.dasharray"
            :stroke-dashoffset="segment.dashoffset"
            :aria-label="`${legends.find((item) => item.key === segment.key)?.label} ${legends.find((item) => item.key === segment.key)?.percent}`"
            @mouseenter="hoveredKey = segment.key"
            @mouseleave="hoveredKey = null"
            @focus="hoveredKey = segment.key"
            @blur="hoveredKey = null"
          />
        </svg>
        <div class="donut-center">
          <transition name="donut-value" mode="out-in">
            <div :key="hoveredLegend ? hoveredLegend.key : 'total'" class="donut-center-content">
              <strong>{{ hoveredLegend ? hoveredLegend.percent : pool.total }}</strong>
              <span>{{ hoveredLegend ? `${hoveredLegend.label} · ${hoveredLegend.count}` : 'DRAWS' }}</span>
            </div>
          </transition>
        </div>
      </div>
      <div class="analytics-legend">
        <div
          v-for="legend in legends"
          :key="legend.key"
          class="legend-row"
          :class="{ active: hoveredKey === legend.key, muted: hoveredKey !== null && hoveredKey !== legend.key }"
          tabindex="0"
          @mouseenter="hoveredKey = legend.key"
          @mouseleave="hoveredKey = null"
          @focus="hoveredKey = legend.key"
          @blur="hoveredKey = null"
        >
          <span class="legend-name"><i :style="{ background: legend.color }" />{{ legend.label }}</span>
          <strong>{{ legend.count }}</strong><small>{{ legend.percent }}</small>
        </div>
        <div class="legend-rule"></div>
        <div class="legend-note">当前垫抽 <b>{{ pool.pad }}</b></div>
      </div>
    </div>

    <div class="analytics-kpis">
      <div class="analysis-kpi"><span>平均出金</span><strong>{{ pool.avgSSR }}</strong><small>PULLS</small></div>
      <div class="analysis-kpi"><span>平均 UP</span><strong>{{ pool.avgUp }}</strong><small>PULLS</small></div>
      <div class="analysis-kpi analysis-kpi--wai"><span>歪率</span><strong>{{ pool.waiRate }}</strong><small>{{ pool.isPermanent ? 'N/A' : '%' }}</small></div>
    </div>

    <div class="analytics-records-head"><span>五星抽卡记录</span><b>{{ pool.fiveStars.length }} RECORDS</b></div>
    <div v-if="pool.fiveStars.length" class="record-chip-grid">
      <span v-for="item in pool.fiveStars" :key="`${item.time}-${item.item}-${item.costDraws}`" class="record-chip" :class="progressTone(item.costDraws)" :title="`${item.name} · ${item.costDraws} 抽${item.isWai ? ' · 歪' : ''}`">
        <span class="chip-name">{{ item.name }}</span><strong>{{ item.costDraws }}</strong><em v-if="item.isWai">歪</em>
      </span>
    </div>
    <div v-else class="analytics-empty">暂无五星抽卡记录</div>
  </article>
</template>

<script setup>
import { computed, ref } from 'vue'
const props = defineProps({ pool: { type: Object, required: true } })
const pool = computed(() => props.pool)
const hoveredKey = ref(null)
const progressTone = (draws) => draws < 30 ? 'tone-green' : draws < 60 ? 'tone-yellow' : 'tone-red'
const COLORS = { 5: '#dfac45', 4: '#b58bb8', 3: '#5891c5' }
const LABELS = { 5: '五星', 4: '四星', 3: '三星' }
const CIRCUMFERENCE = 2 * Math.PI * 43
const totalRarity = computed(() => {
  const rarity = props.pool.rarity || { 5: 0, 4: 0, 3: 0 }
  return (rarity[5] || 0) + (rarity[4] || 0) + (rarity[3] || 0)
})
const donutSegments = computed(() => {
  let offset = 0
  return [5, 4, 3].map((key) => {
    const length = totalRarity.value ? ((props.pool.rarity?.[key] || 0) / totalRarity.value) * CIRCUMFERENCE : 0
    const segment = { key, color: COLORS[key], dasharray: `${Math.max(0, length - 2)} ${CIRCUMFERENCE}`, dashoffset: -offset }
    offset += length
    return segment
  })
})
const legends = computed(() => [5, 4, 3].map((key) => {
  const count = props.pool.rarity?.[key] || 0
  return { key, label: LABELS[key], color: COLORS[key], count, percent: `${totalRarity.value ? ((count / totalRarity.value) * 100).toFixed(1) : '0.0'}%` }
}))
const hoveredLegend = computed(() => legends.value.find((item) => item.key === hoveredKey.value) || null)
</script>

<style scoped>
.analytics-card { position: relative; min-width: 0; padding: 16px 17px 17px; color: #e9e6dd; background: linear-gradient(135deg, rgba(255,255,255,.035), transparent 32%), repeating-linear-gradient(90deg, transparent 0 31px, rgba(255,255,255,.016) 31px 32px), #15191c; border: 1px solid #333a3f; border-top: 3px solid var(--signal); box-shadow: 0 12px 30px rgba(22,22,20,.18); overflow: hidden; }
.analytics-card::after { content: ""; position: absolute; right: 9px; bottom: 9px; width: 13px; height: 13px; border-right: 1px solid #4e555a; border-bottom: 1px solid #4e555a; pointer-events: none; }
.analytics-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding-bottom: 10px; border-bottom: 1px solid #343a3f; }
.analytics-code { color: #747c81; font: 8px/1 var(--font-technical); letter-spacing: 1.1px; }
.analytics-head h4 { margin: 4px 0 0; color: #f1eee6; font-size: 17px; font-weight: 750; letter-spacing: .6px; }
.analytics-type { padding: 3px 6px 2px; color: #a5abb0; border: 1px solid #41484d; font: 7.5px/1 var(--font-technical); letter-spacing: .8px; }
.analytics-chart-row { display: grid; grid-template-columns: 164px minmax(0, 1fr); align-items: center; gap: 15px; padding: 14px 0 12px; }
.donut-wrap { position: relative; width: 158px; height: 158px; }
.donut { width: 100%; height: 100%; transform: rotate(-90deg) scale(1); transform-origin: 50% 50%; transition: transform .34s cubic-bezier(.22,1,.36,1), filter .34s ease; }
.donut-wrap:hover .donut, .donut.scanning { transform: rotate(-90deg) scale(1.025); filter: drop-shadow(0 0 8px rgba(219,225,228,.09)); }
.donut-track, .donut-segment { fill: none; stroke-width: 13; }
.donut-track { stroke: #292f33; transition: opacity .24s ease; }
.donut-wrap:hover .donut-track { opacity: .68; }
.donut-segment { stroke-linecap: butt; cursor: pointer; outline: none; opacity: 1; transition: stroke-width .28s cubic-bezier(.22,1,.36,1), opacity .22s ease, filter .28s ease; }
.donut-segment.active { stroke-width: 18; filter: drop-shadow(0 0 5px rgba(255,255,255,.3)); }
.donut-segment.muted { opacity: .28; }
.donut-center { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; pointer-events: none; }
.donut-center-content { display: flex; flex-direction: column; align-items: center; justify-content: center; }
.donut-center strong { color: #fff; font: 700 29px/1 var(--font-technical); font-variant-numeric: tabular-nums; }
.donut-center span { margin-top: 5px; color: #71797e; font: 7.5px/1 var(--font-technical); letter-spacing: 1.1px; }
.donut-value-enter-active, .donut-value-leave-active { transition: opacity .16s ease, transform .16s ease; }
.donut-value-enter-from { opacity: 0; transform: translateY(5px); }
.donut-value-leave-to { opacity: 0; transform: translateY(-4px); }
.analytics-legend { min-width: 0; }
.legend-row { display: grid; grid-template-columns: minmax(0,1fr) 38px 54px; align-items: baseline; gap: 6px; padding: 7px 5px; margin: 0 -5px; border-bottom: 1px solid #2d3337; cursor: default; opacity: 1; transition: background .2s ease, opacity .2s ease, transform .24s cubic-bezier(.22,1,.36,1); }
.legend-row.active { background: rgba(255,255,255,.045); transform: translateX(2px); }
.legend-row.muted { opacity: .5; }
.legend-row:focus-visible { outline: 1px solid var(--signal); outline-offset: -1px; background: rgba(255,255,255,.04); }
.legend-name { display: inline-flex; align-items: center; gap: 7px; color: #aeb3b3; font-size: 10px; }
.legend-name i { width: 7px; height: 7px; flex: none; }
.legend-row strong { color: #f1eee6; font: 700 14px/1 var(--font-technical); text-align: right; }
.legend-row small { color: #737a7e; font: 8.5px/1 var(--font-technical); text-align: right; }
.legend-rule { height: 8px; }
.legend-note { color: #7e8589; font-size: 9.5px; text-align: right; }
.legend-note b { margin-left: 5px; color: var(--signal-hi); font: 700 13px/1 var(--font-technical); }
.analytics-kpis { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 1px; background: #343a3f; border: 1px solid #343a3f; }
.analysis-kpi { min-width: 0; padding: 8px 9px 7px; background: #1d2226; }
.analysis-kpi span { display: block; color: #7f878b; font-size: 8.5px; letter-spacing: .4px; }
.analysis-kpi strong { display: inline-block; margin-top: 4px; color: #ebe8df; font: 700 17px/1 var(--font-technical); font-variant-numeric: tabular-nums; }
.analysis-kpi small { margin-left: 4px; color: #666e72; font: 7px/1 var(--font-technical); }
.analysis-kpi--wai { border-left: 2px solid rgba(217,81,67,.72); }
.analysis-kpi--wai strong { color: #e07b6e; }
.analytics-records-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin: 14px 0 8px; color: #aeb3b3; font-size: 9.5px; }
.analytics-records-head b { color: #666e72; font: 7.5px/1 var(--font-technical); letter-spacing: .7px; }
.record-chip-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.record-chip { display: inline-flex; align-items: center; gap: 6px; min-height: 28px; padding: 4px 7px; color: var(--chip-text); background: var(--chip-bg); border: 1px solid var(--chip-border); border-left: 2px solid var(--chip-accent); }
.record-chip strong { color: var(--chip-strong); font: 700 10px/1 var(--font-technical); }
.record-chip strong::before { content: "["; margin-right: 1px; color: var(--chip-bracket); }
.record-chip strong::after { content: "]"; margin-left: 1px; color: var(--chip-bracket); }
.record-chip em { padding: 1px 3px; color: #ffb3a9; background: rgba(217,81,67,.2); border: 1px solid rgba(217,81,67,.45); font-size: 7px; font-style: normal; }
.record-chip.tone-green { --chip-text: #a8dab7; --chip-strong: #d7ecdc; --chip-bg: rgba(60,128,83,.16); --chip-border: rgba(91,166,115,.45); --chip-accent: #59a66d; --chip-bracket: #6c8d76; }
.record-chip.tone-yellow { --chip-text: #e2cb8d; --chip-strong: #f0dfb0; --chip-bg: rgba(185,139,32,.15); --chip-border: rgba(202,157,49,.46); --chip-accent: #c99b32; --chip-bracket: #94814e; }
.record-chip.tone-red { --chip-text: #e9a79d; --chip-strong: #f1c5be; --chip-bg: rgba(177,62,48,.16); --chip-border: rgba(200,76,60,.48); --chip-accent: #c34f40; --chip-bracket: #9e625a; }
.chip-name { max-width: 112px; overflow: hidden; font-size: 9.5px; white-space: nowrap; text-overflow: ellipsis; }
.analytics-empty { padding: 18px 12px; color: #666e72; border: 1px dashed #394045; font-size: 10px; text-align: center; }
@media (max-width: 1060px) { .analytics-chart-row { grid-template-columns: 142px minmax(0,1fr); } .donut-wrap { width: 138px; height: 138px; } }
</style>