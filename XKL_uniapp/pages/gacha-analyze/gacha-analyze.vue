<template>
    <view class="gacha-analyze-container">
        <view class="gacha-analyze-title">▌少女前线2追放抽卡分析</view>
        <view class="input-container">
            <view class="input-title">请粘贴抽卡分析请求</view>
            <textarea 
                class="custom-input"
                placeholder="例如latest_request.json里的请求"
            />
        </view>
        <view class="bottom-container">
            <view class="bottom-item bottom-active" @click="gotoGachaDetail">开始分析</view>
            <view class="bottom-item" @click="gotoGachaRecords">历史记录</view>
            <view class="bottom-item" @click="gotoGachaRank">排行榜</view>
        </view>
        <view class="gacha-analyze-title">▌获取分析请求教程</view>
        <view class="readme-text">B站bv号：<text user-select="true">BV1M7AGzuEPk</text></view>
    </view>
    
</template>
    
<script setup>
    import { gachaAnalyze } from './gachaAnalyze'
    const {gotoGachaDetail, gotoGachaRank, gotoGachaRecords} = gachaAnalyze()
</script>
    
<style scoped lang="scss">
    @import './gachaAnalyze.scss';
</style>