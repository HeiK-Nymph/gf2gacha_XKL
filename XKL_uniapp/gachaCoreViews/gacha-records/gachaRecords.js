import {ref} from 'vue'

export const gachaRecords = () => {
    // 模拟历史记录数据
    const recordsList = ref([
        { id: 1, uid: '100456783', time: '2026-03-24 15:30', offsetX: 0 },
        { id: 2, uid: '100382910', time: '2026-03-23 12:15', offsetX: 0 },
        { id: 3, uid: '100729481', time: '2026-03-22 09:45', offsetX: 0 },
        { id: 4, uid: '100183472', time: '2026-03-21 18:20', offsetX: 0 },
        { id: 5, uid: '100928374', time: '2026-03-20 14:55', offsetX: 0 },
        { id: 6, uid: '100562193', time: '2026-03-19 11:30', offsetX: 0 },
        { id: 7, uid: '100847261', time: '2026-03-18 16:40', offsetX: 0 },
        { id: 8, uid: '100294817', time: '2026-03-17 10:25', offsetX: 0 }
    ])
    
    // 触摸开始位置
    const startX = ref(0)
    
    // 触摸开始
    const touchStart = (e, item) => {
        startX.value = e.touches[0].clientX
        // 重置其他项的偏移
        recordsList.value.forEach(record => {
            if (record.id !== item.id) {
                record.offsetX = 0
            }
        })
    }
    
    // 触摸移动
    const touchMove = (e, item) => {
        const moveX = e.touches[0].clientX - startX.value
        // 只允许左滑（负值），最大滑动距离150rpx
        if (moveX < 0) {
            item.offsetX = Math.max(moveX, -150)
        } else if (item.offsetX < 0 && moveX > 0) {
            // 右滑恢复
            item.offsetX = Math.min(0, item.offsetX + moveX)
        }
    }
    
    // 触摸结束
    const touchEnd = (item) => {
        // 如果滑动超过一半，展开删除按钮
        if (item.offsetX < -75) {
            item.offsetX = -150
        } else {
            // 否则恢复
            item.offsetX = 0
        }
    }
    
    // 删除记录
    const deleteRecord = (id) => {
        recordsList.value = recordsList.value.filter(item => item.id !== id)
    }
    
    // 查看详情
    const viewDetail = (uid) => {
        uni.navigateTo({
            url: `/gachaCoreViews/gacha-detail/gacha-detail?uid=${uid}`
        })
    }
    
    return {
        recordsList,
        touchStart,
        touchMove,
        touchEnd,
        deleteRecord,
        viewDetail
    }
}
