// 超时只结束前端等待；后台任务由后端管理。
export async function withTimeout(promise, timeoutMs = 5000) {
  let timer
  try {
    return await Promise.race([
      promise,
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error('等待程序响应超时，请重试或查看日志')), timeoutMs)
      }),
    ])
  } finally {
    clearTimeout(timer)
  }
}

export async function waitForApi(timeoutMs = 5000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (window.pywebview?.api?.get_startup_ssr_data) return true
    await new Promise(resolve => setTimeout(resolve, 50))
  }
  return false
}
