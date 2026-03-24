<template>
    <view class="gacha-records-container">
        <view class="records-header">
            <view class="records-title">历史记录</view>
            <view class="records-count">共 {{ recordsList.length }} 条记录</view>
        </view>
        <view class="records-tip">选中记录左滑即可删除</view>
        
        <scroll-view scroll-y class="records-list">
            <view 
                class="record-item-wrapper" 
                v-for="item in recordsList" 
                :key="item.id"
            >
                <!-- 删除按钮（底层） -->
                <view class="delete-btn" @click="deleteRecord(item.id)">
                    <text class="delete-text">删除</text>
                </view>
                
                <!-- 记录内容（上层，可滑动） -->
                <view 
                    class="record-item"
                    :style="{ transform: `translateX(${item.offsetX}rpx)` }"
                    @touchstart="touchStart($event, item)"
                    @touchmove="touchMove($event, item)"
                    @touchend="touchEnd(item)"
                    @click="viewDetail(item.uid)"
                >
                    <view class="record-info">
                        <view class="record-uid">UID：{{ item.uid }}</view>
                        <view class="record-time">{{ item.time }}</view>
                    </view>
                    <view class="record-arrow">›</view>
                </view>
            </view>
            
            <!-- 空状态 -->
            <view class="empty-state" v-if="recordsList.length === 0">
                <text class="empty-text">暂无历史记录</text>
            </view>
        </scroll-view>
    </view>
</template>
    
<script setup>
    import {gachaRecords} from './gachaRecords'
    const {recordsList, touchStart, touchMove, touchEnd, deleteRecord, viewDetail} = gachaRecords()
</script>
    
<style scoped lang="scss">
    @import './gachaRecords.scss';
</style>