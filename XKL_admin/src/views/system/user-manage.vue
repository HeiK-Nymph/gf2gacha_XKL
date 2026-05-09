<template>
  <div class="page-container">
    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar">
        <el-input
          v-model="searchText"
          placeholder="搜索用户名"
          clearable
          style="width: 240px"
          :prefix-icon="Search"
        />
        <el-button type="primary" @click="loadData"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </el-card>

    <el-card shadow="never" class="table-card">
      <el-table :data="filteredUsers" v-loading="loading" stripe size="default">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column label="角色" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.role === 1 ? 'danger' : 'info'" effect="dark" size="small">
              {{ row.role === 1 ? '管理员' : '普通用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === '1' ? 'success' : 'danger'" size="small">
              {{ row.status === '1' ? '正常' : '封禁' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="lastLoginTime" label="最后登录" min-width="170">
          <template #default="{ row }">
            {{ row.lastLoginTime ? formatTime(row.lastLoginTime) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="注册时间" width="170" />
        <el-table-column label="操作" width="260" align="center" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.username !== currentUsername"
              :type="row.role === 1 ? 'warning' : 'primary'"
              size="small"
              link
              :loading="row._loading"
              @click="toggleRole(row)"
            >
              {{ row.role === 1 ? '降为普通' : '设为管理员' }}
            </el-button>
            <el-button
              v-if="row.username !== currentUsername"
              :type="row.status === '1' ? 'danger' : 'success'"
              size="small"
              link
              :loading="row._loading"
              @click="toggleStatus(row)"
            >
              {{ row.status === '1' ? '封禁' : '解封' }}
            </el-button>
            <el-tag v-else type="success" size="small">当前账号</el-tag>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="暂无用户数据" :image-size="80" />
        </template>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import useUserStore from '@/stores/user'
import { getSysUserListApi, updateSysUserRoleApi, updateSysUserStatusApi } from '@/api'
import type { SysUser } from '@/types'

const userStore = useUserStore()
const currentUsername = userStore.userInfo?.username || ''

const loading = ref(false)
const searchText = ref('')
const users = ref<SysUser[]>([])

const filteredUsers = computed(() => {
  if (!searchText.value) return users.value
  return users.value.filter((u) => u.username.includes(searchText.value))
})

function formatTime(t: string): string {
  return t ? new Date(t).toLocaleString('zh-CN') : '-'
}

async function loadData() {
  loading.value = true
  try {
    const res = await getSysUserListApi()
    if (res.code === 200) {
      users.value = (res.data || []).map((u: any) => ({
        ...u,
        _loading: false,
      }))
    }
  } finally {
    loading.value = false
  }
}

async function toggleRole(user: SysUser) {
  const newRole = user.role === 1 ? 0 : 1
  const action = newRole === 1 ? '提升为管理员' : '降为普通用户'

  try {
    await ElMessageBox.confirm(`确定将「${user.username}」${action}？`, '权限变更', {
      type: 'warning',
    })
    user._loading = true
    const res = await updateSysUserRoleApi(user.username, newRole)
    if (res.code === 200) {
      ElMessage.success(`已${action}`)
      user.role = newRole
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      // 错误提示已在 request.ts 响应拦截器中统一处理
      console.warn('权限变更失败:', e)
    }
  } finally {
    user._loading = false
  }
}

async function toggleStatus(user: SysUser) {
  const newStatus = user.status === '1' ? '0' : '1'
  const action = newStatus === '0' ? '封禁' : '解封'

  try {
    await ElMessageBox.confirm(`确定${action}用户「${user.username}」？`, '状态变更', {
      type: 'warning',
    })
    user._loading = true
    const res = await updateSysUserStatusApi(user.username, newStatus)
    if (res.code === 200) {
      ElMessage.success(`已${action}`)
      user.status = newStatus
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      // 错误提示已在 request.ts 响应拦截器中统一处理
      console.warn('状态变更失败:', e)
    }
  } finally {
    user._loading = false
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
  }
}
</style>
