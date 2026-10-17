import { createApp, h, nextTick } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import html2canvas from 'html2canvas'
import GachaItem from '../src/components/GachaItem.vue'
import { useSSRStore } from '../src/stores/ssr.js'
import { useGachaRecordStore } from '../src/stores/gachaRecord.js'
import characterIcon from '../../images/gacha/character/1001.png?inline'
import weaponIcon from '../../images/gacha/weapon/10001.png?inline'

// 实际组件使用本地图片替身，不请求线上图床；10002 专门模拟加载失败。
const imageSource = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src')
Object.defineProperty(HTMLImageElement.prototype, 'src', {
  get: imageSource.get,
  set(value) {
    if (typeof value === 'string' && value.startsWith('https://static.gf2gacha-xkl.uk/')) {
      this.dataset.requestedSrc = value
      value = value.endsWith('/10002.png') ? 'data:image/png;base64,broken' : value.includes('/weapon/') ? weaponIcon : characterIcon
    }
    imageSource.set.call(this, value)
  },
})

const pinia = createPinia()
const ssr = useSSRStore(pinia)
const records = useGachaRecordStore(pinia)
const longName = '这是一把用于验证完整显示的超长武器名称'
ssr.SSR_character = {1001: '角色甲', 1008: '角色乙', 1009: '角色丙', 1017: '角色丁', 1022: '角色戊'}
ssr.SSR_weapon = {10001: '短名', 10002: longName, 10003: '中等武器名', 10004: '第四把武器', 10005: '第五把武器'}
ssr.SSR_permanent = {1001: '角色甲', 10001: '短名', 10002: longName}
ssr.SSR_custom_character = ssr.SSR_character
ssr.SSR_custom_weapon = ssr.SSR_weapon
const pools = ['character', 'weapon', 'permanent', 'custom_character', 'custom_weapon']
const names = ['角色池', '武器池', '常驻池', '自选角色池', '自选武器池']
const buildPool = (ids) => [{data: {list: Array.from({length: 266}, (_, index) => ({
  item: ids[[8, 37, 67, 126, 186].indexOf(index)] || 999,
  time: 2000000000 - index,
  pool_id: 1,
}))}}]
pools.forEach(pool => {
  const ids = pool.includes('weapon') ? [10001, 10002, 10003, 10004, 10005]
    : pool === 'permanent' ? [1001, 10001, 10002, 1001, 10001] : [1001, 1008, 1009, 1017, 1022]
  records.gacha[`${pool}_pool`] = buildPool(ids)
})
const style = document.createElement('style')
style.textContent = `body {margin:20px; background:white; font-family:"Microsoft YaHei",sans-serif; color:#303133}
  .fixture-screen {display:grid;grid-template-columns:repeat(3,350px);gap:24px;width:1098px}
  .fixture-pool>h3 {text-align:center;margin:12px 0}
  .screenshot-container {display:flex;gap:20px;width:1090px;padding:15px;background:white;margin-top:24px}
  .screenshot-container .fixture-pool {width:350px;flex:none}`
document.head.appendChild(style)
createApp({setup: () => () => [
  h('section', {class: 'fixture-screen'}, pools.map((pool,index) => h('div', {class:'fixture-pool', 'data-pool':pool}, [h('h3',names[index]),h(GachaItem,{pool_type:pool})]))),
  h('section',{class:'screenshot-container'}, pools.slice(0,3).map((pool,index) => h('div',{class:'fixture-pool','data-pool':pool},[h('h3',names[index]),h(GachaItem,{pool_type:pool,shareMode:true})]))),
]}).use(pinia).use(ElementPlus).mount('#app')
window.html2canvas = html2canvas
window.layoutFixture = {records, nextTick, longName, characterIcon}
nextTick(() => {window.fixtureReady = true})
