import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useSSRStore = defineStore('ssr', () => {
  const SSR_character = ref({})
  const SSR_weapon = ref({})
  const SSR_permanent = ref({})
  const SSR_version = ref('')
  const SSR_fromRemote = ref(false)
  const isLoaded = ref(false)

  async function loadData() {
    if (isLoaded.value) return

    try {
      // 等待 pywebview 完全准备好（最多等待10秒）
      let apiReady = false
      for (let i = 0; i < 100; i++) {
        if (window.pywebview?.api?.load_ssr_data) {
          apiReady = true
          break
        }
        console.log(`[SSR] 等待 pywebview 准备中... ${i + 1}/100`)
        await new Promise(r => setTimeout(r, 100))
      }
      
      if (!apiReady) {
        console.error('[SSR] pywebview 未准备好')
        return 'error'
      }
      
      // 调用后端加载数据
      const result = await window.pywebview.api.load_ssr_data()
      const data = result.data
      SSR_character.value = data.SSR_character || {}
      SSR_weapon.value = data.SSR_weapon || {}
      SSR_permanent.value = data.SSR_permanent || {}
      SSR_version.value = data.version || ''
      SSR_fromRemote.value = result.source === 'remote'
      isLoaded.value = true
      
      return result.source  // 返回数据来源
    } catch (e) {
      console.error('[SSR] 加载失败', e)
      return 'error'
    }
  }

  return {
    SSR_character,
    SSR_weapon,
    SSR_permanent,
    SSR_version,
    SSR_fromRemote,
    loadData,
    isLoaded
  }
})
