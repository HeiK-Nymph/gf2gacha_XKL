import {ref} from 'vue'

export const index = () => {
    const gotoGachaAnalyze = () => {
        uni.navigateTo({
            url: '/pages/gacha-analyze/gacha-analyze'
        })
    }
    const gotoGachaRank = () => {
        uni.navigateTo({
            url: '/gachaCoreViews/gacha-rank/gacha-rank'
        })
    }
    return {
        gotoGachaAnalyze,
        gotoGachaRank
    }
}