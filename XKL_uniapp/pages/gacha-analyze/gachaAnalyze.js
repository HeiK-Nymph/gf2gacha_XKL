import {ref} from 'vue'
export const gachaAnalyze = () => {
    const gotoGachaDetail = () => {
        uni.navigateTo({
            url: '/gachaCoreViews/gacha-detail/gacha-detail'
        })
    }
    return {
        gotoGachaDetail
    }
}