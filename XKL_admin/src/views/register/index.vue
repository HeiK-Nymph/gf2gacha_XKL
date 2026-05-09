<template>
  <div class="register-container">
    <div class="register-card">
      <div class="register-header">
        <h1 class="title">创建账号</h1>
        <p class="subtitle">注册 GF2 Gacha Admin 管理系统</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" size="large">
        <el-form-item prop="username" :error="usernameError">
          <el-input
            ref="inputUsername"
            v-model="form.username"
            placeholder="请输入用户名"
            prefix-icon="User"
            @input="onUsernameInput"
            @keyup.enter="focusNext('inputPassword')"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            ref="inputPassword"
            v-model="form.password"
            type="password"
            placeholder="请输入密码（至少4位）"
            prefix-icon="Lock"
            show-password
            @keyup.enter="focusNext('inputInviteCode')"
          />
        </el-form-item>
        <el-form-item prop="inviteCode">
          <el-input
            ref="inputInviteCode"
            v-model="form.inviteCode"
            type="password"
            placeholder="请输入邀请码"
            prefix-icon="Key"
            show-password
            @keyup.enter="handleRegister"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitLock.loading" class="register-btn" @click="handleRegister">
            {{ submitLock.loading ? '注册中...' : '注 册' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="register-footer">
        <el-link type="primary" :underline="false" @click="router.push('/login')">
          已有账号？返回登录
        </el-link>
      </div>
    </div>

    <!-- 装饰背景 -->
    <div class="bg-decoration">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
      <div class="circle circle-3"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { registerApi } from '@/api'
import { useAsyncLock } from '@/utils/debounce'

const router = useRouter()

const formRef = ref<FormInstance>()
const inputUsername = ref()
const inputPassword = ref()
const inputInviteCode = ref()
const submitLock = useAsyncLock()

const form = reactive({
  username: '',
  password: '',
  inviteCode: '',
})

const usernameError = ref('')

function focusNext(refKey: string) {
  nextTick(() => {
    const targetMap: Record<string, any> = { inputPassword: inputPassword.value, inputInviteCode: inputInviteCode.value }
    const target = targetMap[refKey]
    if (target) {
      const inputEl = target.$el?.querySelector('input') as HTMLInputElement | null
      if (inputEl) {
        inputEl.focus()
        if (inputEl.value) inputEl.setSelectionRange(inputEl.value.length, inputEl.value.length)
      }
    }
  })
}

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名长度为2-20个字符', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_]+$/, message: '用户名仅支持字母、数字、下划线', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 4, max: 32, message: '密码长度为4-32个字符', trigger: 'blur' },
  ],
  inviteCode: [
    { required: true, message: '请输入邀请码', trigger: 'blur' },
  ],
}

const handleRegister = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) { clearSensitive(); return }

  await submitLock.run(async () => {
    try {
      const res = await registerApi({
        username: form.username,
        password: form.password,
        inviteCode: form.inviteCode,
      })
      if (res.code === 200) {
        ElMessage.success('注册成功，请登录')
        router.push('/login')
      } else {
        clearSensitive()
      }
    } catch (e: any) {
      // 用户名重复：在对应字段位置展示错误，不清空其他表单数据
      if (e?.message?.includes('已被注册')) {
        usernameError.value = e.message || '该用户名已被注册'
      } else {
        clearSensitive()
      }
    }
  })
}

function clearSensitive() {
  form.password = ''
  form.inviteCode = ''
}

function onUsernameInput() {
  usernameError.value = ''
}
</script>

<style lang="scss" scoped>
.register-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0c1426 0%, #1a2332 50%, #0f1923 100%);
  position: relative;
  overflow: hidden;
}

.register-card {
  width: 420px;
  padding: 48px 40px 36px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(20px);
  position: relative;
  z-index: 10;
}

.register-header {
  text-align: center;
  margin-bottom: 36px;

  .title {
    font-size: 28px;
    font-weight: 800;
    color: #1a2332;
    letter-spacing: 2px;
    margin: 0 0 8px;
  }

  .subtitle {
    font-size: 14px;
    color: #8c9bab;
    margin: 0;
  }
}

.register-btn {
  width: 100%;
  height: 46px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 8px;
  letter-spacing: 4px;
  background: linear-gradient(135deg, #409eff 0%, #337ecc 100%);
  border: none;
  transition: all 0.3s;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(64, 158, 255, 0.35);
  }
}

.register-footer {
  text-align: center;
  margin-top: 24px;
}

.bg-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;

  .circle {
    position: absolute;
    border-radius: 50%;
    opacity: 0.06;
    background: #409eff;
  }

  .circle-1 {
    width: 600px;
    height: 600px;
    right: -200px;
    top: -200px;
  }

  .circle-2 {
    width: 400px;
    height: 400px;
    left: -100px;
    bottom: -150px;
  }

  .circle-3 {
    width: 200px;
    height: 200px;
    left: 30%;
    top: 15%;
  }
}

:deep(.el-input__wrapper) {
  border-radius: 8px;
  box-shadow: 0 0 0 1px #dcdfe6 inset;
  transition: box-shadow 0.3s;

  &:hover {
    box-shadow: 0 0 0 1px #a0cfff inset;
  }

  &.is-focus {
    box-shadow: 0 0 0 1px #409eff inset;
  }
}
</style>
