import { ref } from 'vue'
import { defineStore } from 'pinia'
import { waitForApi } from '../utils/bridge.js'

// 角色/武器图片缓存：后端磁盘缓存 24 小时，前端用 data URI 覆盖远程地址。
export const useImageCacheStore = defineStore('imageCache', () => {
  const images = ref({})
  let pending = null

  const normalize = (urls) => [...new Set((urls || []).filter((url) => typeof url === 'string' && url.startsWith('http')))]

  async function ensureImages(urls) {
    const wanted = normalize(urls)
    const missing = wanted.filter((url) => !images.value[url])
    if (!missing.length) return images.value
    if (!(await waitForApi())) return images.value

    if (pending) {
      await pending
      return ensureImages(missing)
    }

    pending = (async () => {
      try {
        const result = await window.pywebview.api.get_cached_images(missing)
        if (result?.status === 'success' && result.images) {
          images.value = { ...images.value, ...result.images }
        }
      } catch (error) {
        console.error('[图片缓存] 读取失败', error)
      }
    })().finally(() => {
      pending = null
    })

    await pending
    return images.value
  }

  return { images, ensureImages }
})