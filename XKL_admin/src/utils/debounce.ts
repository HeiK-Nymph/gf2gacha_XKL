/**
 * 创建一个异步操作锁，防止用户快速重复点击导致重复提交
 * @returns {Object} { run(fn), loading, reset() }
 *
 * 用法：
 *   const lock = useAsyncLock()
 *   <button :loading="lock.loading" @click="lock.run(async () => { ... })">提交</button>
 */
export function useAsyncLock() {
  let _locked = false

  const run = async <T>(fn: () => Promise<T>): Promise<T> => {
    if (_locked) return Promise.reject(new Error('操作正在进行中，请稍候'))
    _locked = true
    try {
      return await fn()
    } finally {
      _locked = false
    }
  }

  const reset = () => { _locked = false }

  return { run, get loading() { return _locked }, reset }
}
