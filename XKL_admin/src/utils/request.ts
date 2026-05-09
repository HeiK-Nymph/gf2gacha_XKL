import type { Result } from '@/types'
import axios from 'axios'
import type { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import router from '@/router'
import useUserStore from '@/stores/user'

const service: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15000,
})

// 不需要 Token 的白名单接口
const whiteList = ['/sys-auth/login', '/sys-auth/register']

// 请求拦截器
service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const userStore = useUserStore()
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse<Result>) => {
    const res = response.data

    if (res.code !== 200) {
      // 权限不足 -> 403（含封禁/越权等）
      if (res.code === 403) {
        ElMessage.error(res.msg || '权限不足')
        // 如果是封禁类提示，强制退出登录
        if (res.msg && (res.msg.includes('封禁') || res.msg.includes('异常'))) {
          setTimeout(() => {
            const userStore = useUserStore()
            userStore.logout()
            router.push('/login')
          }, 1500)
        }
        return Promise.reject(new Error(res.msg || 'Forbidden'))
      }

      ElMessage.error(res.msg || '请求失败')

      // Token 过期或无效 -> 401
      if (res.code === 401) {
        ElMessageBox.confirm('登录已过期，请重新登录', '提示', {
          confirmButtonText: '重新登录',
          cancelButtonText: '取消',
          type: 'warning',
        }).then(() => {
          const userStore = useUserStore()
          userStore.logout()
          router.push('/login')
        })
      }

      return Promise.reject(new Error(res.msg || 'Error'))
    }
    return response
  },
  (error) => {
    const msg = error.response?.data?.msg || error.message || '网络异常'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default service
