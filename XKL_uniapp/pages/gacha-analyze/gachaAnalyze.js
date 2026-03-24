import {ref} from 'vue'
export const gachaAnalyze = () => {
    const gotoGachaDetail = () => {
        uni.navigateTo({
            url: '/gachaCoreViews/gacha-detail/gacha-detail'
        })
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
        gotoGachaRecords
    }
}