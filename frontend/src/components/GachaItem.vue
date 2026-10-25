<template>
  <div class="gacha-item-container" :class="{ 'is-share': props.shareMode, 'is-collapsed': props.collapsed }">
    <div class="gacha-metrics">
      <div class="gacha-summary">
        <span class="metric-label">累计抽数</span>
        <span class="metric-value">{{ totalDrawCount }}</span>
        <span class="metric-unit">DRAWS</span>
        <span class="metric-note">当前垫 {{ currentPadCount }}</span>
      </div>
      <div class="gacha-summary">
        <span class="metric-label">五星记录</span>
        <span class="metric-value">{{ ssrTotal }}</span>
        <span class="metric-unit">SSR</span>
        <span v-if="props.pool_type !== 'permanent'" class="metric-wai" :title="`歪出 ${waiCount} 个五星`">
          <small>歪出</small><strong>{{ waiCount }}</strong>
        </span>
        <span v-else class="metric-note">常驻档案</span>
      </div>
    </div>

    <div class="gacha-body" :class="{ 'is-collapsed': props.collapsed }" :aria-hidden="props.collapsed">
      <div class="gacha-body-inner">
        <div v-if="totalDrawCount === 0" class="gacha-empty" aria-label="暂无抽卡记录">
      <span class="empty-reticle" aria-hidden="true" />
      <strong>暂无作战记录</strong>
      <p>点击顶部「更新记录」同步最新抽卡档案。</p>
      <span class="empty-code">AWAITING DATA // 00</span>
    </div>

    <template v-else>
      <div class="ssr-grid" v-if="ssrTotal > 0" aria-label="五星记录缩略图">
        <div v-for="item in ssrList" :key="`${item.drawTime}-${item.item}-${item.drawIndex}`" class="ssr-grid-avatar" :title="item.name">
          <img v-if="!imageFailures[item.item]" :src="getImagePath(item.item)" :alt="item.name" @error="imageFailures[item.item] = true" />
          <span v-else class="grid-avatar-fallback">{{ isWeaponItem(item.item) ? '武' : item.name.slice(0, 1) }}</span>
        </div>
      </div>
      <div class="ssr-details">
        <div class="ssr-item pity-row tone-gold">
          <div class="record-avatar question-avatar" aria-label="当前垫抽">?</div>
          <span class="draw-cost">{{ currentPadCount }}</span>
          <div class="draw-bar" role="progressbar" aria-label="当前垫抽" :aria-valuenow="currentPadCount" aria-valuemin="0" :aria-valuemax="Math.max(80, currentPadCount)">
            <div class="bar-fill" :style="{ width: progressWidth(currentPadCount) }"></div>
          </div>
          <span class="wai-tag wai-hidden" aria-hidden="true">歪</span>
          <span class="ssr-name pity-name" :title="`已垫 ${currentPadCount} 抽`">已垫 {{ currentPadCount }} 抽</span>
        </div>
        <div v-for="item in ssrList" :key="`${item.drawTime}-${item.item}-${item.drawIndex}`" class="ssr-item" :class="progressTone(item.costDraws)">
          <div class="record-avatar" :title="item.name">
            <img v-if="!imageFailures[item.item]" :src="getImagePath(item.item)" :alt="item.name" @error="imageFailures[item.item] = true" />
            <span v-else class="avatar-fallback">{{ isWeaponItem(item.item) ? '武' : item.name.slice(0, 1) }}</span>
          </div>
          <span class="draw-cost" :title="`${item.costDraws} 抽`">{{ item.costDraws }}</span>
          <div class="draw-bar" role="progressbar" :aria-label="`${item.name}出金抽数`" :aria-valuenow="item.costDraws" aria-valuemin="0" :aria-valuemax="Math.max(80, item.costDraws)">
            <div class="bar-fill" :style="{ width: progressWidth(item.costDraws) }"></div>
          </div>
          <span class="wai-tag" :class="{ 'wai-hidden': !item.isWai || props.pool_type === 'permanent' }" :aria-hidden="!item.isWai || props.pool_type === 'permanent'">歪</span>
          <span class="ssr-name" :title="item.name">{{ item.name }}</span>
        </div>
      </div>
        </template>
      </div>
    </div>
  </div>

</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useGachaRecordStore } from '@/stores/gachaRecord'
import { useSSRStore } from '@/stores/ssr'
import { useImageCacheStore } from '@/stores/imageCache'

// 1. 定义props并添加类型/默认值校验
const props = defineProps({
  pool_type: {
    type: String,
    required: true,
    default: 'character',
    validator: (val) => ['character', 'weapon', 'permanent', 'custom_character', 'custom_weapon'].includes(val)
  },
  shareMode: {
    type: Boolean,
    default: false
  },
  collapsed: {
    type: Boolean,
    default: false
  }
})

// 2. 获取仓库实例
const gachaRecordStore = useGachaRecordStore()
const ssrStore = useSSRStore()
const imageCacheStore = useImageCacheStore()

// 所有行共用相同的80抽标尺；保留实际抽数，视觉宽度最多100%。
const imageFailures = ref({})
watch(() => imageCacheStore.images, () => { imageFailures.value = {} })
const progressWidth = (draws) => `${Math.max(0, Math.min(100, draws * 1.25))}%`
const progressTone = (draws) => draws < 30 ? 'tone-green' : draws < 60 ? 'tone-yellow' : 'tone-red'

// 动态获取图片路径（R2）
const getImagePath = (itemId) => {
  const remoteUrl = itemId === 'question'
    ? 'https://static.gf2gacha-xkl.uk/images/character/question.png'
    : `https://static.gf2gacha-xkl.uk/images/${isWeaponItem(itemId) ? 'weapon' : 'character'}/${itemId}.png`
  return imageCacheStore.images[remoteUrl] || remoteUrl
}

// 判断道具类型，以选择图片目录和加载失败时的占位文字。
// 判断依据（当前游戏 SSR 数据）：
//   限定武器表 SSR_weapon 中的 ID 都是武器
//   限定人形表 SSR_character 中的 ID 都是人形
//   常驻池物品（可能既不在限定武器表也不在限定人形表）：
//     人形 ID 为 4 位数字（如 1033），武器 ID 为 5 位数字（如 10493、10433）
// 优先用映射表判断，映射表查不到再用 ID 位数兜底
const isWeaponItem = (itemId) => {
  const id = itemId.toString()
  // 在限定武器表中 → 武器
  if ((ssrStore.SSR_weapon || {}).hasOwnProperty(id)) return true
  // 在限定人形表中 → 人形（非武器）
  if ((ssrStore.SSR_character || {}).hasOwnProperty(id)) return false
  // 常驻池物品兜底：5 位数字为武器，4 位数字为人形
  return id.length === 5
}

// 3. 动态获取对应卡池数据，兜底空数组
const gachaData = computed(() => {
  const poolMap = {
    character: gachaRecordStore.characterGacha,
    weapon: gachaRecordStore.weaponGacha,
    permanent: gachaRecordStore.permanentGacha,
    custom_character: gachaRecordStore.customCharacterGacha,
    custom_weapon: gachaRecordStore.customWeaponGacha
  }
  return poolMap[props.pool_type] || []
})

// 4. 获取对应五星映射表
// 说明：角色池/武器池的五星判定需包含常驻池物品（因为可能抽出常驻池人形/武器即"歪"）
// 合并时用 spread 顺序让限定池(character/weapon)优先于常驻池(permanent)
const permanentMap = computed(() => ssrStore.SSR_permanent || {})

const getSsrMap = computed(() => {
  const permanent = permanentMap.value
  const ssrMap = {
    character: { ...permanent, ...(ssrStore.SSR_character || {}) },
    weapon: { ...permanent, ...(ssrStore.SSR_weapon || {}) },
    permanent: permanent,
    custom_character: { ...permanent, ...(ssrStore.SSR_custom_character || {}) },
    custom_weapon: { ...permanent, ...(ssrStore.SSR_custom_weapon || {}) }
  }
  return ssrMap[props.pool_type]
})

// 4.1 获取常驻池五星ID集合（用于判断歪）
// item 在常驻池中即为"歪"（即使它被角色/武器池的合并映射算作五星）
const permanentSSRSet = computed(() => {
  return new Set(Object.keys(permanentMap.value))
})

// 5. 核心重构：给所有抽卡记录添加【绝对原始索引】（所有统计的基础）
// absoluteIndex：代表该抽卡在总记录中的实际位置，从0开始，唯一不重复
const allDraws = computed(() => {
  // 保存页面索引，用于在时间戳相同时保持原始页面顺序
  const recordsWithPageIndex = gachaData.value.flatMap((page, pageIndex) =>
    (page.data?.list || []).map((draw) => ({
      ...draw,
      pageIndex // 保存原始页面索引（页面索引小的，数据越新）
    }))
  )

  // 排序：时间戳降序（最新的在前），时间戳相同时保持原始页面顺序
  return recordsWithPageIndex
    .sort((a, b) => {
      if (b.time !== a.time) {
        return b.time - a.time // 时间戳不同：新的在前
      }
      // 时间戳相同：保持原始页面顺序（页面索引小的在前，因为数组越靠上越新）
      return a.pageIndex - b.pageIndex
    })
    .map((draw, absoluteIndex) => ({
      ...draw,
      absoluteIndex // 新增：总抽卡的绝对原始索引（核心！）
    }))
})

// 6. 筛选五星抽卡记录 - 新增costDraws属性：出当前五星花费的抽数（包含自身1抽）
const ssrList = computed(() => {
  const ssrMap = getSsrMap.value
  const permanentSet = permanentSSRSet.value
  
  // 先筛选出所有五星（保留绝对索引）
  const ssrFiltered = allDraws.value
    .filter(draw => ssrMap.hasOwnProperty(draw.item))
    .map(draw => ({
      name: ssrMap[draw.item],
      poolId: draw.pool_id,
      drawTime: new Date(draw.time * 1000).toLocaleString(),
      time: draw.time,
      item: draw.item,
      drawIndex: draw.absoluteIndex, // 总抽卡的绝对原始索引
      isWai: permanentSet.has(draw.item.toString()) // 判断是否歪了（item在常驻池中即为歪）
    }))

  // 遍历给每个五星添加costDraws（花费抽数，包含自身）
  return ssrFiltered.map((current, index) => {
    let costDraws = 0
    if (ssrFiltered.length === 1) {
      // 只有1个五星：花费抽数 = 从该五星到最后的抽数（包含自身）
      costDraws = totalDrawCount.value - current.drawIndex
    } else {
      if (index < ssrFiltered.length - 1) {
        // 不是最后一个五星：花费抽数 = 下一个五星索引 - 当前五星索引（包含当前五星1抽）
        const nextSSR = ssrFiltered[index + 1]
        costDraws = nextSSR.drawIndex - current.drawIndex
      } else {
        // 最后一个五星：花费抽数 = 从该五星到最后的抽数（包含自身）
        costDraws = totalDrawCount.value - current.drawIndex
      }
    }
    return {
      ...current,
      costDraws, // 新增属性：出当前五星花费的抽数（包含自身1抽）
      tip: 'costDraws包含五星自身1抽，代表出上一个五星后（或最新抽卡开始）花了N抽出当前五星'
    }
  })
})

// 7. 基础统计（无需修改，逻辑正常）
const ssrTotal = computed(() => ssrList.value.length) // 五星总数
const totalDrawCount = computed(() => allDraws.value.length) // 总抽卡数

// 7.1 计算歪数（角色池和武器池）
const waiCount = computed(() => {
  // 只有角色池和武器池需要计算歪数
  if (props.pool_type === 'permanent') {
    return 0 // 常驻池没有歪的概念
  }
  return ssrList.value.filter(item => item.isWai).length
})

// 8. 当前垫抽数 - 核心公式修正（基于绝对索引）
// 公式：垫抽数 = 最晚出的五星（最新的）之前的非五星数量 = 最新五星的索引
const currentPadCount = computed(() => {
  if (ssrTotal.value > 0) {
    const latestSSR = ssrList.value[0] // 最晚出的五星（最新的）
    return latestSSR.drawIndex
  }
  return totalDrawCount.value
})

// 9. 五星抽卡间隔 + 最后五星低星统计 - 按需求修正：抽数包含五星本身，需+1（去掉原-1）
const ssrIntervals = computed(() => {
  const intervals = []
  // 不足2个五星，仅统计最后五星（若有）的低星抽数
  if (ssrTotal.value < 2) {
    if (ssrTotal.value === 1) {
      const lastSSR = ssrList.value[0]
      // 最后五星后低星抽数（非五星数量，公式不变）
      const lowStarCountAfterLast = totalDrawCount.value - lastSSR.drawIndex - 1
      intervals.push({
        type: '最后五星后低星统计',
        lastSSR: lastSSR.name,
        lowStarDrawCount: lowStarCountAfterLast,
        tip: '该数值为最后一次出五星后，累计抽的非五星卡（四星/三星）数量'
      })
    }
    return intervals
  }

  // 计算【相邻五星之间】的抽数间隔 - 核心修改：去掉-1，抽数包含五星本身
  // 公式：interval = 后一个五星索引 - 前一个五星索引 （包含当前五星，即出前一个后花了N抽出当前五星，含当前五星1抽）
  for (let i = 0; i < ssrList.value.length - 1; i++) {
    const preSSR = ssrList.value[i]     // 后出的五星（最新）
    const nextSSR = ssrList.value[i + 1] // 先出的五星（更旧）
    const interval = nextSSR.drawIndex - preSSR.drawIndex // 去掉原有的 -1
    // 过滤≤0的无效间隔（同十连出多个五星的情况，间隔为0/负数无意义）
    if (interval > 0) {
      intervals.push({
        type: '五星间抽数间隔',
        preSSR: preSSR.name,
        nextSSR: nextSSR.name,
        drawCount: interval, // 结果：出nextSSR后，花了interval抽出preSSR（包含preSSR本身1抽）
        tip: '该数值包含当前五星本身，即出前一个五星后累计抽N抽出当前五星'
      })
    }
  }

  // 统计【最后一个五星后】的低星抽数（非五星数量，公式不变）
  const lastSSR = ssrList.value[0]
  const lowStarCountAfterLast = totalDrawCount.value - lastSSR.drawIndex - 1
  intervals.push({
    type: '最后五星后低星统计',
    lastSSR: lastSSR.name,
    lowStarDrawCount: lowStarCountAfterLast,
    tip: '该数值为最后一次出五星后，累计抽的非五星卡（四星/三星）数量'
  })

  return intervals
})

</script>

<style scoped>
.gacha-item-container {
  width: 100%;
  color: #1a1d1f;
  font-family: var(--font-ui);
}

.gacha-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  margin-bottom: 10px;
  border: 1px solid #d1cabc;
  background: #d1cabc;
  transition: margin-bottom 0.32s cubic-bezier(0.22, 1, 0.36, 1);
}
.gacha-item-container.is-collapsed .gacha-metrics { margin-bottom: 0; }
.gacha-body {
  display: grid;
  grid-template-rows: 1fr;
  opacity: 1;
  overflow: hidden;
  transition:
    grid-template-rows 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.2s ease;
  will-change: grid-template-rows, opacity;
}
.gacha-body.is-collapsed {
  grid-template-rows: 0fr;
  opacity: 0;
  pointer-events: none;
}
.gacha-body-inner { min-height: 0; overflow: hidden; }
.gacha-summary {
  min-width: 0;
  display: grid;
  grid-template-columns: auto auto 1fr;
  align-items: baseline;
  column-gap: 5px;
  padding: 8px 9px 7px;
  background: #eeeadf;
}
.metric-label {
  grid-column: 1 / -1;
  margin-bottom: 2px;
  color: #858075;
  font-size: 8.5px;
  letter-spacing: 0.4px;
}
.metric-value {
  color: #171a1c;
  font: 700 19px/1 var(--font-technical);
  font-variant-numeric: tabular-nums;
}
.metric-unit { color: #9b5f42; font: 7px/1 var(--font-technical); letter-spacing: 0.7px; }
.metric-wai {
  justify-self: end;
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  padding: 2px 5px 1px;
  color: #a6372a;
  background: rgba(216, 77, 62, 0.1);
  border: 1px solid rgba(196, 62, 49, 0.34);
  line-height: 1;
  white-space: nowrap;
}
.metric-wai small { color: #9b5147; font-size: 8px; letter-spacing: 0.25px; }
.metric-wai strong {
  color: #b4382b;
  font: 700 13px/1 var(--font-technical);
  font-variant-numeric: tabular-nums;
}
.metric-note {
  justify-self: end;
  overflow: hidden;
  color: #706b62;
  font-size: 8.5px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.gacha-empty {
  position: relative;
  min-height: 232px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 24px 12px;
  background:
    linear-gradient(rgba(37, 40, 41, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(37, 40, 41, 0.035) 1px, transparent 1px),
    #e5e0d5;
  background-size: 18px 18px;
  border: 1px solid #d1cabc;
  text-align: center;
}
.gacha-empty::before,
.gacha-empty::after {
  content: "";
  position: absolute;
  width: 18px;
  height: 18px;
  border-color: #a49e91;
  border-style: solid;
}
.gacha-empty::before { left: 8px; top: 8px; border-width: 1px 0 0 1px; }
.gacha-empty::after { right: 8px; bottom: 8px; border-width: 0 1px 1px 0; }
.empty-reticle {
  position: relative;
  width: 34px;
  height: 34px;
  margin-bottom: 12px;
  border: 1px solid #8e8a80;
  border-radius: 50%;
}
.empty-reticle::before,
.empty-reticle::after {
  content: "";
  position: absolute;
  left: 50%;
  top: 50%;
  background: #8e8a80;
  transform: translate(-50%, -50%);
}
.empty-reticle::before { width: 20px; height: 1px; }
.empty-reticle::after { width: 1px; height: 20px; }
.gacha-empty strong {
  color: #343634;
  font-size: 12.5px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.gacha-empty p { margin: 6px 0 11px; color: #7c786f; font-size: 9.5px; line-height: 1.5; }
.empty-code { color: #aaa497; font: 7.5px/1 var(--font-technical); letter-spacing: 1px; }

.ssr-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 6px;
  margin: 9px 0 11px;
  padding: 7px;
  background:
    repeating-linear-gradient(135deg, rgba(255, 255, 255, 0.035) 0 5px, transparent 5px 10px),
    #202428;
  border-left: 2px solid var(--signal);
}
.ssr-grid > div { min-width: 0; }
.ssr-grid-avatar {
  width: 100%;
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: #34393d;
  border: 1px solid #4d5357;
}
.ssr-grid-avatar img { width: 100%; height: 100%; object-fit: contain; }

.ssr-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 2px;
}
.ssr-item {
  display: grid;
  grid-template-columns: 29px 28px minmax(0, 1fr) 18px 68px;
  align-items: center;
  gap: 5px;
  min-height: 39px;
  padding: 5px 7px;
  background: #e9e5db;
  border: 1px solid #c9c2b4;
}
.pity-row {
  padding-left: 5px;
  background-color: #e9e5db;
  background-image: linear-gradient(90deg, rgba(212, 160, 39, 0.12), transparent 72%);
  border-left: 3px solid #c69432;
}
.record-avatar {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: #ddd8cd;
  border: 1px solid #c3bcae;
}
.record-avatar img { display: block; width: 100%; height: 100%; object-fit: contain; }
.avatar-fallback { color: #626761; font-size: 11px; }
.question-avatar { color: #9b702e; font: 700 18px/1 var(--font-technical); }
.draw-cost {
  color: var(--draw-color);
  font: 700 13px/1 var(--font-technical);
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.draw-bar { min-width: 0; height: 17px; background: #d5cfc3; }
.bar-fill {
  height: 100%;
  background-color: var(--bar-base);
  background-image: linear-gradient(45deg,
    var(--bar-light) 25%, var(--bar-base) 25%, var(--bar-base) 50%,
    var(--bar-light) 50%, var(--bar-light) 75%, var(--bar-base) 75%);
  background-size: 20px 20px;
  clip-path: polygon(0 0, calc(100% - 5px) 0, 100% 50%, calc(100% - 5px) 100%, 0 100%);
  animation: stripe-move 1.8s linear infinite;
}
@keyframes stripe-move { from { background-position: 0 0; } to { background-position: 20px 0; } }
.tone-green { --bar-base: #3b9b6b; --bar-light: #64bb8e; --draw-color: #28734f; }
.tone-yellow { --bar-base: #d2a02d; --bar-light: #e7c15f; --draw-color: #8c681a; }
.tone-red { --bar-base: #c84a39; --bar-light: #df7060; --draw-color: #a32d25; }
.tone-gold { --bar-base: #c69432; --bar-light: #e2bd64; --draw-color: #956a1c; }

.wai-tag {
  width: 18px;
  padding: 2px 0;
  color: #fff;
  background: #d84d3e;
  font-size: 9px;
  line-height: 14px;
  text-align: center;
}
.wai-hidden { visibility: hidden; }
.ssr-name {
  min-width: 0;
  overflow: hidden;
  color: #4d4f4c;
  font-size: 10.5px;
  line-height: 1.4;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.pity-name { color: #87621f; }
.is-share .ssr-name { overflow: visible; white-space: normal; overflow-wrap: anywhere; }
.is-share .draw-bar { background: #bcb4a5; box-shadow: inset 0 0 0 1px #9d9587; }
.is-share .bar-fill { animation: none; background-position: 0 0; }
.grid-avatar-fallback {
  width: 100%;
  height: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #d8d8d2;
  background: #3c4246;
  font-size: 11px;
}

@media (prefers-reduced-motion: reduce) { .bar-fill { animation: none; } }
</style>