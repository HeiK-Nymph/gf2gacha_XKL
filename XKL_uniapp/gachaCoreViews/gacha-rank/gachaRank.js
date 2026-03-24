import {ref, computed} from 'vue'

export const gachaRank = () => {
    const activeTab = ref(0)
    const tabs = ['欧皇榜', '非酋榜', '氪佬榜']
    
    // 模拟欧皇榜数据（欧气值降序）
    const ouhuangList = ref([
        { rank: 1, value: 99.8, uid: '100***123' },
        { rank: 2, value: 98.5, uid: '100***456' },
        { rank: 3, value: 97.2, uid: '100***789' },
        { rank: 4, value: 95.6, uid: '100***234' },
        { rank: 5, value: 94.3, uid: '100***567' },
        { rank: 6, value: 92.1, uid: '100***890' },
        { rank: 7, value: 90.8, uid: '100***345' },
        { rank: 8, value: 88.4, uid: '100***678' },
        { rank: 9, value: 86.5, uid: '100***901' },
        { rank: 10, value: 85.2, uid: '100***112' },
        { rank: 2, value: 98.5, uid: '100***456' },
        { rank: 3, value: 97.2, uid: '100***789' },
        { rank: 4, value: 95.6, uid: '100***234' },
        { rank: 5, value: 94.3, uid: '100***567' },
        { rank: 6, value: 92.1, uid: '100***890' },
        { rank: 7, value: 90.8, uid: '100***345' },
        { rank: 8, value: 88.4, uid: '100***678' },
        { rank: 9, value: 86.5, uid: '100***901' },
        { rank: 10, value: 85.2, uid: '100***112' },
        { rank: 2, value: 98.5, uid: '100***456' },
        { rank: 3, value: 97.2, uid: '100***789' },
        { rank: 4, value: 95.6, uid: '100***234' },
        { rank: 5, value: 94.3, uid: '100***567' },
        { rank: 6, value: 92.1, uid: '100***890' },
        { rank: 7, value: 90.8, uid: '100***345' },
        { rank: 8, value: 88.4, uid: '100***678' },
        { rank: 9, value: 86.5, uid: '100***901' },
        { rank: 10, value: 85.2, uid: '100***112' },
        { rank: 2, value: 98.5, uid: '100***456' },
        { rank: 3, value: 97.2, uid: '100***789' },
        { rank: 4, value: 95.6, uid: '100***234' },
        { rank: 5, value: 94.3, uid: '100***567' },
        { rank: 6, value: 92.1, uid: '100***890' },
        { rank: 7, value: 90.8, uid: '100***345' },
        { rank: 8, value: 88.4, uid: '100***678' },
        { rank: 9, value: 86.5, uid: '100***901' },
        { rank: 10, value: 85.2, uid: '100***112' },
        { rank: 2, value: 98.5, uid: '100***456' },
        { rank: 3, value: 97.2, uid: '100***789' },
        { rank: 4, value: 95.6, uid: '100***234' },
        { rank: 5, value: 94.3, uid: '100***567' },
        { rank: 6, value: 92.1, uid: '100***890' },
        { rank: 7, value: 90.8, uid: '100***345' },
        { rank: 8, value: 88.4, uid: '100***678' },
        { rank: 9, value: 86.5, uid: '100***901' },
        { rank: 10, value: 85.2, uid: '100***112' }
    ])
    
    // 模拟非酋榜数据（欧气值升序，即欧气值最低的排前面）
    const feiqiuList = ref([
        { rank: 1, value: 12.3, uid: '100***999' },
        { rank: 2, value: 15.6, uid: '100***888' },
        { rank: 3, value: 18.2, uid: '100***777' },
        { rank: 4, value: 21.5, uid: '100***666' },
        { rank: 5, value: 24.8, uid: '100***555' },
        { rank: 6, value: 28.1, uid: '100***444' },
        { rank: 7, value: 31.4, uid: '100***333' },
        { rank: 8, value: 34.7, uid: '100***222' },
        { rank: 9, value: 38.0, uid: '100***111' },
        { rank: 10, value: 41.2, uid: '100***000' }
    ])
    
    // 模拟氪佬榜数据（累计晶条，单位：万）
    const kelaoList = ref([
        { rank: 1, value: 15.8, uid: '100***001' },
        { rank: 2, value: 13.2, uid: '100***002' },
        { rank: 3, value: 9.8, uid: '100***003' },
        { rank: 4, value: 8.6, uid: '100***004' },
        { rank: 5, value: 7.2, uid: '100***005' },
        { rank: 6, value: 5.8, uid: '100***006' },
        { rank: 7, value: 4.5, uid: '100***007' },
        { rank: 8, value: 3.8, uid: '100***008' },
        { rank: 9, value: 2.6, uid: '100***009' },
        { rank: 10, value: 1.8, uid: '100***010' }
    ])
    
    // 当前用户数据
    const myRankData = ref({
        ouhuang: { rank: 256, value: 78.5, percent: 68 },
        feiqiu: { rank: null, value: 52.3, percent: null },
        kelao: { rank: 1024, value: 0.45, percent: 85 }
    })
    
    const currentList = computed(() => {
        const lists = [ouhuangList.value, feiqiuList.value, kelaoList.value]
        return lists[activeTab.value]
    })
    
    const currentMyRank = computed(() => {
        const keys = ['ouhuang', 'feiqiu', 'kelao']
        return myRankData.value[keys[activeTab.value]]
    })
    
    // 表格标题（去掉称号列）
    const tableHeaders = computed(() => {
        if (activeTab.value === 2) return ['排名', '累计晶条', 'UID']
        return ['排名', '欧气值', 'UID']
    })
    
    // 数值单位
    const valueUnit = computed(() => {
        if (activeTab.value === 2) return '万'
        return ''
    })
    
    const selectTab = (index) => { activeTab.value = index }
    
    return {
        activeTab, tabs, currentList, currentMyRank, tableHeaders, valueUnit, selectTab
    }
}