import {ref} from 'vue'

export const index = () => {
    const gotoGachaAnalyze = () => {
        uni.navigateTo({
            url: '/pages/gacha-analyze/gacha-analyze'
        })
    }
    return {
        gotoGachaAnalyze
    }
}