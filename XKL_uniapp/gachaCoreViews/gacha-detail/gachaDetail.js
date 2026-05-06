import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { useGachaAnalyzeStore } from '@/stores/gachaAnalyze'

/**
 * gacha-detail 页面逻辑
 * 数据来源：
 *   1. Pinia Store (gachaAnalyze.gfUserInfo) = 后端 GfUserDTO 解包后的对象（从分析入口页或历史记录页写入）
 *   2. 支持通过 onLoad 接收 URL 参数中的 uid
 *
 * 数据链路：
 * POST /api/gacha-web/get → Result<GfUserDTO> → request.js 解包 resolve(result.data)
 * → 存入 store.gfUserInfo → 本页面通过 computed 读取并渲染
 *
 * 或：
 * GET /api/gf-user/get?uid=xxx → Result<GfUserDTO> → 存入 store.gfUserInfo → 本页面渲染
 */

export const gachaDetail = () => {

    const store = useGachaAnalyzeStore()

    // =============================================
    // 通过 onLoad 获取 URL 参数（兼容微信小程序）
    // =============================================
    const needMaskUid = ref(false)  // 是否需要对 UID 去敏（排行榜入口传入 mask=1）

    onLoad((options) => {
        if (options) {
            if (options.mask === '1') {
                needMaskUid.value = true
            }
        }
    })

    // =============================================
    // Tab 配置：与后端 GachaRecordsVO.poolType 对应
    // =============================================
    const POOL_TABS = [
        { key: 'character',       label: '角色池',       poolType: 3 },
        { key: 'weapon',          label: '武器池',       poolType: 4 },
        { key: 'permanent',       label: '常驻池',       poolType: 1 },
        { key: 'custom_character', label: '自选角色',     poolType: 6 },
        { key: 'custom_weapon',   label: '自选武器',     poolType: 7 }
    ]

    const activePoolIndex = ref(0)

    // =============================================
    // 从 store 读取用户信息（响应式）
    // mask=1 时读 rankGfUserInfo（排行榜查看的他人数据）
    // 否则读 myGfUserInfo（自己的数据：分析JSON / 历史记录入口）
    // =============================================
    const userInfo = computed(() => {
        if (needMaskUid.value) {
            return store.rankGfUserInfo || {}
        }
        return store.myGfUserInfo || {}
    })

    // UID 显示（根据入口来源决定是否去敏）
    // needMaskUid=true 时去敏（排行榜进入），否则显示原始 UID（分析JSON / 历史记录进入）
    const displayUid = computed(() => {
        const uid = userInfo.value.uid || ''
        if (needMaskUid.value && uid.length >= 4) {
            return uid.slice(0, 3) + '***' + uid.slice(-3)
        }
        return uid
    })

    // =============================================
    // 顶部概览卡片数据 — 对应 GfUserDTO 的统计字段
    // =============================================
    const gachaOverview = computed(() => [
        { count: String(userInfo.value.totalSSR ?? 0), info: '五星数' },
        { count: `${userInfo.value.avgCharacter ?? 0}抽`,   info: '角色平均' },
        { count: `${userInfo.value.avgWeapon ?? 0}抽`,      info: '武器平均' },
        { count: `${userInfo.value.avgPermanent ?? 0}抽`,   info: '常驻平均' }
    ])

    // =============================================
    // 当前选中池子的数据 — 对应 GfUserDTO.gachaRecordsList 中的一条
    // =============================================

    /** 当前激活的 tab 配置 */
    const currentTabConfig = computed(() => POOL_TABS[activePoolIndex.value])

    /** 当前池子的完整记录对象 (GachaRecordsVO) */
    const currentPoolRecord = computed(() => {
        const records = userInfo.value.gachaRecordsList || []
        const targetPoolType = currentTabConfig.value.poolType
        return records.find(r => r.poolType === targetPoolType) || null
    })

    /** 当前池子总抽数 */
    const totalDraws = computed(() => currentPoolRecord.value?.totalDraws ?? 0)

    /** 当前池子总SSR数 */
    const ssrTotal = computed(() => currentPoolRecord.value?.totalSSR ?? 0)

    /** 当前池子歪数（常驻池固定为0） */
    const waiCount = computed(() => {
        if (!currentPoolRecord.value) return 0
        if (currentTabConfig.value.key === 'permanent') return 0
        return currentPoolRecord.value.waiCnt ?? 0
    })

    /**
     * 当前池子的垫抽数 (currentPad)
     * 来自 gachaItems[0] 的 costDraws（question 占位符）
     */
    const currentPad = computed(() => {
        const items = currentPoolRecord.value?.gachaItems
        if (!items || items.length === 0) return 0
        // gachaItems[0] 是 question 占位符，costDraws 表示最新SSR后的垫抽数
        return items[0]?.costDraws ?? 0
    })

    /**
     * SSR 列表 — 排除 question 占位符（index=0）
     * 每项对应一个 GachaItemVO
     */
    const ssrList = computed(() => {
        const items = currentPoolRecord.value?.gachaItems
        if (!items || items.length <= 1) return []
        // 从 index=1 开始才是真实的 SSR 记录
        return items.slice(1)
    })

    // =============================================
    // SSR 分类名称列表（用于 tab 标签）
    // =============================================
    const SSRClass = computed(() => POOL_TABS.map(tab => tab.label))

    // =============================================
    // 工具方法
    // =============================================

    /** 进度条颜色：<30绿色 <60黄色 >=60红色 */
    const getProgressColor = (costDraws) => {
        if (costDraws < 30) return '#66ad68'
        if (costDraws < 60) return '#F0C044'
        return '#D66555'
    }

    /** 角色头像图片路径 */
    const getImagePath = (id) => `https://static.gf2gacha-xkl.uk/images/character/${id}.png`

    /** 是否为武器类池子（用文字而非图片展示） */
    const isWeaponPool = computed(() => {
        const key = currentTabConfig.value?.key
        return key === 'weapon' || key === 'custom_weapon'
    })

    /** 选择池子 tab */
    const selectPool = (index) => { activePoolIndex.value = index }

    /** 跳转排名页 */
    const gotoGachaRank = () => {
        uni.navigateTo({
            url: '/gachaCoreViews/gacha-rank/gacha-rank'
        })
    }

    return {
        // 响应式数据
        gachaOverview,
        SSRClass,
        activePoolIndex,
        // 当前池子数据
        totalDraws,
        currentPad,
        ssrTotal,
        waiCount,
        ssrList,
        isWeaponPool,
        // 用户概览
        userInfo,
        displayUid,
        // 方法
        selectPool,
        getProgressColor,
        getImagePath,
        gotoGachaRank
    }
}
