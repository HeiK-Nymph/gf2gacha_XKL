import { reactive } from 'vue'

// 轻量全局确认框（替代 ElMessageBox.confirm）：promise 风格。
// const ok = await confirmDialog({ title, message, confirmText, cancelText, danger })
const state = reactive({
  visible: false,
  title: '确认',
  message: '',
  confirmText: '确定',
  cancelText: '取消',
  danger: false,
  _resolve: null,
})

export function confirmDialog(options = {}) {
  return new Promise((resolve) => {
    Object.assign(state, {
      visible: true,
      title: '确认',
      message: '',
      confirmText: '确定',
      cancelText: '取消',
      danger: false,
      ...options,
      _resolve: resolve,
    })
  })
}

export function settleConfirm(result) {
  state.visible = false
  const resolve = state._resolve
  state._resolve = null
  if (resolve) resolve(result)
}

export function useConfirmState() {
  return state
}
