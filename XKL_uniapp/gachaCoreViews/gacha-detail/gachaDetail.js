import {ref, computed} from 'vue'

export const gachaDetail = () => {
   const gachaOverview = ref([
    {
        count: "19",
        info:"五星数"
    },
    {
        count:"25抽",
        info:"角色平均"
    },
    {
        count:"14抽",
        info:"武器平均"
    },
    {
        count:"66抽",
        info:"常驻平均"
    }
   ])
   const SSRClass = ref([
    "角色池",
    "武器池",
    "常驻池",
    "自选角色",
    "自选武器"
   ])
   const activePoolIndex = ref(0)
   
   // 模拟数据 - 基于 ssr.json
   const mockGachaData = ref({
       // 角色池：UP角色不歪，常驻角色歪
       character: {
           totalDraws: 156,
           currentPad: 23,
           ssrList: [
               { id: '1057', name: '洛贝拉', costDraws: 12, isWai: false },
               { id: '1025', name: '托洛洛', costDraws: 45, isWai: true },
               { id: '1057', name: '洛贝拉', costDraws: 8, isWai: false },
               { id: '1029', name: '塞布丽娜', costDraws: 67, isWai: true },
               { id: '1043', name: '绯', costDraws: 31, isWai: true }
           ]
       },
       // 武器池：UP武器不歪，常驻武器歪
       weapon: {
           totalDraws: 89,
           currentPad: 5,
           ssrList: [
               { id: '11038', name: '游星', costDraws: 35, isWai: true },
               { id: '10001', name: '喧闹恶灵', costDraws: 22, isWai: false },
               { id: '11044', name: '金石奏', costDraws: 27, isWai: true }
           ]
       },
       // 常驻池：没有歪的概念
       permanent: {
           totalDraws: 200,
           currentPad: 15,
           ssrList: [
               { id: '1025', name: '托洛洛', costDraws: 55, isWai: false },
               { id: '1029', name: '塞布丽娜', costDraws: 72, isWai: false },
               { id: '11038', name: '游星', costDraws: 43, isWai: false },
               { id: '1043', name: '绯', costDraws: 28, isWai: false }
           ]
       },
       // 自选角色池
       custom_character: {
           totalDraws: 60,
           currentPad: 60,
           ssrList: []
       },
       // 自选武器池
       custom_weapon: {
           totalDraws: 45,
           currentPad: 45,
           ssrList: []
       }
   })
   
   const poolTypes = ['character', 'weapon', 'permanent', 'custom_character', 'custom_weapon']
   
   const currentPoolData = computed(() => mockGachaData.value[poolTypes[activePoolIndex.value]])
   const currentPoolType = computed(() => poolTypes[activePoolIndex.value])
   const ssrTotal = computed(() => currentPoolData.value.ssrList.length)
   
   const waiCount = computed(() => {
       if (currentPoolType.value === 'permanent') return 0
       return currentPoolData.value.ssrList.filter(item => item.isWai).length
   })
   
   // 进度条颜色：绿色<30<黄色<60<红色
   const getProgressColor = (costDraws) => {
       if (costDraws < 30) return '#66ad68'
       if (costDraws < 60) return '#F0C044'
       return '#D66555'
   }
   
   const getImagePath = (id) => `https://static.gf2gacha-xkl.uk/images/character/${id}.png`
   
   const selectPool = (index) => { activePoolIndex.value = index }
   
   const gotoGachaRank = () => {
    uni.navigateTo({
        url:'/gachaCoreViews/gacha-rank/gacha-rank'
    })
   }

   return {
        gachaOverview, SSRClass, activePoolIndex, selectPool,
        currentPoolData, currentPoolType, ssrTotal, waiCount,
        getProgressColor, getImagePath,
        gotoGachaRank
    }
}