import {defineStore} from 'pinia'
import {ref} from 'vue'

export const useGachaAnalyzeStore = defineStore('gachaAnalyze', () => {

    /**
     * GfUserDTO 数据结构（两份存储，互相隔离）：
     *
     * {
     *   uid: string,
     *   gachaRecordsList: GachaRecordsVO[],  // 5个池子各一条
     *   totalDraws: number,                   // 全部池子总抽数
     *   totalSSR: number,                     // 全部池子总SSR数
     *   safeRate: number,                     // 保底不歪率（百分比整数）
     *   waiCnt: number,                       // 总歪数
     *   avgCharacter: number,                 // 角色池平均抽数
     *   avgWeapon: number,                    // 武器池平均抽数
     *   avgPermanent: number                  // 常驻池平均抽数
     * }
     */

    /** 自己的用户信息（分析JSON / 历史记录入口写入） */
    const myGfUserInfo = ref({})

    /** 排行榜查看的他人信息（排行榜 viewDetail 写入） */
    const rankGfUserInfo = ref({})

    return {

        myGfUserInfo,
        rankGfUserInfo

    }

})
