<template>
    <view class="gacha-detail-container">
        <view class="user-info">
            <view class="uid">UID：100***383</view>
            <view class="gacha-overview">总抽卡次数：<text>894抽</text></view>
            <view class="gacha-overview">小保底不歪：<text>100%</text></view>
        </view>
    </view>
</template>
    
<script setup>
    import { gachaDetail } from './gachaDetail'
</script>
    
<style scoped lang="scss">
    @import './gachaDetail.scss';
</style>