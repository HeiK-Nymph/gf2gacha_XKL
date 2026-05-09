<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1 class="title">GF2 Gacha Admin</h1>
        <p class="subtitle">少女前线2 抽卡管理系统</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" size="large">
        <el-form-item prop="username">
          <el-input
            ref="inputUsername"
            v-model="form.username"
            placeholder="请输入用户名"
            prefix-icon="User"
            @keyup.enter="focusNext('inputPassword')"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            ref="inputPassword"
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitLock.loading" class="login-btn" @click="handleLogin">
            {{ submitLock.loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-footer">
        <el-link type="primary" :underline="false" @click="router.push('/register')">
          没有账号？立即注册
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
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import useUserStore from '@/stores/user'
import { useAsyncLock } from '@/utils/debounce'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const inputUsername = ref()
const inputPassword = ref()
const submitLock = useAsyncLock()

function focusNext(refKey: string) {
  nextTick(() => {
    const target = refKey === 'inputPassword' ? inputPassword.value : null
    if (target) {
      const inputEl = target.$el?.querySelector('input') as HTMLInputElement | null
      if (inputEl) {
        inputEl.focus()
        // 光标定位到文字末尾
        if (inputEl.value) inputEl.setSelectionRange(inputEl.value.length, inputEl.value.length)
      }
    }
  })
}

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const handleLogin = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) { clearSensitive(); return }

  await submitLock.run(async () => {
    try {
      await mockLogin()
      const redirect = (route.query.redirect as string) || '/'
      router.push(redirect)
      ElMessage.success('登录成功')
    } catch (err) {
      clearSensitive()
    }
  })
}

function clearSensitive() {
  form.password = ''
}

// 调用后端真实登录 API
async function mockLogin() {
  const { loginApi } = await import('@/api')
  const res = await loginApi({
    username: form.username,
    password: form.password,
  })

  if (res.code === 200 && res.data) {
    userStore.setToken(res.data.token)
    userStore.setUserInfo(res.data.user)
  } else {
    // 封禁/账号异常：特殊提示，不清除密码让用户可重试
    const errMsg = res.msg || '登录失败'
    if (errMsg.includes('封禁') || errMsg.includes('异常')) {
      throw new Error(errMsg)
    }
    throw new Error(errMsg)
  }
}
</script>

<style lang="scss" scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0c1426 0%, #1a2332 50%, #0f1923 100%);
  position: relative;
  overflow: hidden;
}

.login-card {
  width: 420px;
  padding: 48px 40px 36px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(20px);
  position: relative;
  z-index: 10;
}

.login-header {
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

.login-btn {
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

.login-footer {
  text-align: center;
  margin-top: 24px;

  p {
    font-size: 12px;
    color: #b0b8c4;
    margin: 0;
  }
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
