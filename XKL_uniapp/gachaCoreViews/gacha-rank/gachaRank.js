import {ref, computed, onMounted} from 'vue'
import request from '../../common/request'
import { useGachaAnalyzeStore } from '../../stores/gachaAnalyze'

/**
 * 后端返回数据结构:
 * GET /api/gf-gacha-ranking/get → Result<GfGachaRankingListDTO>
 *
 * GfGachaRankingListDTO {
 *   gfGachaRankingListOrderByLuckValueDesc: GfGachaRankingListVO[],  // luckValue 降序
 *   gfGachaRankingListOrderByTotalDrawsDesc: GfGachaRankingListVO[]   // totalDraws 降序
 * }
 *
 * GfGachaRankingListVO {
 *   userId: number,     // 游戏UID
 *   luckValue: number,  // 欧皇值
 *   totalDraws: number  // 总抽数
 * }
 */

const MASK_UID = (uid) => {
    const s = String(uid)
    if (s.length <= 3) return s
    return s.slice(0, 3) + '***' + s.slice(-3)
}

export const gachaRank = (myUid = null) => {
    const activeTab = ref(0)
    const tabs = ['欧皇榜', '非酋榜', '氪佬榜']
    const loading = ref(true)
    const errorMsg = ref('')
    const showRulePopup = ref(false)
    const gachaAnalyzeStore = useGachaAnalyzeStore()

    // 原始数据（从接口获取）
    const orderByLuckValue = ref([])  // luckValue 降序
    const orderByTotalDraws = ref([]) // totalDraws 降序

    // 获取排行榜数据
    const fetchRankData = async () => {
        loading.value = true
        errorMsg.value = ''
        try {
            const data = await request.get('/api/gf-gacha-ranking/get')
            orderByLuckValue.value = data.gfGachaRankingListOrderByLuckValueDesc || []
            orderByTotalDraws.value = data.gfGachaRankingListOrderByTotalDrawsDesc || []
        } catch (e) {
            console.error('[gacha-rank] 获取排行榜失败:', e)
            errorMsg.value = '获取排行榜数据失败'
            orderByLuckValue.value = []
            orderByTotalDraws.value = []
        } finally {
            loading.value = false
        }
    }

    // ====== 欧皇榜：luckValue 降序（取前 100）======
    const ouhuangList = computed(() => {
        return orderByLuckValue.value.slice(0, 100).map((item, idx) => ({
            rank: idx + 1,
            value: item.luckValue,
            uid: MASK_UID(item.userId),
            _rawUid: item.userId,
            _rawValue: item.luckValue,
            _rawTotalDraws: item.totalDraws
        }))
    })

    // ====== 非酋榜：luckValue 升序（最非的排前，取后 100 反转）======
    const feiqiuList = computed(() => {
        const all = [...orderByLuckValue.value].reverse()
        return all.slice(0, 100).map((item, idx) => ({
            rank: idx + 1,
            value: item.luckValue,
            uid: MASK_UID(item.userId),
            _rawUid: item.userId,
            _rawValue: item.luckValue,
            _rawTotalDraws: item.totalDraws
        }))
    })

    // ====== 氪佬榜：totalDraws 降序，value = 总抽数 * 150（累计晶条）======
    const kelaoList = computed(() => {
        return orderByTotalDraws.value.slice(0, 100).map((item, idx) => ({
            rank: idx + 1,
            value: item.totalDraws * 150,
            uid: MASK_UID(item.userId),
            _rawUid: item.userId,
            _rawValue: item.luckValue,
            _rawTotalDraws: item.totalDraws
        }))
    })

    /**
     * 当前用户在各榜单中的排名信息
     * 从 myGfUserInfo.uid 读取自己的 uid（不受 rankGfUserInfo 影响）
     */
    const myRankData = computed(() => {
        // 从 myGfUserInfo（自己那份）实时读取 uid
        const currentMyUid = myUid || gachaAnalyzeStore.myGfUserInfo?.uid || null

        if (!currentMyUid) {
            return {
                ouhuang: { rank: null, value: null, percent: null },
                feiqiu: { rank: null, value: null, percent: null },
                kelao: { rank: null, value: null, percent: null }
            }
        }

        const uidNum = Number(currentMyUid)

        // 欧皇榜：在 luckValue 降序列表中查找
        const ouIdx = orderByLuckValue.value.findIndex(r => r.userId === uidNum)
        const ouItem = ouIdx >= 0 ? orderByLuckValue.value[ouIdx] : null

        // 非酋榜：在 luckValue 升序（反转）中查找
        const fiAll = [...orderByLuckValue.value].reverse()
        const fiIdx = fiAll.findIndex(r => r.userId === uidNum)
        const fiItem = fiIdx >= 0 ? fiAll[fiIdx] : null

        // 氪佬榜：在 totalDraws 降序列表中查找
        const klIdx = orderByTotalDraws.value.findIndex(r => r.userId === uidNum)
        const klItem = klIdx >= 0 ? orderByTotalDraws.value[klIdx] : null

        const totalO = orderByLuckValue.value.length
        const totalK = orderByTotalDraws.value.length

        return {
            ouhuang: ouItem
                ? { rank: ouIdx + 1, value: ouItem.luckValue, percent: totalO > 1 ? Math.round((1 - (ouIdx + 1) / totalO) * 100) : 100 }
                : { rank: null, value: null, percent: null },
            feiqiu: fiItem
                ? { rank: fiIdx + 1, value: fiItem.luckValue, percent: null }
                : { rank: null, value: null, percent: null },
            kelao: klItem
                ? { rank: klIdx + 1, value: klItem.totalDraws * 150, percent: totalK > 1 ? Math.round((1 - (klIdx + 1) / totalK) * 100) : 100 }
                : { rank: null, value: null, percent: null }
        }
    })

    const currentList = computed(() => {
        const lists = [ouhuangList.value, feiqiuList.value, kelaoList.value]
        return lists[activeTab.value]
    })

    const currentMyRank = computed(() => {
        const keys = ['ouhuang', 'feiqiu', 'kelao']
        return myRankData.value[keys[activeTab.value]]
    })

    // 表格标题
    const tableHeaders = computed(() => {
        if (activeTab.value === 2) return ['排名', '累计晶条', 'UID']
        return ['排名', '欧皇值', 'UID']
    })

    // 数值单位（仅氪佬榜需要"万"）
    const valueUnit = computed(() => {
        return ''
    })

    // 格式化显示值：氪佬榜>=10000自动加"万"
    const fmtValue = (val) => {
        if (activeTab.value !== 2) return val ?? '-'
        const n = Number(val)
        if (n >= 10000) return (n / 10000).toFixed(2)
        return String(n)
    }

    // 是否显示底部我的排名卡片（非酋榜隐藏）
    const showMyRankCard = computed(() => {
        if (loading.value || errorMsg.value) return false
        if (activeTab.value === 1) return false // 非酋榜不显示
        return true
    })

    const selectTab = (index) => { activeTab.value = index }
    const toggleRulePopup = () => { showRulePopup.value = !showRulePopup.value }
    const gotoAnalyze = () => {
        uni.navigateTo({ url: '/pages/gacha-analyze/gacha-analyze' })
    }

    /**
     * 点击榜单某一行，通过 uid 从后端获取 GfUserDTO 后跳转详情页
     * 数据写入 rankGfUserInfo（他人信息），不影响 myGfUserInfo（自己的信息）
     */
    const viewDetail = async (rawUid) => {
        try {
            const res = await request.get('/api/gf-user/get', { uid: rawUid },
                { loading: true, loadingText: '加载中...' }
            )
            // 写入 rankGfUserInfo（他人数据），不污染 myGfUserInfo
            gachaAnalyzeStore.rankGfUserInfo = res
            uni.navigateTo({
                url: `/gachaCoreViews/gacha-detail/gacha-detail?mask=1`
            })
        } catch (e) {
            console.error('[viewDetail] 获取用户数据失败:', e)
        }
    }

    onMounted(() => {
        fetchRankData()
    })

    return {
        activeTab, tabs, loading, errorMsg, showRulePopup,
        currentList, currentMyRank, tableHeaders, valueUnit,
        selectTab, toggleRulePopup, gotoAnalyze,
        fetchRankData, fmtValue, showMyRankCard, viewDetail
    }
}
