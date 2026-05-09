<template>
  <div class="page-container">
    <!-- 搜索/操作栏 -->
    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar">
        <el-space>
          <el-input
            v-model="searchText"
            placeholder="搜索道具名称/ID"
            clearable
            style="width: 220px"
            :prefix-icon="Search"
          />
          <el-button type="primary" @click="loadData"><el-icon><Refresh /></el-icon>刷新</el-button>
        </el-space>
        <el-space>
          <!-- 正常列表 Tab 下显示的操作按钮 -->
          <template v-if="activeTab === 'normal'">
            <el-button type="success" @click="showAddDialog"><el-icon><Plus /></el-icon>批量添加</el-button>
          </template>
          <!-- 回收站 Tab 下显示的操作按钮 -->
          <template v-else>
            <el-popconfirm title="确认恢复所有已删除的物品？" @confirm="handleRestoreAll">
              <template #reference>
                <el-button type="warning" plain :loading="restoring"><el-icon><RefreshRight /></el-icon>恢复全部</el-button>
              </template>
            </el-popconfirm>
            <el-popconfirm title="此操作不可逆，确认物理删除所有已标记删除的物品？" @confirm="handleHardDelete" confirm-button-text="确认删除" cancel-button-text="取消" confirm-button-type="danger">
              <template #reference>
                <el-button type="danger" plain :loading="hardDeleting"><el-icon><Delete /></el-icon>彻底清理</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-space>
      </div>

      <!-- Tab 切换 -->
      <div class="tab-bar" style="margin-top: 12px">
        <el-radio-group v-model="activeTab" size="default" @change="handleTabChange">
          <el-radio-button value="normal">正常列表</el-radio-button>
          <el-radio-button value="trash">回收站</el-radio-button>
        </el-radio-group>
        <span v-if="activeTab === 'trash' && trashCount >= 0" class="trash-count">{{ trashCount }} 条已删除</span>
      </div>
    </el-card>

    <!-- 数据表格 - 正常列表 -->
    <el-card v-if="activeTab === 'normal'" shadow="never" class="table-card">
      <el-table :data="filteredList" v-loading="loading" stripe size="default" max-height="calc(100vh - 360px)">
        <el-table-column prop="itemId" label="道具ID" width="90" sortable />
        <el-table-column prop="itemName" label="名称" min-width="160" />
        <el-table-column label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.itemType === 10 ? '' : 'warning'" size="small">
              {{ row.itemType === 10 ? '人形' : '武器' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="SSR类型" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="ssrTypeTagMap[row.ssrType] || 'info'" effect="dark" size="small">
              {{ ssrTypeNameMap[row.ssrType] || '未知' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="180" />
        <el-table-column label="操作" width="120" align="center" fixed="right">
          <template #default="{ row }">
            <el-popconfirm :title="'确认删除「' + row.itemName + '」？'" @confirm="handleRemove(row.itemId)">
              <template #reference>
                <el-button type="danger" link size="small" :loading="removingIds.has(row.itemId)">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="暂无 SSR 物品数据" :image-size="80" />
        </template>
      </el-table>
    </el-card>

    <!-- 数据表格 - 回收站 -->
    <el-card v-else shadow="never" class="table-card">
      <el-table :data="filteredTrashList" v-loading="loading" stripe size="default" max-height="calc(100vh - 360px)">
        <el-table-column prop="itemId" label="道具ID" width="90" sortable />
        <el-table-column prop="itemName" label="名称" min-width="160" />
        <el-table-column label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.itemType === 10 ? '' : 'warning'" size="small">
              {{ row.itemType === 10 ? '人形' : '武器' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="SSR类型" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="ssrTypeTagMap[row.ssrType] || 'info'" effect="dark" size="small">
              {{ ssrTypeNameMap[row.ssrType] || '未知' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updatedAt" label="删除时间" width="180" />
        <el-table-column label="操作" width="120" align="center" fixed="right">
          <template #default="{ row }">
            <el-popconfirm :title="'确认恢复「' + row.itemName + '」？'" @confirm="handleRestoreOne(row.itemId)">
              <template #reference>
                <el-button type="warning" link size="small" :loading="restoringIds.has(row.itemId)">恢复</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="回收站为空" :image-size="80" />
        </template>
      </el-table>
    </el-card>

    <!-- 批量添加弹窗 -->
    <el-dialog v-model="addDialogVisible" title="批量添加 SSR 物品" width="600px" destroy-on-close>
      <el-alert type="info" :closable="false" style="margin-bottom: 16px">
        <p>每行一个物品，格式：<code>道具ID,名称,类型(10=人形/20=武器),SSR类型(1=限定角色/2=限定武器/3=常驻)</code></p>
      </el-alert>
      <el-input
        v-model="batchInput"
        type="textarea"
        :rows="10"
        placeholder="示例：&#10;101,薇拉,10,1&#10;201,战术匕首,20,2&#10;102,蒂娜,10,1"
      />
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleBatchInsert" :loading="submitting">确认添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh, Plus, RefreshRight, Delete } from '@element-plus/icons-vue'
import {
  getSsrItemAllApi, insertSsrItemBatchApi,
  removeSsrItemByItemIdApi, restoreAllSsrItemsApi,
  getDeletedSsrItemsApi, restoreSsrItemByItemIdApi,
  deleteSsrItemsByIsDeletedApi
} from '@/api'
import type { GfSsrItem, GfSsrItemDTO } from '@/types'

const ssrTypeTagMap: Record<number, string> = { 1: '', 2: 'warning', 3: 'info' }
const ssrTypeNameMap: Record<number, string> = { 1: '限定角色', 2: '限定武器', 3: '常驻' }

const loading = ref(false)
const submitting = ref(false)
const searchText = ref('')
const tableData = ref<GfSsrItem[]>([])
const trashData = ref<GfSsrItem[]>([])
const addDialogVisible = ref(false)
const batchInput = ref('')
const activeTab = ref<'normal' | 'trash'>('normal')

// 正常列表筛选
const filteredList = computed(() => {
  if (!searchText.value) return tableData.value
  const kw = searchText.value.toLowerCase()
  return tableData.value.filter(
    (item) =>
      String(item.itemId).includes(kw) ||
      item.itemName.toLowerCase().includes(kw),
  )
})

// 回收站列表筛选
const filteredTrashList = computed(() => {
  if (!searchText.value) return trashData.value
  const kw = searchText.value.toLowerCase()
  return trashData.value.filter(
    (item) =>
      String(item.itemId).includes(kw) ||
      item.itemName.toLowerCase().includes(kw),
  )
})

// 回收站数量
const trashCount = computed(() => trashData.value.length)

function handleTabChange(val: string) {
  searchText.value = ''
  if (val === 'normal') {
    loadData()
  } else {
    loadTrashData()
  }
}

async function loadData() {
  loading.value = true
  try {
    const res = await getSsrItemAllApi()
    if (res.code === 200) {
      tableData.value = res.data || []
    }
  } finally {
    loading.value = false
  }
}

async function loadTrashData() {
  loading.value = true
  try {
    const res = await getDeletedSsrItemsApi()
    if (res.code === 200) {
      trashData.value = res.data || []
    }
  } finally {
    loading.value = false
  }
}

function showAddDialog() {
  batchInput.value = ''
  addDialogVisible.value = true
}

async function handleBatchInsert() {
  if (!batchInput.value.trim()) {
    ElMessage.warning('请输入物品数据')
    return
  }

  const lines = batchInput.value.trim().split('\n').map((l) => l.trim()).filter(Boolean)
  const items: GfSsrItemDTO[] = []

  for (const line of lines) {
    const parts = line.split(',').map((s) => s.trim())
    if (parts.length >= 4) {
      items.push({
        itemId: Number(parts[0]) || 0,
        itemName: parts[1],
        itemType: Number(parts[2]) || 10,
        ssrType: Number(parts[3]) || 3,
      })
    }
  }

  if (!items.length) {
    ElMessage.error('格式错误，请检查输入')
    return
  }

  submitting.value = true
  try {
    const res = await insertSsrItemBatchApi({ GfSsrItemList: items })
    if (res.code === 200) {
      ElMessage.success('添加成功')
      addDialogVisible.value = false
      loadData()
    }
  } finally {
    submitting.value = false
  }
}

const removingIds = ref<Set<number>>(new Set())
const restoringIds = ref<Set<number>>(new Set())
const restoring = ref(false)
const hardDeleting = ref(false)

async function handleRemove(itemId: number) {
  removingIds.value.add(itemId)
  try {
    const res = await removeSsrItemByItemIdApi(itemId)
    if (res.code === 200) {
      ElMessage.success('已删除')
      loadData()
    }
  } finally {
    removingIds.value.delete(itemId)
  }
}

/** 回收站：单条恢复 */
async function handleRestoreOne(itemId: number) {
  restoringIds.value.add(itemId)
  try {
    const res = await restoreSsrItemByItemIdApi(itemId)
    if (res.code === 200) {
      ElMessage.success('已恢复')
      loadTrashData()
    }
  } finally {
    restoringIds.value.delete(itemId)
  }
}

async function handleRestoreAll() {
  restoring.value = true
  try {
    const res = await restoreAllSsrItemsApi()
    if (res.code === 200) {
      ElMessage.success('已恢复所有已删除物品')
      loadData()
    }
  } finally {
    restoring.value = false
  }
}

async function handleHardDelete() {
  hardDeleting.value = true
  try {
    const res = await deleteSsrItemsByIsDeletedApi()
    if (res.code === 200) {
      ElMessage.success('清理完成')
      loadData()
    }
  } finally {
    hardDeleting.value = false
  }
}

onMounted(loadData)
</script>

<style lang="scss" scoped>
.page-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar-card, .table-card {
  border-radius: 12px;

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
  }
}

.tab-bar {
  display: flex;
  align-items: center;
  gap: 16px;

  .trash-count {
    font-size: 13px;
    color: #909399;
  }
}

// SSR类型限定角色 tag 蓝色主题（穿透 el-table 单元格 + el-tag scoped 边界）
:deep(.el-tag--dark.el-tag--info) {
  --el-tag-bg-color: #409eff !important;
  --el-tag-border-color: #409eff !important;
  --el-tag-text-color: #fff !important;
}
</style>
