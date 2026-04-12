<template>
  <el-container>
    <!-- 全屏加载遮罩 -->
    <div v-if="isLoading" class="loading-overlay">
      <div class="loading-content">
        <el-icon class="loading-spinner" :size="50"><Loading /></el-icon>
        <span class="loading-text">正在加载角色数据...</span>
      </div>
    </div>

    <el-header class="app-header">

      <div class="header-left">
        <el-button type="warning" size="large" @click="installCert">安装证书</el-button>
        <el-button type="danger" size="large" @click="uninstallCert">卸载证书</el-button>
        <el-button type="success" size="large" @click="updateRecord" :loading="isUpdating">更新记录</el-button>
        <el-button 
          :type="isCustomPurchaseOn ? 'success' : 'info'" 
          size="large" 
          @click="toggleCustomPurchase"
        >
          自选采购：{{ isCustomPurchaseOn ? '开' : '关' }}
        </el-button>
      </div>
      <div class="header-center">
        <div class="record-selector">
          <el-select
            v-model="selectedRecordId"
            placeholder="选择抽卡记录"
            size="large"
            style="width: 300px;"
            @change="onRecordChange"
          >
            <el-option
              v-for="record in recordList"
              :key="record"
              :label="record"
              :value="record"
            />
          </el-select>
        </div>
      </div>
      <div class="header-right">
        <span class="version-info">v{{ currentVersion }}</span>
        <el-button type="info" size="large" @click="checkUpdate">检查更新</el-button>
      </div>
    </el-header>
    <el-main class="app-main">

  

    
      <el-row :gutter="40">
        <el-col :span="8"><div class="app-main-item" >
          <span>角色池</span>
          <GachaItem pool_type="character" style="margin-right: auto;"></GachaItem>
        </div></el-col>
        <el-col :span="8"><div class="app-main-item" >
          <span>武器池</span>
          <GachaItem pool_type="weapon" style="margin-right: auto;"></GachaItem>
        </div></el-col>
        <el-col :span="8"><div class="app-main-item" >
          <span>常驻池</span>
          <GachaItem pool_type="permanent" style="margin-right: auto;"></GachaItem>
        </div></el-col>
      </el-row>
      
      <el-row :gutter="40" v-if="isCustomPurchaseOn">
        <el-col :span="8"><div class="app-main-item" >
          <span>自选角色池</span>
          <GachaItem pool_type="custom_character" style="margin-right: auto;"></GachaItem>
        </div></el-col>
        <el-col :span="8"><div class="app-main-item" >
          <span>自选武器池</span>
          <GachaItem pool_type="custom_weapon" style="margin-right: auto;"></GachaItem>
        </div></el-col>
      </el-row>
    </el-main>
  </el-container>
  
</template>

  
<script setup>
  import {ref, onMounted} from 'vue'
  import {Loading} from '@element-plus/icons-vue'
  import GachaItem from './components/GachaItem.vue'
  import {ElMessage, ElMessageBox} from 'element-plus'
  import {useGachaRecordStore} from '@/stores/gachaRecord'
  import {useSSRStore} from '@/stores/ssr'
  import versionInfo from '@/../../version.json'


  const gachaRecordStore = useGachaRecordStore()
  const ssrStore = useSSRStore()

  const recordList = ref([])
  const selectedRecordId = ref('')
  const currentVersion = ref(versionInfo.current_version)
  const isUpdating = ref(false)
  const isLoading = ref(true)
  const isCustomPurchaseOn = ref(false)

  // 显示更新通知
  const showUpdateNotification = (latestVersion) => {
    ElMessageBox.confirm(
      `发现新版本 v${latestVersion}，是否更新？`,
      '更新提示',
      {
        confirmButtonText: '更新',
        cancelButtonText: '稍后',
        type: 'info',
      }
    ).then(() => {
      startUpdate()
    }).catch(() => {
      // 用户取消
    })
  }

  // 开始更新
  const startUpdate = async () => {
    try {
      const res = await window.pywebview.api.start_update()
      if (res.status == 'success') {
        ElMessage.success('正在启动更新器...')
        // 更新器会自动关闭主程序
      } else {
        ElMessage.error(`启动更新失败: ${res.message || '未知错误'}`)
      }
    } catch (e) {
      console.error('[ERROR] 启动更新异常:', e)
      ElMessage.error(`启动更新失败: ${e.message || e}`)
    }
  }

  // 加载记录列表
  const loadRecordList = async () => {
    // 检查 pywebview 和方法是否已准备好
    if (!window.pywebview?.api?.get_record_list) {
      console.log('[INFO] pywebview API 尚未完全就绪，延迟加载记录列表...')
      // 300ms后重试，避免过于频繁
      setTimeout(loadRecordList, 300)
      return
    }

    try {
      const res = await window.pywebview.api.get_record_list()
      if (res.status == 'success') {
        recordList.value = res.data || []
        console.log('[INFO] 记录列表加载成功:', res.data)
      } else {
        console.error('[ERROR] 加载记录列表失败:', res.msg)
        ElMessage.error(`加载记录列表失败: ${res.msg}`)
      }
    } catch (e) {
      console.error('[ERROR] 加载记录列表异常:', e)
      ElMessage.error(`加载记录列表失败: ${e.message || e}`)
    }
  }

  // 手动检查更新
  const checkUpdate = async () => {
    try {
      const res = await window.pywebview.api.get_version_info()
      if (res.status == 'success') {
        currentVersion.value = res.current_version
        if (res.has_update) {
          showUpdateNotification(res.latest_version)
        } else {
          ElMessage.success('当前已是最新版本')
        }
      } else {
        console.error('[ERROR] 检查更新失败:', res.message)
        ElMessage.error(`检查更新失败: ${res.message || '未知错误'}`)
      }
    } catch (e) {
      console.error('[ERROR] 检查更新异常:', e)
      ElMessage.error(`检查更新失败: ${e.message || e}`)
    }
  }

  // 记录选择变化时自动导入
  const onRecordChange = async (recordId) => {
    if (!recordId) return

    await importRecordInternal(recordId)
  }

  // 导入记录（内部方法）
  const importRecordInternal = async (recordId) => {
    try {
      const res = await window.pywebview.api.import_record(recordId)
      if (res.status == 'success') {
        gachaRecordStore.gacha = res.data
        // 不显示导入成功提示，因为用户可能快速切换
      } else {
        console.error('[ERROR] 导入记录失败:', res.msg)
        ElMessage.error(res.msg)
      }
    } catch (e) {
      console.error('[ERROR] 导入记录异常:', e)
      ElMessage.error(`导入记录失败: ${e.message || e}`)
    }
  }

  // 打开GitHub主页
  const openGitHub = async () => {
    try {
      const res = await window.pywebview.api.open_github()
      if (res.status !== 'success') {
        console.error('[ERROR] 打开GitHub主页失败:', res.message)
        ElMessage.error(`打开GitHub主页失败: ${res.message || '未知错误'}`)
      }
    } catch (e) {
      console.error('[ERROR] 打开GitHub主页异常:', e)
      ElMessage.error(`打开GitHub主页失败: ${e.message || e}`)
    }
  }

  // 更新记录
  const updateRecord = async () => {
    isUpdating.value = true
    const loadingMessage = ElMessage({
      message: '正在获取抽卡记录...',
      type: 'info',
      duration: 0,
      showClose: false
    })

    try{
       const res = await window.pywebview.api.get_gacha()
       loadingMessage.close()

       if (res.status == 'success'){
          ElMessage.success(res.msg)
          // 新的数据结构包含uid和gacha
          gachaRecordStore.gacha = res.data.gacha
          
          // 自动保存记录，使用uid作为记录名称
          if (res.data.uid) {
            const uid = res.data.uid.toString()
            const saveRes = await window.pywebview.api.export_record(uid, gachaRecordStore.gacha)
            if (saveRes.status == 'success') {
              ElMessage.success(`记录已自动保存: ${uid}`)
              // 刷新记录列表并选中刚保存的记录
              await loadRecordList()
              selectedRecordId.value = uid
            } else {
              console.error('[ERROR] 自动保存记录失败:', saveRes.msg)
              ElMessage.error(`自动保存记录失败: ${saveRes.msg}`)
            }
          }
       }else{
          console.error('[ERROR] 获取记录失败:', res.msg)
          ElMessage.error(res.msg)
        }
   }catch (e) {
      loadingMessage.close()
      console.error('[ERROR] 获取记录异常:', e)
      ElMessage.error(`获取记录失败: ${e.message || e}`)
   } finally {
      isUpdating.value = false
   }
  }

  // 安装证书
  const installCert = async () => {
    try{
      const res = await window.pywebview.api.install_cert()
      if (res.status == 'success'){
        ElMessage.success(res.msg || '证书安装成功')
      }else{
        console.error('[ERROR] 安装证书失败:', res.msg)
        ElMessage.error(res.msg)
      }
    }catch (e) {
      console.error('[ERROR] 安装证书异常:', e)
      ElMessage.error(`安装证书失败: ${e.message || e}`)
    }
  }

  // 卸载证书
  const uninstallCert = async () => {
    try{
      // 确认对话框
      await ElMessageBox.confirm(
        '确定要卸载 gf2gacha_XKL 证书吗？',
        '警告',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        }
      )
      
      const res = await window.pywebview.api.uninstall_cert()
      if (res.status == 'success'){
        ElMessage.success(res.msg || '证书卸载成功')
      }else{
        console.error('[ERROR] 卸载证书失败:', res.msg)
        ElMessage.error(res.msg)
      }
    }catch (e) {
      if (e !== 'cancel') {
        console.error('[ERROR] 卸载证书异常:', e)
        ElMessage.error(`卸载证书失败: ${e.message || e}`)
      }
    }
  }

  // 切换自选采购开关
  const toggleCustomPurchase = () => {
    isCustomPurchaseOn.value = !isCustomPurchaseOn.value
  }

  // 组件挂载时加载数据
  onMounted(async () => {
    // 加载记录列表
    loadRecordList()
    
    // 加载SSR数据（前端主动控制）
    const source = await ssrStore.loadData()
    
    // 关闭遮罩
    isLoading.value = false
    
    // 显示提示
    if (source === 'remote' || source === 'local-proto') {
      ElMessage.success('正在使用最新五星数据')
    } else if (source === 'local-json') {
      ElMessage.warning('正在使用本地五星数据(可能不是最新)')
    } else {
      ElMessage.error('无法加载五星数据')
    }
  })

</script>
  
<style scoped>
  .app-header{
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .header-left {
    display: flex;
    gap: 10px;  /* 按钮之间的间距 */
  }
  .header-center {
    display: flex;
    gap: 10px;
    align-items: center;
  }
  .header-right {
    display: flex;
    gap: 10px;
    align-items: center;
  }
  .record-selector {
    display: flex;
    gap: 10px;
    align-items: center;
  }
  .version-info {
    font-size: 14px;
    color: #909399;
  }
  .app-main{
    /* background-color: blue; */
    height: 100%;
  }
  .app-main-item{
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-bottom: 20px;
    
  }
  .app-main-item span{
    font-size: 20px;
    font-weight: bold;
  }

  /* 全屏加载遮罩 */
  .loading-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 9999;
  }

  .loading-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
  }

  .loading-spinner {
    animation: spin 1s linear infinite;
    color: #409eff;
  }

  .loading-text {
    font-size: 18px;
    color: #606266;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>