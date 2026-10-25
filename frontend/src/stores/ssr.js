import { ref } from 'vue'
import { defineStore } from 'pinia'
import { waitForApi, withTimeout } from '../utils/bridge.js'

export const useSSRStore = defineStore('ssr', () => {
  const SSR_character = ref({})
  const SSR_weapon = ref({})
  const SSR_permanent = ref({})
  const SR_character = ref({})
  const SR_weapon = ref({})
  const SSR_custom_character = ref({})
  const SSR_custom_weapon = ref({})
  const SSR_version = ref('')
  const SSR_fromRemote = ref(false)
  const isLoaded = ref(false)
  const source = ref('error')
  const isRefreshing = ref(false)
  let refreshTimer = null
  let stopped = false

  function apply(result) {
    if (stopped) return false
    isRefreshing.value = !!result?.refreshing
    if (stopped || result?.status !== 'success' || !result.data?.SSR_character) return false
    const data = result.data
    SSR_character.value = data.SSR_character || {}
    SSR_weapon.value = data.SSR_weapon || {}
    SSR_permanent.value = data.SSR_permanent || {}
    SR_character.value = data.SR_character || {}
    SR_weapon.value = data.SR_weapon || {}
    SSR_custom_character.value = SSR_character.value
    SSR_custom_weapon.value = SSR_weapon.value
    SSR_version.value = data.version || ''
    SSR_fromRemote.value = ['remote', 'local-proto'].includes(result.source)
    source.value = result.source
    isLoaded.value = true
    return true
  }

  function scheduleRefresh(deadline) {
    if (stopped) return
    if (Date.now() >= deadline) {
      isRefreshing.value = false
      return
    }
    refreshTimer = setTimeout(async () => {
      try {
        const result = await withTimeout(window.pywebview.api.get_startup_ssr_data())
        apply(result)
        if (result?.refreshing) scheduleRefresh(deadline)
      } catch (error) {
        isRefreshing.value = false
        console.error('[SSR] 后台刷新状态获取失败', error)
      }
    }, 1000)
  }

  async function loadData() {
    if (isLoaded.value) return source.value
    stopped = false
    try {
      if (!(await waitForApi())) throw new Error('程序接口尚未就绪')
      const result = await withTimeout(window.pywebview.api.get_startup_ssr_data())
      apply(result)
      if (result?.refreshing) scheduleRefresh(Date.now() + 20000)
      return source.value
    } catch (error) {
      console.error('[SSR] 加载失败', error)
      return 'error'
    }
  }

  function stopRefresh() {
    stopped = true
    clearTimeout(refreshTimer)
  }

  return {
    SSR_character, SSR_weapon, SSR_permanent, SSR_custom_character, SSR_custom_weapon,
    SR_character, SR_weapon,
    SSR_version, SSR_fromRemote, loadData, isLoaded, source, isRefreshing, stopRefresh,
  }
})
