<template>
    <view class="gacha-detail-container">
        <view class="user-info">
            <view class="uid">UID：100***383</view>
            <view class="user-info-gacha-all">总抽卡次数：<text>894抽</text></view>
            <view class="user-info-gacha-all">小保底不歪：<text>100%</text></view>
        </view>
        <view class="gacha-overview-content">
            <view class="gacha-overview">
                <view class="gacha-overview-item" v-for="v in gachaOverview" key="v.info">
                    <view class="gacha-overview-item-count">{{ v.count }}</view>
                    <view class="gacha-overview-item-info">{{ v.info }}</view>
                </view>
            </view>
            <view class="user-rank">
                <view class="user-rank-bto" @click="gotoGachaRank">我的排名</view>
            </view>
        </view>
        <view class="SSR-class-content">
            <view 
                class="SSR-class" 
                :class="{ 'SSR-class-active': activePoolIndex === index }"
                v-for="(v, index) in SSRClass" 
                :key="v"
                @click="selectPool(index)"
            >{{ v }}</view>
        </view>
        <view class="gacha-detail-content">
            <view class="gacha-stats">
                <view>一共<text class="highlight">{{ currentPoolData.totalDraws }}</text>条抽卡记录，已垫<text class="highlight">{{ currentPoolData.currentPad }}</text>抽</view>
                <view>共获得五星<text class="highlight">{{ ssrTotal }}</text>个<text v-if="currentPoolType !== 'permanent'">，歪了<text class="highlight">{{ waiCount }}</text>个</text></view>
            </view>
            
            <view class="ssr-grid" v-if="ssrTotal > 0">
                <view class="ssr-grid-item" v-for="(item, index) in currentPoolData.ssrList" :key="index">
                    <image v-if="currentPoolType !== 'weapon' && currentPoolType !== 'custom_weapon'" :src="getImagePath(item.id)" class="ssr-avatar" mode="aspectFill"/>
                    <text v-else class="weapon-name">{{ item.name }}</text>
                </view>
            </view>
            
            <view class="ssr-item" v-if="currentPoolData.totalDraws > 0">
                <image :src="getImagePath('question')" class="ssr-avatar" mode="aspectFill"/>
                <view class="progress-wrapper">
                    <view class="progress-bar" :style="{ width: currentPoolData.currentPad * 1.25 + '%' }">
                        <text class="progress-text">{{ currentPoolData.currentPad }}抽</text>
                    </view>
                </view>
            </view>
            
            <view class="ssr-item" v-for="(item, index) in currentPoolData.ssrList" :key="index">
                <image v-if="currentPoolType !== 'weapon' && currentPoolType !== 'custom_weapon'" :src="getImagePath(item.id)" class="ssr-avatar" mode="aspectFill"/>
                <text v-else class="weapon-name">{{ item.name }}</text>
                <view class="progress-wrapper">
                    <view class="progress-bar" :style="{ width: item.costDraws * 1.25 + '%', backgroundColor: getProgressColor(item.costDraws) }">
                        <text class="progress-text">{{ item.costDraws }}抽</text>
                    </view>
                </view>
                <text v-if="item.isWai && currentPoolType !== 'permanent'" class="wai-tag">歪</text>
            </view>
        </view>
    </view>
</template>
    
<script setup>
    import { gachaDetail } from './gachaDetail'
    const {gachaOverview, SSRClass, activePoolIndex, selectPool, currentPoolData, currentPoolType, ssrTotal, waiCount, getProgressColor, getImagePath, gotoGachaRank} = gachaDetail()
</script>
    
<style scoped lang="scss">
    @import './gachaDetail.scss';
</style>