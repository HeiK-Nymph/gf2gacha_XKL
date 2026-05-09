<template>
  <div class="dashboard">
    <!-- 统计卡片（仅管理员可见） -->
    <el-row :gutter="16" class="stat-cards" v-if="statCards.length > 0">
      <el-col :xs="24" :sm="12" :lg="6" v-for="(card, index) in statCards" :key="index">
        <el-card shadow="hover" class="stat-card" :body-style="{ padding: '20px' }">
          <div class="stat-content">
            <div class="stat-info">
              <p class="stat-label">{{ card.label }}</p>
              <template v-if="card.loading">
                <el-skeleton animated :rows="0" class="stat-skeleton">
                  <template #template>
                    <el-skeleton-item variant="h1" style="width: 60px; height: 36px" />
                  </template>
                </el-skeleton>
              </template>
              <h3 v-else class="stat-value">{{ card.value }}</h3>
            </div>
            <el-icon :size="48" :color="card.color" class="stat-icon-bg">
              <component :is="card.icon" />
            </el-icon>
          </div>
          <div class="stat-footer">
            <span>{{ card.desc }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表/快捷入口区 -->
    <el-row :gutter="16" class="content-row">
      <el-col :xs="24" :lg="16">
        <el-card shadow="never" class="content-card">
          <template #header>
            <div class="card-header">
              <span>快捷操作</span>
            </div>
          </template>
          <div class="quick-actions">
            <div
              v-for="action in quickActions"
              :key="action.path"
              class="action-item"
              @click="$router.push(action.path)"
            >
              <el-icon :size="28" :color="action.color"><component :is="action.icon" /></el-icon>
              <span>{{ action.title }}</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="content-card">
          <template #header>
            <div class="card-header">
              <span>系统信息</span>
            </div>
          </template>
          <div class="sys-info">
            <div class="info-row" v-for="(item, i) in sysInfo" :key="i">
              <span class="info-label">{{ item.label }}</span>
              <span class="info-value">{{ item.value }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import useUserStore from '@/stores/user'
import {
  User, Box, TrendCharts, Trophy,
  Search, Setting, DocumentCopy
} from '@element-plus/icons-vue'
import type { Result } from '@/types'
import { getUserCountApi, getSsrItemCountApi, getActiveUserCountApi } from '@/api'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.userInfo?.role === 1)

// ========== 加载状态 ==========
const loading = reactive({
  userCount: false,
  ssrItemCount: false,
  rankingCount: false,
})

// ========== 统计卡片数据（响应式）==========
const statData = reactive({
  userCount: '--',
  ssrItemCount: '--',
  rankingCount: '--',
})

// 全部统计卡片（管理员可见）— 使用 computed 确保数据变化时自动更新
const allStatCards = computed(() => [
  { label: '注册用户', value: statData.userCount, icon: 'User', color: '#409eff', desc: '系统用户总数', roles: [1], loading: loading.userCount },
  { label: 'SSR 物品', value: statData.ssrItemCount, icon: 'Box', color: '#67c23a', desc: '物品字典数量', roles: [1], loading: loading.ssrItemCount },
  { label: '排行榜记录', value: statData.rankingCount, icon: 'TrendCharts', color: '#e6a23c', desc: '活跃抽卡用户', roles: [1], loading: loading.rankingCount },
  { label: '今日访问', value: '--', icon: 'Trophy', color: '#f56c6c', desc: '页面访问统计', roles: [1], loading: false },
])

const statCards = computed(() => {
  const role = userStore.userInfo?.role ?? 0
  return allStatCards.value.filter((card) => (card.roles || []).includes(role))
})

const allQuickActions = [
  { title: '抽卡查询', path: '/gacha-query', icon: 'Search', color: '#409eff', roles: [0, 1] },
  { title: '排行榜', path: '/ranking', icon: 'Trophy', color: '#e6a23c', roles: [0, 1] },
  { title: 'SSR物品管理', path: '/ssr-item', icon: 'Box', color: '#67c23a', roles: [1] },
  { title: '用户管理', path: '/user-manage', icon: 'UserFilled', color: '#909399', roles: [1] },
  { title: '系统设置', path: '/system-config', icon: 'Setting', color: '#b37feb', roles: [1] },
  { title: '操作指南', path: '/guide', icon: 'DocumentCopy', color: '#13c2c2', roles: [0, 1] },
]

const quickActions = computed(() => {
  const role = userStore.userInfo?.role ?? 0
  return allQuickActions.filter((a) => (a.roles || []).includes(role))
})

const sysInfo = computed(() => {
  const base = [
    { label: '当前版本', value: 'v1.0.0' },
    { label: '框架', value: 'Vue 3 + Element Plus' },
  ]
  if (isAdmin.value) {
    base.unshift({ label: '后端地址', value: import.meta.env.VITE_API_BASE_URL || '/api' })
    base.push({ label: '数据库', value: 'MySQL (gf2gacha_xkl)' })
  }
  return base
})

// ========== 异步加载统计数据（通用方法）==========
async function fetchStat<T>(
  key: keyof typeof loading,
  dataKey: keyof typeof statData,
  apiCall: () => Promise<Result<T>>,
): Promise<void> {
  loading[key] = true
  try {
    const res = await apiCall()
    if (res.code === 200 && res.data != null) {
      ;(statData as any)[dataKey] = String(res.data)
    } else {
      const cardLabel = allStatCards.value.find(c => c.loading === loading[key])?.label ?? key
      ElMessage.warning(`${cardLabel} 数据获取异常`)
    }
  } catch (e: any) {
    console.error(`[Dashboard] ${key} 请求失败:`, e)
    const cardLabel = allStatCards.value.find(c => c.loading === loading[key])?.label ?? key
    ElMessage.error(`${cardLabel} 数据加载失败，请检查网络连接`)
  } finally {
    loading[key] = false
  }
}

onMounted(async () => {
  if (!isAdmin.value) return

  // 并行请求三个统计接口，互不依赖
  await Promise.allSettled([
    fetchStat('userCount', 'userCount', getUserCountApi),
    fetchStat('ssrItemCount', 'ssrItemCount', getSsrItemCountApi),
    fetchStat('rankingCount', 'rankingCount', getActiveUserCountApi),
  ])
})
</script>

<style lang="scss" scoped>
.dashboard {
  padding: 0;
}

.stat-cards {
  margin-bottom: 16px;
}

.stat-card {
  border-radius: 12px;
  transition: transform 0.3s, box-shadow 0.3s;

  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  }

  .stat-content {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }

  .stat-label {
    font-size: 14px;
    color: #909399;
    margin: 0 0 8px;
  }

  .stat-value {
    font-size: 32px;
    font-weight: 800;
    color: #1a2332;
    margin: 0;
  }

  .stat-skeleton {
    padding: 0;

    .el-skeleton__item {
      margin: 0 !important;
    }
  }

  .stat-icon-bg {
    opacity: 0.15;
  }

  .stat-footer {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid #f0f0f0;

    span {
      font-size: 12px;
      color: #b0b8c4;
    }
  }
}

.content-row {
  margin-bottom: 16px;
}

.content-card {
  border-radius: 12px;
  height: 100%;

  .card-header {
    font-weight: 600;
    font-size: 15px;
    color: #303133;
  }
}

.quick-actions {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 16px;

  .action-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 20px 12px;
    border-radius: 10px;
    background: #f7f9fc;
    cursor: pointer;
    transition: all 0.3s;

    &:hover {
      background: #ecf5ff;
      transform: translateY(-2px);

      span {
        color: #409eff;
      }
    }

    span {
      font-size: 13px;
      color: #606266;
      font-weight: 500;
      transition: color 0.3s;
    }
  }
}

.sys-info {
  .info-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 0;
    border-bottom: 1px solid #fafafa;

    &:last-child {
      border-bottom: none;
    }

    .info-label {
      font-size: 13px;
      color: #909399;
    }

    .info-value {
      font-size: 13px;
      color: #303133;
      font-weight: 500;
      font-family: 'SF Mono', 'Consolas', monospace;
    }
  }
}
</style>
