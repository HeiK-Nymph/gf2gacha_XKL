<template>
  <div class="page-container">
    <el-card shadow="never" class="rank-card">
      <template #header>
        <div class="card-title-row">
          <span><el-icon><Trophy /></el-icon> 抽卡排行榜</span>
          <el-radio-group v-model="rankMode" size="default" @change="loadData">
            <el-radio-button value="luck">欧皇榜</el-radio-button>
            <el-radio-button value="draws">肝帝榜</el-radio-button>
          </el-radio-group>
        </div>
      </template>

      <el-table
        :data="displayList"
        stripe
        v-loading="loading"
        size="default"
        :row-class-name="tableRowClassName"
        max-height="calc(100vh - 260px)"
        @row-click="handleRowClick"
        class="rank-table"
      >
        <el-table-column label="排名" width="70" align="center">
          <template #default="{ $index }">
            <span class="rank-num" :class="'rank-' + ($index + 1)">
              {{ $index < 3 ? ['', '\u{1F947}', '\u{1F948}', '\u{1F949}'][$index + 1] : $index + 1 }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="userId" label="UID" width="120" />
        <el-table-column v-if="rankMode === 'luck'" prop="luckValue" label="欧皇值" width="120" sortable>
          <template #default="{ row }">
            <span class="luck-value">{{ row.luckValue }}</span>
          </template>
        </el-table-column>
        <el-table-column v-else prop="totalDraws" label="总抽数" width="120" sortable />
        <el-table-column label="评级" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getRankTag(row)" effect="dark" size="small">
              {{ getRankLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column min-width="1" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Trophy } from '@element-plus/icons-vue'
import { getRankingListApi } from '@/api'
import type { GfGachaRankingListVO, GfGachaRankingListDTO } from '@/types'

const loading = ref(false)
const rankMode = ref<'luck' | 'draws'>('luck')
const rankingData = ref<GfGachaRankingListDTO | null>(null)
const router = useRouter()

const displayList = computed(() => {
  if (!rankingData.value) return []
  return rankMode.value === 'luck'
    ? rankingData.value.gfGachaRankingListOrderByLuckValueDesc
    : rankingData.value.gfGachaRankingListOrderByTotalDrawsDesc
})

function tableRowClassName({ rowIndex }: { rowIndex: number }) {
  return rowIndex < 3 ? 'top-rank-row' : ''
}

function getRankLabel(row: GfGachaRankingListVO): string {
  if (rankMode.value === 'luck') {
    if (row.luckValue >= 700) return 'SSS'
    if (row.luckValue >= 500) return 'SS'
    if (row.luckValue >= 300) return 'S'
    if (row.luckValue >= 150) return 'A'
    return 'B+'
  } else {
    if (row.totalDraws >= 3000) return 'SSS 肝帝'
    if (row.totalDraws >= 2000) return 'SS'
    if (row.totalDraws >= 1000) return 'S'
    if (row.totalDraws >= 500) return 'A'
    return 'B+'
  }
}

function getRankTag(row: GfGachaRankingListVO): string {
  if (rankMode.value === 'luck') {
    if (row.luckValue >= 500) return 'danger'
    if (row.luckValue >= 300) return 'warning'
    if (row.luckValue >= 150) return ''
    return 'info'
  } else {
    if (row.totalDraws >= 2000) return 'danger'
    if (row.totalDraws >= 1000) return 'warning'
    if (row.totalDraws >= 500) return ''
    return 'info'
  }
}

function getLuckPercent(row: GfGachaRankingListVO): number {
  if (rankMode.value === 'luck') {
    const maxVal = Math.max(...(rankingData.value?.gfGachaRankingListOrderByLuckValueDesc.map(r => r.luckValue) || [1]))
    return Math.min(100, Math.round((row.luckValue / maxVal) * 100))
  } else {
    const maxVal = Math.max(...(rankingData.value?.gfGachaRankingListOrderByTotalDrawsDesc.map(r => r.totalDraws) || [1]))
    return Math.min(100, Math.round((row.totalDraws / maxVal) * 100))
  }
}

function getStatus(row: GfGachaRankingListVO): '' | 'warning' | 'exception' | 'success' {
  if (rankMode.value === 'luck') {
    if (row.luckValue >= 500) return 'success'
    if (row.luckValue >= 200) return ''
    return 'warning'
  } else {
    if (row.totalDraws >= 2000) return 'success'
    if (row.totalDraws >= 800) return ''
    return 'warning'
  }
}

function handleRowClick(row: GfGachaRankingListVO) {
  router.push({ path: '/gacha-query', query: { uid: row.userId } })
}

async function loadData() {
  loading.value = true
  try {
    const res = await getRankingListApi()
    if (res.code === 200) {
      rankingData.value = res.data
    }
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style lang="scss" scoped>
.page-container {
  height: 100%;
}

.rank-card {
  border-radius: 12px;
  height: 100%;
  box-sizing: border-box;

  .card-title-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    font-size: 15px;

    .el-icon {
      margin-right: 6px;
      color: #e6a23c;
    }
  }
}

.rank-num {
  font-weight: 800;
  font-size: 18px;
  &.rank-1 { font-size: 22px; }
  &.rank-2 { font-size: 20px; }
  &.rank-3 { font-size: 18px; }
}

.luck-value {
  font-weight: 700;
  color: #e6a23c;
  font-family: 'SF Mono', Consolas, monospace;
}

:deep(.top-rank-row) {
  background-color: #fdf6ec !important;
}

:deep(.el-table__row:hover > td) {
  background-color: #ecf5ff !important;
}

.rank-table {
  :deep(.el-table__body tr) {
    cursor: pointer;
  }
}
</style>
