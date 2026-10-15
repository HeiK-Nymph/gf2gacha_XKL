import { shallowRef } from 'vue'

import { platforms } from '@/data/releases'

const TIMEOUT_MS = 6000

const releases = shallowRef(platforms.map((platform) => ({ ...platform, live: false })))
let started = false

async function fetchJson(url) {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), TIMEOUT_MS)
  try {
    const response = await fetch(url, { signal: controller.signal, cache: 'no-store' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    return await response.json()
  } finally {
    window.clearTimeout(timer)
  }
}

function merge(platform, remote) {
  if (!remote || typeof remote !== 'object') return { ...platform, live: false }
  const url = typeof remote.download_url === 'string' && remote.download_url.startsWith('https://')
    ? remote.download_url
    : platform.downloadUrl
  return {
    ...platform,
    downloadUrl: url,
    version: remote.current_version || platform.version,
    size: Number.isFinite(remote.size) ? remote.size : platform.size,
    sha256: remote.sha256 || platform.sha256,
    notes: remote.update_info || platform.notes,
    live: true,
  }
}

/**
 * R2 上的 version.json 没有开 CORS，跨域读取可能失败。
 * 失败就保留内置的兜底版本信息，页面照常可用。
 */
export async function loadReleases() {
  if (started) return
  started = true
  const results = await Promise.allSettled(platforms.map((platform) => fetchJson(platform.versionUrl)))
  releases.value = platforms.map((platform, index) => {
    const result = results[index]
    return result.status === 'fulfilled' ? merge(platform, result.value) : { ...platform, live: false }
  })
}

export function useReleases() {
  return releases
}
