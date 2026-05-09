<template>
  <div class="page-container">
    <el-card shadow="never" class="search-card">
      <el-form :model="queryForm" inline size="default">
        <el-form-item label="玩家 UID">
          <el-input
            v-model.number="queryForm.uid"
            placeholder="输入游戏 UID"
            clearable
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleQuery" :loading="loading">
            <el-icon><Search /></el-icon>查询
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 查询结果 -->
    <el-card shadow="never" v-if="gachaData" class="result-card">
      <template #header>
        <div class="card-title-row">
          <span>UID {{ gachaData.uid }} 抽卡详情</span>
          <el-tag type="success">共 {{ gachaData.totalDraws }} 抽 / {{ gachaData.totalSSR }} SSR</el-tag>
        </div>
      </template>

      <!-- 概览指标 -->
      <el-row :gutter="16" class="summary-row">
        <el-col :xs="12" :sm="6" v-for="item in summaryItems" :key="item.label">
          <div class="summary-item">
            <div class="summary-value" :style="{ color: item.color }">{{ gachaData[item.key] }}</div>
            <div class="summary-label">{{ item.label }}</div>
          </div>
        </el-col>
      </el-row>

      <!-- 各池子详情 -->
      <el-tabs v-model="activePoolTab" type="border-card" class="pool-tabs">
        <el-tab-pane
          v-for="pool in gachaData.gachaRecordsList"
          :key="pool.poolType"
          :label="getPoolName(pool.poolType)"
          :name="String(pool.poolType)"
        >
          <div class="pool-summary">
            <el-space wrap>
              <el-statistic title="总抽数" :value="pool.totalDraws" />
              <el-statistic title="SSR 数" :value="pool.totalSSR" />
              <el-statistic title="歪了次数" :value="pool.waiCnt" />
              <el-rate
                disabled
                :model-value="pool.totalDraws > 0 ? Math.max(1, 5 - Math.floor(pool.totalDraws / pool.totalSSR / 20)) : 5"
                show-score
                text-color="#ff9900"
              />
            </el-space>
          </div>

          <el-table :data="pool.gachaItems" stripe size="small" max-height="400">
            <el-table-column prop="drawOrder" label="#" width="55" />
            <el-table-column prop="itemId" label="道具ID" width="80" />
            <el-table-column prop="itemName" label="名称" min-width="150">
              <template #default="{ row }">
                <el-tag :type="row.itemName === 'question' ? 'info' : ''" size="small">
                  {{ row.itemName === 'question' ? '未知五星' : row.itemName }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="100">
              <template #default="{ row }">
                <el-tag :type="getItemTypeTag(row.itemType)" size="small">
                  {{ getItemTypeName(row.itemType) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="SSR类型" width="110">
              <template #default="{ row }">
                <el-tag :type="getSsrTypeTag(row.ssrType)" size="small" effect="dark">
                  {{ getSsrTypeName(row.ssrType) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="costDraws" label="花费抽数" width="90" />
            <el-table-column label="是否歪了" width="85">
              <template #default="{ row }">
                <el-tag :type="row.isWai ? 'danger' : 'success'" size="small">
                  {{ row.isWai ? '歪了' : '没歪' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 空状态提示 -->
    <el-empty v-else-if="!loading && searched" description="暂无数据，请输入正确的 UID 进行查询" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { getGfUserByUidApi } from '@/api'
import type { GfUserDTO } from '@/types'

type GfUserSummaryKey = 'totalDraws' | 'totalSSR' | 'safeRate' | 'waiCnt'

const summaryItems: { key: GfUserSummaryKey; label: string; color: string }[] = [
  { key: 'totalDraws', label: '总抽数', color: '#409eff' },
  { key: 'totalSSR', label: '总SSR', color: '#67c23a' },
  { key: 'safeRate', label: '保底率%', color: '#e6a23c' },
  { key: 'waiCnt', label: '歪的次数', color: '#f56c6c' },
]

const loading = ref(false)
const searched = ref(false)
const gachaData = ref<GfUserDTO | null>(null)
const activePoolTab = ref('3')
const route = useRoute()

const queryForm = reactive({
  uid: undefined as number | undefined,
})

function getPoolName(poolType: number): string {
  const map: Record<number, string> = {
    1: '常驻池',
    3: '角色池',
    4: '武器池',
    6: '自选角色池',
    7: '自选武器池',
  }
  return map[poolType] || `未知(${poolType})`
}

function getItemTypeName(type: number): string {
  return { 0: '垫抽', 10: '人形', 20: '武器' }[type] || '未知'
}
function getItemTypeTag(type: number): string {
  return { 10: '', 20: 'warning', 0: 'info' }[type] || ''
}
function getSsrTypeName(type: number): string {
  return { 0: '-', 1: '限定角色', 2: '限定武器', 3: '常驻' }[type] || '-'
}
function getSsrTypeTag(type: number): string {
  return { 1: '', 2: 'warning', 3: 'info', 0: 'info' }[type] || ''
}

async function handleQuery() {
  if (!queryForm.uid) {
    ElMessage.warning('请输入 UID')
    return
  }
  loading.value = true
  searched.value = true

  try {
    const res = await getGfUserByUidApi(queryForm.uid!)
    if (res.code === 200) {
      gachaData.value = res.data
      if (res.data?.gachaRecordsList?.length) {
        activePoolTab.value = String(res.data.gachaRecordsList[0].poolType)
      }
    } else {
      // 错误提示已在 request.ts 响应拦截器中统一处理
      gachaData.value = null
    }
  } catch {
    gachaData.value = null
    // 错误提示已在 request.ts 响应拦截器中统一处理
  } finally {
    loading.value = false
  }
}

function handleReset() {
  queryForm.uid = undefined
  gachaData.value = null
  searched.value = false
}

// 页面加载时，若URL携带uid参数则自动查询
onMounted(() => {
  const uidParam = route.query.uid
  if (uidParam) {
    queryForm.uid = Number(uidParam)
    if (queryForm.uid) {
      handleQuery()
    }
  }
})
</script>

<style lang="scss" scoped>
.page-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.search-card {
  border-radius: 12px;
}

.result-card {
  border-radius: 12px;

  .card-title-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    font-size: 15px;
  }
}

.summary-row {
  margin-bottom: 20px;
}

.summary-item {
  text-align: center;
  padding: 12px 0;
  background: #fafbfc;
  border-radius: 10px;

  .summary-value {
    font-size: 26px;
    font-weight: 800;
  }

  .summary-label {
    font-size: 12px;
    color: #909399;
    margin-top: 4px;
  }
}

.pool-tabs {
  border-radius: 10px;
  overflow: hidden;
}

.pool-summary {
  margin-bottom: 16px;
  padding: 16px;
  background: #f7f9fc;
  border-radius: 8px;
}
</style>
