<template>
	<view class="content">
		<view class="hot-utils">
			<view class="hot-utils-title">热门工具</view>
			<view class="hot-utils-content">
				<view class="gacha-analyze" @click="gotoGachaAnalyze">抽卡分析</view>
				<view class="gacha-rank">排行榜</view>
			</view>
		</view>
	</view>
</template>

<script setup>
	import {index} from './index'
	const {gotoGachaAnalyze} = index()
</script>

<style lang="scss">
	@import './index.scss';
</style>
