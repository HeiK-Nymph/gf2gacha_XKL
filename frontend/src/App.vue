<template>
  <el-container>
    <el-header class="app-header">

      <div class="header-left">
        <el-button type="warning" size="large" @click="installCert">安装证书</el-button>
        <el-button type="success" size="large" @click="updateRecord">更新记录</el-button>
        <el-button type="primary" size="large" @click="importRecord">导入记录</el-button>
        <el-button type="primary" size="large" @click="exportRecord">导出记录</el-button>
      </div>
      <div class="header-right">
        <span class="version-info">v{{ currentVersion }}</span>
        <el-button type="info" size="large" @click="checkUpdate">检查更新</el-button>
      </div>
      <el-input v-model="recordId" placeholder="请设置导入导出的ID" size="large" style="width: 20%;"/>
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
  import {ref, computed, onMounted} from 'vue'
  import GachaItem from './components/GachaItem.vue'
  import {ElMessage, ElMessageBox} from 'element-plus'
  import {useGachaRecordStore} from '@/stores/gachaRecord'
  
  
  const gachaRecordStore = useGachaRecordStore()

  const recordId = ref('')
  const currentVersion = ref('1.0.0')

  // 获取版本信息
  const getVersionInfo = async () => {
    try {
      const res = await window.pywebview.api.get_version_info()
      if (res.status == 'success') {
        currentVersion.value = res.current_version
        if (res.has_update) {
          showUpdateNotification(res.latest_version)
        }
      }
    } catch (e) {
      console.error('获取版本信息失败', e)
    }
  }

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

  // 手动检查更新
  const checkUpdate = async () => {
    try {
      const res = await window.pywebview.api.get_version_info()
      if (res.status == 'success') {
        if (res.has_update) {
          showUpdateNotification(res.latest_version)
        } else {
          ElMessage.success('当前已是最新版本')
        }
      } else {
        ElMessage.error('检查更新失败')
      }
    } catch (e) {
      ElMessage.error('检查更新失败')
    }
  }

  // 打开GitHub主页
  const openGitHub = async () => {
    try {
      const res = await window.pywebview.api.open_github()
      if (res.status !== 'success') {
        ElMessage.error('打开GitHub主页失败')
      }
    } catch (e) {
      ElMessage.error('打开GitHub主页失败')
    }
  }

  const exportRecord = async () => {
    if (recordId.value == ''){
      ElMessage.error('请设置导出记录的ID')
      return
    }

    try{
      const res = await window.pywebview.api.export_record(recordId.value, gachaRecordStore.gacha)
      if (res.status == 'success'){
        ElMessage.success(res.msg)
      }else{
        ElMessage.error(res.msg)
      }
    }catch (e) {
      ElMessage.error('导出记录失败') 
    }
  }

  const importRecord = async () => {
    if (recordId.value == ''){
      ElMessage.error('请设置导入记录的ID')
      return
    }
    try{
      const res = await window.pywebview.api.import_record(recordId.value)
      if (res.status == 'success'){
        ElMessage.success(res.msg)
        gachaRecordStore.gacha = res.data
      }else{
        ElMessage.error(res.msg)
      }
    }catch (e) {
      ElMessage.error('导入记录失败')
    }
  }

  // 更新记录
  const updateRecord = async () => {
    try{
       const res = await window.pywebview.api.get_gacha()
       if (res.status == 'success'){
          ElMessage.success(res.msg)
          gachaRecordStore.gacha = res.data
       }else{
          ElMessage.error(res.msg)
        }
   }catch (e) {
      
      ElMessage.error('获取记录失败')
   }
  }
  
  // 安装证书
  const installCert = async () => {
    try{
      const res = await window.pywebview.api.install_cert()
      if (res.status == 'success'){
        ElMessage.success(res.msg)
      }else{
        ElMessage.error(res.msg)
      }
    }catch (e) {
      ElMessage.error('打开证书网站失败')
    }
  }

  // 组件挂载时获取版本信息
  onMounted(() => {
    getVersionInfo()
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
  .header-right {
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