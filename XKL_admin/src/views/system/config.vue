<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="config-card">
          <template #header>
            <span class="card-title">系统配置</span>
          </template>

          <el-form :model="configForm" label-width="140px" size="default" class="config-form">
            <el-divider content-position="left">基础设置</el-divider>
            <el-form-item label="系统名称">
              <el-input v-model="configForm.systemName" placeholder="系统显示名称" />
            </el-form-item>
            <el-form-item label="API 地址">
              <el-input v-model="apiBaseUrl" disabled>
                <template #append>
                  <el-button @click="copyToClipboard(apiBaseUrl)">复制</el-button>
                </template>
              </el-input>
            </el-form-item>

            <el-divider content-position="left">安全设置</el-divider>
            <el-form-item label="Token 有效期(小时)">
              <el-input-number v-model="configForm.tokenExpireHours" :min="1" :max="720" />
            </el-form-item>
            <el-form-item label="允许注册">
              <el-switch v-model="configForm.allowRegister" active-text="开启" inactive-text="关闭" />
            </el-form-item>

            <el-divider content-position="left">抽卡设置</el-divider>
            <el-form-item label="排行榜 Top N">
              <el-input-number v-model="configForm.rankingTopN" :min="10" :max="5000" :step="10" />
            </el-form-item>
            <el-form-item label="欧皇值算法版本">
              <el-select v-model="configForm.luckAlgorithmVersion" style="width: 200px">
                <el-option label="v1.0 标准版" value="v1" />
                <el-option label="v2.0 严格版" value="v2" />
              </el-select>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="handleSave" :loading="saving">保存配置</el-button>
              <el-button @click="resetConfig">重置默认</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="info-card">
          <template #header>
            <span class="card-title">运行环境信息</span>
          </template>
          <div class="env-list">
            <div class="env-item" v-for="(item, i) in envInfo" :key="i">
              <span class="env-label">{{ item.label }}</span>
              <span class="env-value">{{ item.value }}</span>
            </div>
          </div>
        </el-card>

        <el-card shadow="never" class="info-card" style="margin-top: 16px;">
          <template #header>
            <span class="card-title">数据库表概览</span>
          </template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="sys_user">系统用户 / 管理员</el-descriptions-item>
            <el-descriptions-item label="gf_user">游戏玩家 UID 映射</el-descriptions-item>
            <el-descriptions-item label="gf_gacha_history">抽卡原始 JSON 记录</el-descriptions-item>
            <el-descriptions-item label="gf_gacha_ssr_record">SSR 明细记录</el-descriptions-item>
            <el-descriptions-item label="gf_ssr_item">SSR 物品字典</el-descriptions-item>
            <el-descriptions-item label="gf_gacha_ranking_list">排行榜数据</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

const saving = ref(false)
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'

const configForm = reactive({
  systemName: 'GF2 Gacha Admin',
  tokenExpireHours: 24,
  allowRegister: false,
  rankingTopN: 1000,
  luckAlgorithmVersion: 'v1',
})

const envInfo = [
  { label: '前端框架', value: 'Vue 3.5 + Vite 8' },
  { label: 'UI 组件库', value: 'Element Plus' },
  { label: '后端框架', value: 'Spring Boot 4.x' },
  { label: '数据库', value: 'MySQL (gf2gacha_xkl)' },
  { label: 'ORM 框架', value: 'MyBatis + PageHelper' },
  { label: 'HTTP 客户端', value: 'WebClient (异步)' },
]

function handleSave() {
  saving.value = true
  setTimeout(() => {
    saving.value = false
    ElMessage.success('配置已保存（当前为本地演示模式）')
  }, 800)
}

function resetConfig() {
  Object.assign(configForm, {
    systemName: 'GF2 Gacha Admin',
    tokenExpireHours: 24,
    allowRegister: false,
    rankingTopN: 1000,
    luckAlgorithmVersion: 'v1',
  })
  ElMessage.info('已重置为默认值')
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).then(() => ElMessage.success('已复制'))
}
</script>

<style lang="scss" scoped>
.page-container {
  height: 100%;
  overflow-y: auto;
}

.config-card, .info-card {
  border-radius: 12px;

  .card-title {
    font-weight: 600;
    font-size: 15px;
  }
}

.config-form {
  max-width: 560px;
  padding-right: 16px;
}

.env-list {
  .env-item {
    display: flex;
    justify-content: space-between;
    padding: 11px 0;
    border-bottom: 1px solid #fafafa;

    &:last-child { border-bottom: none; }

    .env-label {
      color: #909399;
      font-size: 13px;
    }

    .env-value {
      color: #303133;
      font-size: 13px;
      font-weight: 500;
      font-family: 'SF Mono', Consolas, monospace;
    }
  }
}
</style>
