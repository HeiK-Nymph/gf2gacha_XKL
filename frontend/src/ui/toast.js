import { reactive } from 'vue'

// 轻量全局 toast（替代 ElMessage）：任何组件 import 后直接调用。
// loading() 返回关闭函数，用于替代 ElMessage({ duration: 0 }) 的常驻提示。
const state = reactive({ items: [], seq: 0 })

const dismiss = (id) => {
  const index = state.items.findIndex((item) => item.id === id)
  if (index >= 0) state.items.splice(index, 1)
}

const push = (type, message, duration) => {
  const id = ++state.seq
  state.items.push({ id, type, message: String(message ?? '') })
  if (duration > 0) setTimeout(() => dismiss(id), duration)
  return id
}

export const toast = {
  success: (message, duration = 3000) => push('success', message, duration),
  error: (message, duration = 4500) => push('error', message, duration),
  warning: (message, duration = 4000) => push('warning', message, duration),
  info: (message, duration = 3000) => push('info', message, duration),
  loading: (message) => {
    const id = push('loading', message, 0)
    return () => dismiss(id)
  },
}

export function useToastState() {
  return state
}

export { dismiss as dismissToast }
