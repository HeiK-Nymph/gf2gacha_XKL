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
            <view class="rank-rule">排名规则</view>
            <view class="rank-test">测一测我的排名</view>
        </view>
        
        <!-- 表格 -->
        <view class="rank-table">
            <!-- 表头 -->
            <view class="table-header">
                <view class="th-rank">{{ tableHeaders[0] }}</view>
                <view class="th-value">{{ tableHeaders[1] }}</view>
                <view class="th-uid">{{ tableHeaders[2] }}</view>
            </view>
            
            <!-- 表格内容 -->
            <scroll-view scroll-y class="table-body">
                <view class="table-row" v-for="item in currentList" :key="item.uid">
                    <view class="td-rank">
                        <text v-if="item.rank === 1" class="rank-medal rank-gold">1</text>
                        <text v-else-if="item.rank === 2" class="rank-medal rank-silver">2</text>
                        <text v-else-if="item.rank === 3" class="rank-medal rank-bronze">3</text>
                        <text v-else class="rank-num">{{ item.rank }}</text>
                    </view>
                    <view class="td-value">{{ item.value }}{{ valueUnit }}</view>
                    <view class="td-uid">{{ item.uid }}</view>
                </view>
            </scroll-view>
        </view>
        
        <!-- 我的排名（固定底部） -->
        <view class="my-rank-card" v-if="!(activeTab === 1 && currentMyRank.rank === null)">
            <view class="my-rank-info">
                <text class="my-rank-label">我的排名</text>
                <text class="my-rank-value" v-if="currentMyRank.rank">{{ currentMyRank.rank }}</text>
                <text class="my-rank-value" v-else>未上榜</text>
            </view>
            <view class="my-rank-divider"></view>
            <view class="my-rank-info">
                <text class="my-rank-label">{{ tableHeaders[1] }}</text>
                <text class="my-rank-value">{{ currentMyRank.value }}{{ valueUnit }}</text>
            </view>
            <view class="my-rank-divider" v-if="activeTab !== 1 && currentMyRank.percent"></view>
            <view class="my-rank-info" v-if="activeTab !== 1 && currentMyRank.percent">
                <text class="my-rank-label">超越</text>
                <text class="my-rank-value">{{ currentMyRank.percent }}%</text>
            </view>
        </view>
    </view>
</template>
    
<script setup>
    import {gachaRank} from './gachaRank'
    const {activeTab, tabs, currentList, currentMyRank, tableHeaders, valueUnit, selectTab} = gachaRank()
</script>
    
<style scoped lang="scss">
    @import './gachaRank.scss';
</style>