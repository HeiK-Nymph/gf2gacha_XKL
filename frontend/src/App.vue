<template>
  <el-container>
    <el-header class="app-header">

      <div class="header-left">
        <el-button type="warning" size="large" @click="installCert">安装证书</el-button>
        <el-button type="success" size="large" @click="updateRecord" :loading="isUpdating">更新记录</el-button>
        <el-button type="primary" size="large" @click="exportRecord">保存记录</el-button>
      </div>
      <div class="header-center">
        <div class="record-selector">
          <template v-if="isInputMode">
            <el-input
              v-model="newRecordId"
              placeholder="请输入新记录名称"
              size="large"
              style="width: 300px;"
              @keyup.enter="saveNewRecord"
            />
            <el-button type="primary" size="large" @click="saveNewRecord">保存</el-button>
            <el-button size="large" @click="cancelNewRecord">取消</el-button>
          </template>
          <template v-else>
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
            <el-button type="success" size="large" @click="showInputMode">
              <el-icon><Plus /></el-icon>
            </el-button>
          </template>
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
    </el-main>
  </el-container>
  
</template>

  
<script setup>
  import {ref, onMounted} from 'vue'
  import {Plus} from '@element-plus/icons-vue'
  import GachaItem from './components/GachaItem.vue'
  import {ElMessage, ElMessageBox} from 'element-plus'
  import {useGachaRecordStore} from '@/stores/gachaRecord'
  import versionInfo from '@/../../version.json'


  const gachaRecordStore = useGachaRecordStore()

  const recordList = ref([])
  const selectedRecordId = ref('')
  const newRecordId = ref('')
  const currentVersion = ref(versionInfo.current_version)
  const isUpdating = ref(false)
  const isInputMode = ref(false)

  // 显示更新通知
  const showUpdateNotification = (latestVersion) => {
    ElMessageBox.confirm(
      `发现新版本 v${latestVersion}，是否前往 GitHub 下载？`,
      '更新提示',
      {
        confirmButtonText: '前往下载',
        cancelButtonText: '稍后',
        type: 'info',
      }
    ).then(() => {
      openGitHub()
    }).catch(() => {
      // 用户取消
    })
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

  // 显示输入模式（添加新记录）
  const showInputMode = () => {
    isInputMode.value = true
    newRecordId.value = ''
  }

  // 取消添加新记录
  const cancelNewRecord = () => {
    isInputMode.value = false
    newRecordId.value = ''
  }

  // 保存新记录
  const saveNewRecord = () => {
    if (newRecordId.value.trim() == '') {
      ElMessage.error('请输入记录名称')
      return
    }

    if (recordList.value.includes(newRecordId.value.trim())) {
      ElMessage.error('该记录已存在')
      return
    }

    selectedRecordId.value = newRecordId.value.trim()
    isInputMode.value = false
    newRecordId.value = ''
    ElMessage.success('记录创建成功')
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

  const exportRecord = async () => {
    if (!selectedRecordId.value) {
      ElMessage.error('请先选择或创建一个记录')
      return
    }

    try{
      const res = await window.pywebview.api.export_record(selectedRecordId.value, gachaRecordStore.gacha)
      if (res.status == 'success'){
        ElMessage.success(res.msg)
        // 导出后刷新记录列表
        loadRecordList()
      }else{
        console.error('[ERROR] 导出记录失败:', res.msg)
        ElMessage.error(res.msg)
      }
    }catch (e) {
      console.error('[ERROR] 导出记录异常:', e)
      ElMessage.error(`导出记录失败: ${e.message || e}`)
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
          gachaRecordStore.gacha = res.data
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
        ElMessage.success(res.msg)
      }else{
        console.error('[ERROR] 打开证书网站失败:', res.msg)
        ElMessage.error(res.msg)
      }
    }catch (e) {
      console.error('[ERROR] 打开证书网站异常:', e)
      ElMessage.error(`打开证书网站失败: ${e.message || e}`)
    }
  }

  // 组件挂载时加载记录列表
  onMounted(() => {
    loadRecordList()
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
    
  }
  .app-main-item span{
    font-size: 20px;
    font-weight: bold;
  }
</style>