import test from 'node:test'
import assert from 'node:assert/strict'
import { setActivePinia, createPinia } from 'pinia'
import { useSSRStore } from '../src/stores/ssr.js'
import { withTimeout, waitForApi } from '../src/utils/bridge.js'

test('永不返回的桥接调用会超时', async () => {
  await assert.rejects(withTimeout(new Promise(() => {}), 20), /超时/)
})

test('API 未注入时等待有上限', async () => {
  globalThis.window = {}
  assert.equal(await waitForApi(20), false)
})

test('先用内置表显示，后台刷新后更新数据，退出停止轮询', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] })
  let calls = 0
  globalThis.window = { pywebview: { api: { get_startup_ssr_data: async () => {
    calls++
    return {
      status: 'success', source: calls === 1 ? 'local-json' : 'local-proto',
      data: { SSR_character: { 1: calls === 1 ? 'old' : 'new' } }, refreshing: calls === 1,
    }
  } } } }
  setActivePinia(createPinia())
  const store = useSSRStore()
  assert.equal(await store.loadData(), 'local-json')
  assert.equal(store.isLoaded, true)
  assert.equal(store.isRefreshing, true)
  assert.equal(calls, 1)
  t.mock.timers.tick(1000)
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(store.SSR_character[1], 'new')
  assert.equal(store.SSR_fromRemote, true)
  assert.equal(store.source, 'local-proto')
  assert.equal(store.isRefreshing, false)
  store.stopRefresh()
  t.mock.timers.tick(5000)
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(calls, 2)
})

test('后端不返回时 store 会结束加载而非永久挂起', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] })
  t.mock.method(console, 'error', () => {})
  globalThis.window = { pywebview: { api: { get_startup_ssr_data: () => new Promise(() => {}) } } }
  setActivePinia(createPinia())
  const store = useSSRStore()
  const loading = store.loadData()
  await new Promise(resolve => setImmediate(resolve))
  t.mock.timers.tick(5000)
  assert.equal(await loading, 'error')
  store.stopRefresh()
})
