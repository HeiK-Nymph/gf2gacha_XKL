import { ref, onMounted } from 'vue'
import request from '@/common/request'
import { useGachaAnalyzeStore } from '@/stores/gachaAnalyze'

const STORAGE_KEY = 'uidList'

export const gachaRecords = () => {

    // 从本地存储读取 uidList，按时间戳倒序排列
    const recordsList = ref([])

    const gachaAnalyzeStore = useGachaAnalyzeStore()

    // 页面加载时读取本地记录
    onMounted(() => {
        loadUidRecords()
    })

    /**
     * 从本地存储加载 uid 历史记录，按时间倒序展示
     * 每条记录格式: { uid: string, time: number(时间戳) }
     */
    const loadUidRecords = () => {
        try {
            const list = uni.getStorageSync(STORAGE_KEY)
            if (list && Array.isArray(list)) {
                // 按时间戳降序排序（最新的在前）
                list.sort((a, b) => b.time - a.time)
                // 为每条记录添加 offsetX 用于左滑动画
                recordsList.value = list.map(item => ({
                    ...item,
                    offsetX: 0
                }))
            }
        } catch (e) {
            console.error('[loadUidRecords] 读取历史记录失败:', e)
        }
    }

    // 触摸开始位置
    const startX = ref(0)

    // 触摸开始
    const touchStart = (e, item) => {
        startX.value = e.touches[0].clientX
        // 重置其他项的偏移
        recordsList.value.forEach(record => {
            if (record.uid !== item.uid) {
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

    /**
     * 删除单条记录（通过覆盖写入的方式）
     * 从当前列表中过滤掉目标 uid，然后用 setStorageSync 覆盖整个列表
     */
    const deleteRecord = (uid) => {
        try {
            // 过滤掉要删除的记录
            const newList = recordsList.value.filter(item => item.uid !== uid)
            // 用 setStorageSync 覆盖写入，实现删除效果
            uni.setStorageSync(STORAGE_KEY, newList)
            // 更新响应式数据
            recordsList.value = newList
            uni.showToast({ title: '已删除', icon: 'none' })
        } catch (e) {
            console.error('[deleteRecord] 删除历史记录失败:', e)
            uni.showToast({ title: '删除失败', icon: 'none' })
        }
    }

    /**
     * 查看详情：通过 GET /api/gf-user/get?uid=xxx 从后端获取 GfUserDTO
     * 获取成功后存入 Pinia Store 并跳转到详情页
     */
    const viewDetail = async (uid) => {
        try {
            const res = await request.get('/api/gf-user/get', { uid },
                { loading: true, loadingText: '加载中...' }
            )
            // 将后端返回的 GfUserDTO 存入 myGfUserInfo（自己的数据）
            gachaAnalyzeStore.myGfUserInfo = res
            uni.navigateTo({
                url: '/gachaCoreViews/gacha-detail/gacha-detail'
            })
        } catch (e) {
            console.error('[viewDetail] 获取用户数据失败:', e)
        }
    }

    /**
     * 格式化时间戳为可读字符串
     */
    const formatTime = (timestamp) => {
        const date = new Date(timestamp)
        const Y = date.getFullYear()
        const M = String(date.getMonth() + 1).padStart(2, '0')
        const D = String(date.getDate()).padStart(2, '0')
        const h = String(date.getHours()).padStart(2, '0')
        const m = String(date.getMinutes()).padStart(2, '0')
        return `${Y}-${M}-${D} ${h}:${m}`
    }

    return {
        recordsList,
        touchStart,
        touchMove,
        touchEnd,
        deleteRecord,
        viewDetail,
        formatTime
    }
}
