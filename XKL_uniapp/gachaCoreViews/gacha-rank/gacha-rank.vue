<template>
    <view class="gacha-rank-container">
        <!-- Tab 切换 -->
        <view class="rank-tabs">
            <view 
                class="rank-tab" 
                :class="{ 'rank-tab-active': activeTab === index }"
                v-for="(tab, index) in tabs" 
                :key="tab"
                @click="selectTab(index)"
            >{{ tab }}</view>
        </view>
        
        <!-- 标题栏 -->
        <view class="rank-header">
            <view class="rank-rule" @click="toggleRulePopup">排名规则</view>
            <view class="rank-test" @click="gotoAnalyze">测一测我的排名</view>
        </view>

        <!-- Loading 状态 -->
        <view v-if="loading" class="rank-loading">
            <text>加载中...</text>
        </view>

        <!-- 错误状态 -->
        <view v-else-if="errorMsg" class="rank-error">
            <text>{{ errorMsg }}</text>
            <view class="retry-btn" @click="fetchRankData">点击重试</view>
        </view>

        <!-- 表格 -->
        <view v-else class="rank-table">
            <!-- 表头 -->
            <view class="table-header">
                <view class="th-rank">{{ tableHeaders[0] }}</view>
                <view class="th-value">{{ tableHeaders[1] }}</view>
                <view class="th-uid">{{ tableHeaders[2] }}</view>
            </view>
            
            <!-- 表格内容 -->
            <scroll-view scroll-y class="table-body">
                <view v-if="currentList.length === 0" class="rank-empty">
                    <text>暂无数据</text>
                </view>
                <view class="table-row" v-else v-for="(item, idx) in currentList" :key="item.uid + '-' + idx" @click="viewDetail(item._rawUid)">
                    <view class="td-rank">
                        <text v-if="item.rank === 1" class="rank-medal rank-gold">1</text>
                        <text v-else-if="item.rank === 2" class="rank-medal rank-silver">2</text>
                        <text v-else-if="item.rank === 3" class="rank-medal rank-bronze">3</text>
                        <text v-else class="rank-num">{{ item.rank }}</text>
                    </view>
                    <view class="td-value">{{ fmtValue(item.value) }}{{ activeTab === 2 && item.value >= 10000 ? '万' : valueUnit }}</view>
                    <view class="td-uid">{{ item.uid }}</view>
                </view>
            </scroll-view>
        </view>
        
        <!-- 我的排名（固定底部，非酋榜不显示） -->
        <view class="my-rank-card" v-if="showMyRankCard && !(activeTab === 1 && currentMyRank?.rank === null)">
            <view class="my-rank-info">
                <text class="my-rank-label">我的排名</text>
                <text class="my-rank-value" v-if="currentMyRank?.rank">{{ currentMyRank.rank }}</text>
                <text class="my-rank-value" v-else>未上榜</text>
            </view>
            <view class="my-rank-divider"></view>
            <view class="my-rank-info">
                <text class="my-rank-label">{{ tableHeaders[1] }}</text>
                <text class="my-rank-value">{{ fmtValue(currentMyRank?.value) }}{{ activeTab === 2 && currentMyRank?.value >= 10000 ? '万' : valueUnit }}</text>
            </view>
            <view class="my-rank-divider" v-if="activeTab !== 1 && currentMyRank?.percent"></view>
            <view class="my-rank-info" v-if="activeTab !== 1 && currentMyRank?.percent">
                <text class="my-rank-label">超越</text>
                <text class="my-rank-value">{{ currentMyRank.percent }}%</text>
            </view>
        </view>

        <!-- 排名规则弹窗 -->
        <view class="rule-mask" v-if="showRulePopup" @click="toggleRulePopup">
            <view class="rule-popup" @click.stop>
                <view class="rule-popup-title">欧皇值计算规则</view>
                <view class="rule-popup-content">
                    <view class="rule-item">
                        <view class="rule-formula">出率分 = 8000 / 平均每颗五星花费抽数</view>
                        <view class="rule-desc">平均抽数越少，出率分越高。比如平均40抽一颗五星得200分，20抽一颗得400分。</view>
                    </view>
                    <view class="rule-item">
                        <view class="rule-formula">不歪分 = 不歪率 x 300</view>
                        <view class="rule-desc">在限定池（角色/武器池）中抽到限定五星算"没歪"，抽到常驻五星算"歪了"。全不歪满分300分。</view>
                    </view>
                    <view class="rule-item">
                        <view class="rule-formula">早出分 = 30抽内出货比例 x 150</view>
                        <view class="rule-desc">30抽以内就出五星算"早出"。早出比例越高，分数越高。全部早出则拿满150分。</view>
                    </view>
                    <view class="rule-note">
                        <text>注：样本量太少时分数会打折（SSR少于5个/限定SSR少于3个），避免运气波动导致排名虚高。</text>
                    </view>
                    <view class="rule-total">
                        <text>欧皇值 = 出率分 + 不歪分 + 早出分</text>
                    </view>
                </view>
                <view class="rule-popup-close" @click="toggleRulePopup">我知道了</view>
            </view>
        </view>
    </view>
</template>
    
<script setup>
    import {gachaRank} from './gachaRank'
    import {useGachaAnalyzeStore} from '../../stores/gachaAnalyze'

    const gachaAnalyzeStore = useGachaAnalyzeStore()
    // 传入当前用户的 UID 用于高亮自己的排名（读自己的那份）
    const myUid = gachaAnalyzeStore.myGfUserInfo?.uid || null

    const {activeTab, tabs, loading, errorMsg, showRulePopup, currentList, currentMyRank, tableHeaders, valueUnit, selectTab, toggleRulePopup, gotoAnalyze, fetchRankData, fmtValue, showMyRankCard, viewDetail} = gachaRank(myUid)
</script>
    
<style scoped lang="scss">
    @import './gachaRank.scss';
</style>