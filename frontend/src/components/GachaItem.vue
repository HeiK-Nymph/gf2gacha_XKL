<template>
  <div class="gacha-item-container" :class="{ 'is-share': shareMode }">
    <div class="gacha-summary">一共<span>{{ totalDrawCount }}</span>条抽卡记录，已垫<span>{{ currentPadCount }}</span>抽</div>
    <div class="gacha-summary">共获得五星<span>{{ ssrTotal }}</span>个，歪了<span v-if="props.pool_type !== 'permanent'"><span>{{ waiCount }}</span></span>个，具体如下：</div>
    <div class="ssr-grid" v-if="ssrTotal > 0">
      <div v-for="item in ssrList" :key="`${item.drawTime}-${item.item}-${item.drawIndex}`" class="ssr-grid-avatar" :title="item.name">
        <img v-if="!imageFailures[item.item]" :src="getImagePath(item.item)" :alt="item.name" @error="imageFailures[item.item] = true" />
        <span v-else class="grid-avatar-fallback">{{ isWeaponItem(item.item) ? '武' : item.name.slice(0, 1) }}</span>
      </div>
    </div>
    <div class="ssr-details">
      <div v-if="totalDrawCount > 0" class="ssr-item pity-row tone-gold">
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

  </div>

</template>

<script setup>
import { ref, computed } from 'vue'
import { useGachaRecordStore } from '@/stores/gachaRecord'
import { useSSRStore } from '@/stores/ssr'

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
  }
})

// 2. 获取仓库实例
const gachaRecordStore = useGachaRecordStore()
const ssrStore = useSSRStore()

// 所有行共用相同的80抽标尺；保留实际抽数，视觉宽度最多100%。
const imageFailures = ref({})
const progressWidth = (draws) => `${Math.max(0, Math.min(100, draws * 1.25))}%`
const progressTone = (draws) => draws < 30 ? 'tone-green' : draws < 60 ? 'tone-yellow' : 'tone-red'

// 动态获取图片路径（R2）
const getImagePath = (itemId) => {
  if (itemId === 'question') {
    return 'https://static.gf2gacha-xkl.uk/images/character/question.png'
  }
  return `https://static.gf2gacha-xkl.uk/images/${isWeaponItem(itemId) ? 'weapon' : 'character'}/${itemId}.png`
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
  box-sizing: border-box;
  width: 100%;
  padding: 16px;
  /* border: 1px solid #e5e7eb; */
  border-radius: 8px;
  background: #EBEEF5;
 
}
.gacha-summary span{
  color: red;
}
.ssr-grid {
  display: grid;
  margin: 30px 0;
  margin-top: 15px;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 16px;
  padding: 5px;
  background-color: gold;
  border-radius: 15px;
}
.ssr-grid > div { min-width: 0; }
.ssr-grid-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 35px;
  height: 35px;
}
.ssr-grid-avatar img {
  width: 35px;
  height: 35px;
  object-fit: contain;
}
.ssr-item {
  display: grid;
  grid-template-columns: 34px 32px minmax(0, 1fr) 20px 72px;
  align-items: center;
  column-gap: 6px;
  min-height: 38px;
  margin: 10px 0;
}
.record-avatar {
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  overflow: hidden;
  border-radius: 50%;
  background: #dce1e9;
}
.record-avatar img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.avatar-fallback {
  font-size: 13px;
  color: #626977;
}
.question-avatar {
  color: #9b741d;
  font-size: 23px;
  font-weight: bold;
}
.draw-cost {
  text-align: center;
  color: var(--draw-color);
  font-size: 15px;
  font-weight: bold;
  font-variant-numeric: tabular-nums;
}
.draw-bar {
  min-width: 0;
  height: 22px;
}
.bar-fill {
  height: 100%;
  border-radius: 6px;
  background-color: var(--bar-base);
  /* 普通线性渐变平铺，兼容 html2canvas 的静态分享图。 */
  background-image: linear-gradient(45deg,
    var(--bar-light) 25%, var(--bar-base) 25%, var(--bar-base) 50%,
    var(--bar-light) 50%, var(--bar-light) 75%, var(--bar-base) 75%);
  background-size: 28px 28px;
  animation: stripe-move 1.8s linear infinite;
}
@keyframes stripe-move {
  from { background-position: 0 0; }
  to { background-position: 28px 0; }
}
.tone-green { --bar-base: #00b050; --bar-light: #92d050; --draw-color: #278747; }
.tone-yellow { --bar-base: #ffc000; --bar-light: #ffd966; --draw-color: #936a00; }
.tone-red { --bar-base: #c00000; --bar-light: #c24146; --draw-color: #c00000; }
.tone-gold { --bar-base: #d9a93c; --bar-light: #efc964; --draw-color: #946c14; }
.wai-tag {
  box-sizing: border-box;
  width: 20px;
  padding: 2px 0;
  font-size: 11px;
  line-height: 16px;
  color: #fff;
  background: #e15d65;
  border-radius: 4px;
  text-align: center;
}
.wai-hidden { visibility: hidden; }
.ssr-name {
  min-width: 0;
  overflow: hidden;
  color: #514d40;
  font-size: 12px;
  line-height: 1.5;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.pity-name { color: #946c14; }
.is-share .ssr-name {
  overflow: visible;
  white-space: normal;
  overflow-wrap: anywhere;
}
.is-share .bar-fill { animation: none; background-position: 0 0; }
@media (prefers-reduced-motion: reduce) {
  .bar-fill { animation: none; }
}

.grid-avatar-fallback {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 35px;
  height: 35px;
  border-radius: 50%;
  color: #626977;
  background: #dce1e9;
}

</style>
