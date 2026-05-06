<template>
    <view class="gacha-detail-container">
        <!-- 用户信息概览 — 对应 GfUserDTO 顶层字段 -->
        <view class="user-info">
            <view class="uid">UID：{{ displayUid }}</view>
            <view class="user-info-gacha-all">总抽卡次数：<text>{{ userInfo.totalDraws ?? 0 }}抽</text></view>
            <view class="user-info-gacha-all">小保底不歪：<text>{{ userInfo.safeRate ?? 0 }}%</text></view>
        </view>
        <!-- 概览卡片 — 对应 GfUserDTO 统计值 -->
        <view class="gacha-overview-content">
            <view class="gacha-overview">
                <view class="gacha-overview-item" v-for="(v) in gachaOverview" :key="v.info">
                    <view class="gacha-overview-item-count">{{ v.count }}</view>
                    <view class="gacha-overview-item-info">{{ v.info }}</view>
                </view>
            </view>
            <view class="user-rank">
                <view class="user-rank-bto" @click="gotoGachaRank">我的排名</view>
            </view>
        </view>
        <!-- 池子分类 Tab — 对应 gachaRecordsList 的 5 个 poolType -->
        <view class="SSR-class-content">
            <view
                class="SSR-class"
                :class="{ 'SSR-class-active': activePoolIndex === index }"
                v-for="(label, index) in SSRClass"
                :key="index"
                @click="selectPool(index)"
            >{{ label }}</view>
        </view>
        <!-- 当前池子详情 — 对应当前 GachaRecordsVO + 其 GachaItemVO[] -->
        <view class="gacha-detail-content">
            <!-- 池子统计摘要 -->
            <view class="gacha-stats">
                <view>一共<text class="highlight">{{ totalDraws }}</text>条抽卡记录，已垫<text class="highlight">{{ currentPad }}</text>抽</view>
                <view>共获得五星<text class="highlight">{{ ssrTotal }}</text>个<text v-if="!isWeaponPool && SSRClass[activePoolIndex] !== '常驻池'">，歪了<text class="highlight">{{ waiCount }}</text>个</text></view>
            </view>

            <!-- SSR 头像网格（仅非武器池显示） -->
            <view class="ssr-grid" v-if="ssrList.length > 0 && !isWeaponPool">
                <view class="ssr-grid-item" v-for="(item, index) in ssrList" :key="(item.itemId || 'q') + '-' + (item.drawOrder ?? index)">
                    <image :src="getImagePath(item.itemId)" class="ssr-avatar" mode="aspectFill"/>
                </view>
            </view>

            <!-- question 占位符：当前垫抽进度条 (gachaItems[0]) -->
            <view class="ssr-item" v-if="totalDraws > 0">
                <image :src="getImagePath('question')" class="ssr-avatar" mode="aspectFill"/>
                <view class="progress-wrapper">
                    <view class="progress-bar" :style="{ width: Math.min(currentPad * 1.25, 100) + '%' }">
                        <text class="progress-text">{{ currentPad }}抽</text>
                    </view>
                </view>
            </view>

            <!-- SSR 列表详情 (gachaItems[1..n]) -->
            <view class="ssr-item" v-for="(item, index) in ssrList" :key="'detail-' + (item.itemId || 'q') + '-' + (item.drawOrder ?? index)">
                <!-- 角色类：显示头像图片；武器类：显示名称文字 -->
                <image v-if="!isWeaponPool" :src="getImagePath(item.itemId)" class="ssr-avatar" mode="aspectFill"/>
                <text v-else class="weapon-name">{{ item.itemName }}</text>
                <!-- 抽取进度条 -->
                <view class="progress-wrapper">
                    <view class="progress-bar" :style="{ width: Math.min(item.costDraws * 1.25, 100) + '%', backgroundColor: getProgressColor(item.costDraws) }">
                        <text class="progress-text">{{ item.costDraws }}抽</text>
                    </view>
                </view>
                <!-- 歪标签：限定池中 ssrType=3(常驻) 才显示 -->
                <text v-if="item.isWai === 1" class="wai-tag">歪</text>
            </view>
        </view>
    </view>
</template>

<script setup>
    import { gachaDetail } from './gachaDetail'
    const {
        gachaOverview, SSRClass, activePoolIndex,
        totalDraws, currentPad, ssrTotal, waiCount, ssrList, isWeaponPool,
        userInfo, displayUid,
        selectPool, getProgressColor, getImagePath, gotoGachaRank
    } = gachaDetail()
</script>

<style scoped lang="scss">
    @import './gachaDetail.scss';
</style>
