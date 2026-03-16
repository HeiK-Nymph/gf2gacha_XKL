<template>
  <div class="gacha-item-container">
    <div>一共<span>{{ totalDrawCount }}</span>条抽卡记录，已垫<span>{{ currentPadCount }}</span>抽</div>
    <div>共获得五星<span>{{ ssrTotal }}</span>个，歪了<span v-if="props.pool_type !== 'permanent'"><span>{{ waiCount }}</span></span>个，具体如下：</div>
    <div class="ssr-grid" v-if="ssrTotal > 0">
      <div v-for="item in ssrList" :key="`${item.drawTime}-${item.item}-${item.drawIndex}`" >
        <img v-if="props.pool_type !== 'weapon'" :src="getImagePath(item.item)" style="width: 35px;"/>
        <span v-else class="weapon-name">{{ item.name }}</span>
      </div>
    </div>
    <div>
      <div class="ssr-item">



 
        <div v-if="totalDrawCount > 0">
          <img :src="getImagePath('question')" style="width: 35px;"/>
        </div>
        <el-progress  :text-inside="true" :stroke-width="26" :percentage="currentPadCount * 1.25" :format="ssrListFormat" :color="customColorMethod"/>
        <span class="wai-tag" style="background-color: white; padding: 0;"></span>
      </div>
      <div v-for="item in ssrList" :key="`${item.drawTime}-${item.item}-${item.drawIndex}`" class="ssr-item">

        <div>

          <img v-if="props.pool_type !== 'weapon'" :src="getImagePath(item.item)" style="width: 35px;"/>
          <span v-else class="weapon-name">{{ item.name }}</span>
        </div>
        <el-progress  :text-inside="true" :stroke-width="30" :percentage="item.costDraws * 1.25" :format="ssrListFormat" :color="customColorMethod"/>
        <span v-if="item.isWai && props.pool_type !== 'permanent'" class="wai-tag">歪</span>
        <span v-else class="wai-tag" style="background-color: white; padding: 0;"></span>
      </div>
    </div>
    
    <!-- 显示原始数据按钮 -->
    <div style="margin-top: 20px; text-align: center;">
      <el-button type="info" @click="toggleRawData">
        {{ showRawData ? '隐藏原始数据' : '显示原始数据' }}
      </el-button>
    </div>
    
    <!-- 原始数据显示区域 -->
    <div v-if="showRawData" class="raw-data-container" style="margin-top: 20px; padding: 15px; background: #f5f5f5; border-radius: 8px;">
      <div style="margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
        <span>原始数据 (共{{ totalPages }}页)</span>
        <div style="display: flex; align-items: center; gap: 10px;">
          <el-input-number
            v-model="inputPage"
            :min="1"
            :max="totalPages"
            size="small"
            style="width: 120px;"
            controls-position="right"
            @change="jumpToPage"
          />
          <el-button size="small" @click="jumpToPage">跳转</el-button>
        </div>
      </div>
      <div class="raw-data-list">
        <div v-if="currentPageData.length === 0" style="text-align: center; padding: 20px; color: #999;">
          暂无数据
        </div>
        <div v-else>
          <div style="text-align: center; margin-bottom: 10px; color: #666; font-size: 14px;">
            当前显示：第 {{ currentPage }} 页
          </div>
          <div v-for="(item, index) in currentPageData" :key="index" class="raw-data-item">
            <span>{{ index + 1 + (currentPage - 1) * 6 }}. {{ item }}</span>
          </div>
        </div>
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
    validator: (val) => ['character', 'weapon', 'permanent'].includes(val)
  }
})

// 2. 获取仓库实例
const gachaRecordStore = useGachaRecordStore()
const ssrStore = useSSRStore()

// 原始数据相关
const showRawData = ref(false)
const currentPage = ref(1)
const inputPage = ref(1)
const pageSize = 6

// 自定义进度条格式化函数
const ssrListFormat = (percentage) => {
  return percentage * 0.8 + '抽'
}

// 自定义进度条颜色函数
const customColorMethod = (percentage) => {
  if (percentage * 0.8 < 30){
    return '#66ad68'
  }
  if (percentage * 0.8 < 60){
    return '#F0C044'
  }
  return '#D66555'
}

// 动态获取图片路径（R2）
const getImagePath = (itemId) => {
  if (itemId === 'question') {
    return 'https://static.gf2gacha-xkl.uk/images/character/question.png'
  }
  return `https://static.gf2gacha-xkl.uk/images/character/${itemId}.png`
}

// 3. 动态获取对应卡池数据，兜底空数组
const gachaData = computed(() => {
  const poolMap = {
    character: gachaRecordStore.characterGacha,
    weapon: gachaRecordStore.weaponGacha,
    permanent: gachaRecordStore.permanentGacha
  }
  return poolMap[props.pool_type] || []
})

// 4. 获取对应五星映射表
const getSsrMap = computed(() => {
  const ssrMap = {
    character: ssrStore.SSR_character || {},
    weapon: ssrStore.SSR_weapon || {},
    permanent: ssrStore.SSR_permanent || {}
  }
  return ssrMap[props.pool_type]
})

// 4.1 获取常驻池五星ID集合（用于判断歪）
const permanentSSRSet = computed(() => {
  const permanentMap = ssrStore.SSR_permanent || {}
  return new Set(Object.keys(permanentMap))
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

// 10. 原始数据相关计算属性
// 获取所有原始数据（按原始页面顺序，即数组顺序）
const rawData = computed(() => {
  return gachaData.value.flatMap((page) =>
    (page.data?.list || []).map((draw) => draw.item)
  )
})

// 总页数
const totalPages = computed(() => {
  return Math.ceil(rawData.value.length / pageSize) || 1
})

// 当前页的数据
const currentPageData = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  const end = start + pageSize
  return rawData.value.slice(start, end)
})

// 切换显示/隐藏原始数据
const toggleRawData = () => {
  showRawData.value = !showRawData.value
  if (showRawData.value) {
    currentPage.value = 1 // 显示时重置到第一页
    inputPage.value = 1 // 重置输入框为第一页
  }
}

// 跳转到指定页面
const jumpToPage = () => {
  if (inputPage.value >= 1 && inputPage.value <= totalPages.value) {
    currentPage.value = inputPage.value
  } else {
    // 如果输入超出范围，自动修正
    inputPage.value = Math.max(1, Math.min(inputPage.value, totalPages.value))
    currentPage.value = inputPage.value
  }
}
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
.gacha-item-container span{
  color: red;
}
.ssr-grid {
  display: grid;
  margin: 30px 0;
  margin-top: 15px;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  padding: 5px;
  background-color: gold;
  border-radius: 15px;
}
.ssr-item {
  display: flex;
  align-items: center;
  gap: 16px; /* 名称和进度条之间的间距 */
  margin: 10px 0;
}
.ssr-item .el-progress {
  flex: 1; /* 让进度条占据剩余空间 */
}
:deep(.ssr-item span) {
  color: #9C27B0;
  /* 可追加其他样式，比如字体加粗、字号等 */
  font-weight: bold;

}
.wai-tag {
  display: inline-block;
  margin-left: 8px;
  padding: 2px 6px;
  font-size: 12px;
  width: 20px;
  color: #fff;
  background-color: #ff4757;
  border-radius: 4px;
  text-align: center;
}

.weapon-name {
  display: inline-block;
  padding: 5px;
  font-size: 12px;
  color: #fff;
  background-color: #2196F3;
  border-radius: 4px;
  text-align: center;
  white-space: nowrap;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;

}

.raw-data-container {
  font-family: monospace;
}

.raw-data-list {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 10px;
  background: white;
}

.raw-data-item {
  padding: 4px 8px;
  border-bottom: 1px solid #eee;
  font-size: 13px;
  color: #333;
}

.raw-data-item:last-child {
  border-bottom: none;
}

</style>