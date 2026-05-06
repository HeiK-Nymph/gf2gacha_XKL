import {ref} from 'vue'
import {useGachaAnalyzeStore} from '@/stores/gachaAnalyze'
import request from '@/common/request'

export const gachaAnalyze = () => {

    const requestText = ref('')

    const gachaAnalyzeStore = useGachaAnalyzeStore()

    const gotoGachaDetail = async () => {

        const text = requestText.value
        if (!text || !text.trim()) {
            uni.showToast({ title: '请粘贴请求内容', icon: 'none' })
            return
        }

        let parsedData
        try {
            parsedData = JSON.parse(text.trim())
        } catch (e) {
            uni.showToast({ title: '格式不正确', icon: 'none' })
            return
        }


        try{
            const res = await request.post('/api/gacha-web/get',
                {
                    firstJson: parsedData
                },
                {
                    loading: true
                }
            )
            gachaAnalyzeStore.myGfUserInfo = res

            // 解析成功后，将 uid+时间戳 存入本地历史记录（uidList）
            if (res && res.uid) {
                saveUidRecord(res.uid)
            }

            uni.navigateTo({
                url: '/gachaCoreViews/gacha-detail/gacha-detail'
            })

        }catch(e){
            console.log(e)
        }
    }

    /**
     * 将 uid 存入本地历史记录（uidList）
     * 数据结构: [{ uid: string, time: number(时间戳) }]
     * 按时间倒序排列，重复 uid 更新其时间戳到最新
     */
    const saveUidRecord = (uid) => {
        try {
            let uidList = uni.getStorageSync('uidList') || []
            // 去除已有的相同 uid 记录（避免重复）
            uidList = uidList.filter(item => item.uid !== uid)
            // 在头部插入新记录
            uidList.unshift({ uid, time: Date.now() })
            // 最多保留 50 条记录
            if (uidList.length > 50) {
                uidList = uidList.slice(0, 50)
            }
            uni.setStorageSync('uidList', uidList)
        } catch (e) {
            console.error('[saveUidRecord] 保存历史记录失败:', e)
        }
    }

    const gotoGachaRank = () => {
        uni.navigateTo({
            url: '/gachaCoreViews/gacha-rank/gacha-rank'
        })
    }
    const gotoGachaRecords = () => {
        uni.navigateTo({
            url: '/gachaCoreViews/gacha-records/gacha-records'
        })
    }
    return {
        gotoGachaDetail,
        gotoGachaRank,
        gotoGachaRecords,
        requestText
    }
}