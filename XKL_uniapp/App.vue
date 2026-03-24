<script>
	export default {
		onLaunch: function() {
			console.log('App Launch')
		},
		onShow: function() {
			console.log('App Show')
		},
		onHide: function() {
			console.log('App Hide')
		}
	}
</script>

<style>
	/*每个页面公共css */
	page {
		/* 兼容老版本 iPhone */
		padding-bottom: constant(safe-area-inset-bottom);
		/* 标准安全区 */
		padding-bottom: env(safe-area-inset-bottom);
		
		/* 如果你想再多留点空隙（可选） */
		padding-bottom: calc(env(safe-area-inset-bottom) + 50rpx);
	}
</style>
