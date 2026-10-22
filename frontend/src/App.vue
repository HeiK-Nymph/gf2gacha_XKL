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
        <el-button type="primary" size="large" @click="openShareDialog" :loading="isSharing">
          <el-icon style="margin-right: 4px;"><Share /></el-icon>分享
        </el-button>
        <span class="version-info">v{{ currentVersion }}</span>
        <el-button type="info" size="large" @click="checkUpdate">检查更新</el-button>
        <el-button type="info" size="large" @click="openLogDialog">日志</el-button>
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

    <!-- 离屏截图容器（用于生成分享图片） -->
    <div ref="screenshotContainerRef" class="screenshot-container">
      <div class="screenshot-pools-row">
        <div class="screenshot-pool-item" v-show="sharePoolChecked('character')">
          <span class="screenshot-pool-title">角色池</span>
          <GachaItem pool_type="character" share-mode />
        </div>
        <div class="screenshot-pool-item" v-show="sharePoolChecked('weapon')">
          <span class="screenshot-pool-title">武器池</span>
          <GachaItem pool_type="weapon" share-mode />
        </div>
        <div class="screenshot-pool-item" v-show="sharePoolChecked('permanent')">
          <span class="screenshot-pool-title">常驻池</span>
          <GachaItem pool_type="permanent" share-mode />
        </div>
        <div class="screenshot-pool-item" v-show="sharePoolChecked('custom_character')">
          <span class="screenshot-pool-title">自选角色池</span>
          <GachaItem pool_type="custom_character" share-mode />
        </div>
        <div class="screenshot-pool-item" v-show="sharePoolChecked('custom_weapon')">
          <span class="screenshot-pool-title">自选武器池</span>
          <GachaItem pool_type="custom_weapon" share-mode />
        </div>
      </div>
    </div>

    <!-- 「分享」窗口：先勾选要分享的卡池，再出图 -->
    <el-dialog v-model="shareDialogVisible" title="选择要分享的卡池" width="460px">
      <div class="share-pool-list">
        <el-checkbox
          v-for="pool in sharePoolOptions"
          :key="pool.key"
          :model-value="selectedSharePools.includes(pool.key)"
          :disabled="!sharePoolHasRecords(pool.storeKey)"
          @change="(val) => toggleSharePool(pool.key, val)"
        >
          <span class="share-pool-name">{{ pool.label }}</span>
          <span v-if="!sharePoolHasRecords(pool.storeKey)" class="share-pool-empty">（无记录）</span>
        </el-checkbox>
      </div>
      <template #footer>
        <el-button @click="shareDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="selectedSharePools.length === 0"
          :loading="isSharing"
          @click="confirmShare"
        >生成分享图</el-button>
      </template>
    </el-dialog>

    <!-- 「上次更新未完成」提示：查看日志 / 一键回滚 / 继续使用 -->
    <el-dialog
      v-model="updateNoticeVisible"
      :title="updateNotice.rolled_back ? '更新失败，已自动回滚' : '上次更新未完成'"
      width="560px"
    >
      <div class="update-notice">
        <p class="update-notice-text">{{ updateNoticeText }}</p>
        <p v-if="updateNotice.error" class="update-notice-error">原因：{{ updateNotice.error }}</p>
        <p class="update-notice-tip">更新日志：{{ updateNotice.updater_log }}</p>
      </div>
      <template #footer>
        <el-button @click="openUpdateLog">查看更新日志</el-button>
        <el-button v-if="updateNotice.can_rollback" type="warning" @click="rollbackUpdate">回滚到上一版本</el-button>
        <el-button type="primary" @click="dismissUpdateNotice">继续使用</el-button>
      </template>
    </el-dialog>

    <!-- 「日志」窗口：代理 / 捕获 / 日志文件这些信息都收在这里 -->
    <el-dialog v-model="logDialogVisible" title="运行状态与日志" width="620px">
      <div class="log-dialog-body">
        <div class="status-row">
          <span class="status-dot" :class="proxyReady && proxyApplied ? 'dot-ok' : 'dot-bad'"></span>
          <span class="status-label">代理</span>
          <span class="status-value">{{ proxyReady ? (proxyApplied ? `运行中（仅解密抽卡接口） 127.0.0.1:${proxyPort}` : '已启动，系统代理未接管（请先安装证书）') : '未启动' }}</span>
        </div>
        <div class="status-row">
          <span class="status-dot" :class="captureReplayable ? 'dot-ok' : 'dot-bad'"></span>
          <span class="status-label">捕获</span>
          <span class="status-value">{{ captureText }}</span>
        </div>
        <div class="status-row">
          <span class="status-dot" :class="logPath ? 'dot-ok' : 'dot-bad'"></span>
          <span class="status-label">日志文件</span>
          <span class="status-value status-path">{{ logPath || '（尚未生成）' }}</span>
        </div>
        <div class="status-hint">{{ statusHint }}</div>
      </div>
      <template #footer>
        <el-button type="primary" @click="openLogFile">打开日志文件</el-button>
      </template>
    </el-dialog>
  </el-container>
  
</template>

  
<script setup>
  import {ref, computed, watch, onMounted, onUnmounted, nextTick} from 'vue'
  import {Loading, Share} from '@element-plus/icons-vue'
  import GachaItem from './components/GachaItem.vue'
  import {ElMessage, ElMessageBox} from 'element-plus'
  import html2canvas from 'html2canvas'
  import {useGachaRecordStore} from '@/stores/gachaRecord'
  import {useSSRStore} from '@/stores/ssr'
  import versionInfo from '@/../../version.json'
  import {waitForApi, withTimeout} from './utils/bridge'


  const gachaRecordStore = useGachaRecordStore()
  const ssrStore = useSSRStore()

  const recordList = ref([])
  const selectedRecordId = ref('')
  const currentVersion = ref(versionInfo.current_version)
  const isUpdating = ref(false)
  const isLoading = ref(true)
  const isCustomPurchaseOn = ref(false)
  const isSharing = ref(false)
  const screenshotContainerRef = ref(null)

  // ---------------- 分享：选择要分享的卡池 ----------------
  // 顺序与主界面一致；勾选只影响出图，不影响主界面显示（和「自选采购」开关互不干扰）
  const sharePoolOptions = [
    { key: 'character', label: '角色池', storeKey: 'character_pool' },
    { key: 'weapon', label: '武器池', storeKey: 'weapon_pool' },
    { key: 'permanent', label: '常驻池', storeKey: 'permanent_pool' },
    { key: 'custom_character', label: '自选角色池', storeKey: 'custom_character_pool' },
    { key: 'custom_weapon', label: '自选武器池', storeKey: 'custom_weapon_pool' },
  ]
  const shareDialogVisible = ref(false)
  const selectedSharePools = ref([])

  const sharePoolHasRecords = (storeKey) => {
    const pages = (gachaRecordStore.gacha || {})[storeKey] || []
    return Array.isArray(pages) && pages.some((page) => ((page || {}).data || {}).list?.length > 0)
  }

  const sharePoolChecked = (key) => selectedSharePools.value.includes(key)

  const toggleSharePool = (key, checked) => {
    if (checked) {
      if (!selectedSharePools.value.includes(key)) selectedSharePools.value.push(key)
    } else {
      selectedSharePools.value = selectedSharePools.value.filter((item) => item !== key)
    }
    // 保持固定顺序（角色/武器/常驻/自选角色/自选武器）
    const order = sharePoolOptions.map((pool) => pool.key)
    selectedSharePools.value.sort((a, b) => order.indexOf(a) - order.indexOf(b))
  }

  // 点「分享」：先弹选择框，默认只勾有记录的池子；没有任何记录时直接提示
  const openShareDialog = () => {
    const withRecords = sharePoolOptions.filter((pool) => sharePoolHasRecords(pool.storeKey))
    if (withRecords.length === 0) {
      ElMessage.warning('还没有抽卡记录，先点「更新记录」或导入一份记录吧')
      return
    }
    selectedSharePools.value = withRecords.map((pool) => pool.key)
    shareDialogVisible.value = true
  }

  const confirmShare = async () => {
    if (selectedSharePools.value.length === 0) return
    shareDialogVisible.value = false
    await shareScreenshot()
  }

  // 将 html2canvas 暴露到全局，供后端 evaluate_js 调用
  window.html2canvas = html2canvas

  // ---------------- 分享图标预热 ----------------
  // 分享慢的根源是要把每张五星图标下载成 base64（图床没有 CORS 头，画进 canvas
  // 会被跨域污染，所以只能由 Python 下载）。这里在数据一到位时就把图标交给后端
  // 后台缓存，用户点「分享」时基本就是纯本地操作了。
  let prefetchTimer = null
  const prefetchShareIcons = () => {
    clearTimeout(prefetchTimer)
    prefetchTimer = setTimeout(async () => {
      if (!(await waitForApi())) return
      try {
        await nextTick()
        const urls = Array.from(document.querySelectorAll('.screenshot-container img'))
          .map((img) => img.getAttribute('src'))
          .filter((src) => src && src.startsWith('http'))
        if (!urls.length) return
        const res = await window.pywebview.api.prefetch_share_images(urls)
        console.log('[分享] 图标预热:', res && res.msg)
      } catch (e) {
        console.error('[分享] 图标预热失败:', e)
      }
    }, 1200)
  }
  watch(() => gachaRecordStore.gacha, () => prefetchShareIcons())

  // ---------------- 代理 / 捕获状态 ----------------
  // 「更新记录」只是重放上一次抓到的游戏请求，所以界面上必须能看出来
  // 代理有没有起来、有没有抓到过请求，否则用户只会看到一句没头没尾的失败。
  const proxyReady = ref(false)
  const proxyApplied = ref(false)
  const proxyError = ref('')
  const proxyPort = ref(null)
  const captureInfo = ref({})
  const lastSeenCapture = ref('')
  const logDialogVisible = ref(false)
  const logPath = ref('')
  let statusTimer = null

  const captureReplayable = computed(() => !!captureInfo.value.replayable)

  const captureText = computed(() => {
    const info = captureInfo.value || {}
    if (!info.exists || !info.size) {
      return '尚未捕获（先在游戏里打开「招募 · 访问详情」页面）'
    }
    if (!info.has_authorization) {
      return '捕获异常：缺少 Authorization'
    }
    const time = (info.captured_at || '').substring(11, 19)
    const age = info.age_text ? `（${info.age_text}）` : ''
    return `已捕获 ${time}${age}`
  })

  const statusHint = computed(() => {
    if (!proxyReady.value) {
      return '代理未启动，游戏请求不会被捕获，请重启本工具'
    }
    if (!proxyApplied.value) {
      return proxyError.value
        ? `系统代理未接管：${proxyError.value}`
        : '代理已启动，但系统代理未接管；请先安装证书'
    }
    if (!captureReplayable.value) {
      return '打开游戏 → 进入「招募 · 访问详情」页面，然后点『更新记录』'
    }
    if (captureInfo.value.stale) {
      return '这份请求比较旧，更新失败时请在游戏里重开一次「招募 · 访问详情」页面'
    }
    return '可以直接点『更新记录』了'
  })

  // 等 pywebview 注入 api（页面脚本有时比后端就绪更早）
  let disposed = false
  let statusPending = false

  const applyStatus = (res, notify) => {
    if (!res || res.status !== 'success') return
    proxyReady.value = !!(res.proxy && res.proxy.ready)
    proxyApplied.value = !!(res.proxy && res.proxy.system_proxy)
    proxyError.value = (res.proxy && res.proxy.error) || ''
    proxyPort.value = res.proxy ? res.proxy.port : null
    captureInfo.value = res.capture || {}
    logPath.value = res.log_path || ''

    const stamp = captureInfo.value.captured_at || ''
    if (notify && stamp && lastSeenCapture.value && stamp !== lastSeenCapture.value) {
      ElMessage.success('已捕获到游戏抽卡请求，现在可以点「更新记录」了')
    }
    if (stamp) lastSeenCapture.value = stamp
  }

  const refreshStatus = async (notify = true) => {
    if (disposed || statusPending) return
    statusPending = true
    try {
      if (!(await waitForApi()) || disposed) return
      const result = await withTimeout(window.pywebview.api.get_capture_status())
      if (!disposed) applyStatus(result, notify)
    } catch (e) {
      console.error('[ERROR] 获取状态失败:', e)
    } finally {
      statusPending = false
    }
  }

  // 打开「日志」窗口：顺带刷新一次状态，保证看到的是最新的
  const openLogDialog = () => {
    logDialogVisible.value = true
    refreshStatus(false)
  }

  // 用系统默认程序直接打开日志文件本身
  const openLogFile = async () => {
    if (!(await waitForApi())) return
    try {
      const res = await window.pywebview.api.open_log_file()
      if (!res || res.status !== 'success') {
        ElMessage.error((res && res.msg) || '打开日志文件失败')
      }
    } catch (e) {
      ElMessage.error(`打开日志文件失败: ${e.message || e}`)
    }
  }


  // 显示更新通知（远端 version.json 里带 update_info 时一并展示更新说明）
  const showUpdateNotification = (latestVersion, notes = '') => {
    const detail = notes ? `\n\n更新内容：\n${notes}` : ''
    ElMessageBox.confirm(
      `发现新版本 v${latestVersion}，是否更新？${detail}`,
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
    if (!(await waitForApi()) || disposed) return

    try {
      const res = await withTimeout(window.pywebview.api.get_record_list())
      if (disposed) return
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

  // ---------------- 上次更新未完成的提示 ----------------
  const updateNoticeVisible = ref(false)
  const updateNotice = ref({})
  const updateNoticeText = computed(() => {
    const n = updateNotice.value || {}
    const from = n.from ? `v${n.from}` : '旧版本'
    const to = n.to ? `v${n.to}` : '新版本'
    if (n.rolled_back) {
      return `上次更新（${from} → ${to}）失败，已经自动回滚到 ${from}，当前可以正常使用。`
    }
    return `上次更新（${from} → ${to}）没有正常完成，当前程序仍然可以使用。`
  })

  const checkUpdateStatus = async () => {
    if (!(await waitForApi())) return
    let st = null
    try {
      // 必须"先读状态"，读完再让后端收尾（mark_update_ok 会把状态改成 ok，
      // 顺序反了这条提示就永远弹不出来）
      st = await withTimeout(window.pywebview.api.get_update_status())
    } catch (e) {
      console.error('[ERROR] 读取更新状态失败:', e)
      return
    }
    if (!st || !st.needs_attention) return
    updateNotice.value = st
    updateNoticeVisible.value = true
  }

  const openUpdateLog = () => {
    window.pywebview.api.open_log_file('updater')
  }

  const dismissUpdateNotice = async () => {
    updateNoticeVisible.value = false
    try {
      await window.pywebview.api.dismiss_update_status()
    } catch (e) {
      console.error('[ERROR] 忽略更新状态失败:', e)
    }
  }

  // 一键回滚：后端会拉起 updater.exe --rollback 并关掉本程序
  const rollbackUpdate = async () => {
    try {
      await ElMessageBox.confirm(
        '将回滚到上一个版本并自动重新启动程序，确定吗？',
        '回滚确认',
        { confirmButtonText: '回滚', cancelButtonText: '取消', type: 'warning' }
      )
    } catch (e) {
      return
    }
    updateNoticeVisible.value = false
    try {
      const res = await window.pywebview.api.rollback_update()
      if (!res || res.status !== 'success') {
        ElMessage.error((res && res.msg) || '启动回滚失败')
      }
    } catch (e) {
      ElMessage.error(`启动回滚失败: ${e.message || e}`)
    }
  }

  // 手动检查更新
  const checkUpdate = async () => {
    try {
      const res = await window.pywebview.api.get_version_info()
      if (res.status == 'success') {
        currentVersion.value = res.current_version
        if (res.has_update) {
          showUpdateNotification(res.latest_version, res.notes)
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
    // 先确认本地有一份「可重放」的捕获：没有就直接告诉用户该做什么，
    // 而不是让他等一句和网络故障长得一模一样的失败提示
    await refreshStatus(false)
    if (!captureReplayable.value) {
      ElMessage.warning(statusHint.value)
      return
    }

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
          console.error('[ERROR] 获取记录失败:', res.code, res.msg)
          ElMessage.error(res.msg)
          // 失败原因可能来自 token 过期 / 接口变动，刷新状态让用户看到最新情况
          refreshStatus(false)
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

  // 分享截图功能
  const shareScreenshot = async () => {
    if (!screenshotContainerRef.value) {
      ElMessage.error('截图容器未就绪')
      return
    }

    isSharing.value = true

    try {
      await nextTick()
      // 截图和剪贴板操作全部由后端通过 evaluate_js 完成（避免大数据通过 api 参数被截断）
      const res = await window.pywebview.api.copy_image_to_clipboard()
      if (res && res.status === 'success') {
        ElMessage.success('截图已复制到剪贴板，可直接粘贴使用')
      } else {
        ElMessage.error(`复制失败: ${res?.message || '未知错误'}`)
      }
    } catch (e) {
      console.error('[ERROR] 截图失败:', e)
      ElMessage.error(`截图失败: ${e.message || e}`)
    } finally {
      isSharing.value = false
    }
  }

  // 后台刷新结束后按最终来源提示；内置表只用于让页面先显示。
  watch(() => [ssrStore.source, ssrStore.isRefreshing], ([source, refreshing]) => {
    if (disposed || refreshing) return
    if (source === 'local-proto') {
      ElMessage.success('正在使用最新五星数据')
    } else if (source === 'remote') {
      ElMessage.success('正在使用远端五星数据')
    } else if (source === 'local-json') {
      ElMessage.warning('正在使用本地五星数据(可能不是最新)')
    } else if (source === 'error') {
      ElMessage.error('无法加载五星数据')
    }
  })

  // 组件挂载时加载数据
  onMounted(async () => {
    // 无论初始化成功还是失败，都必须把遮罩关掉，否则界面会一直转圈没法用
    let source = 'error'
    try {
      // 加载记录列表
      loadRecordList()

      // 状态轮询：代理是否就绪 / 有没有抓到游戏请求
      refreshStatus(false)
      statusTimer = setInterval(() => refreshStatus(true), 3000)

      // 加载SSR数据（前端主动控制）
      source = await ssrStore.loadData()
    } catch (e) {
      console.error('[ERROR] 初始化失败:', e)
      ElMessage.error(`初始化失败: ${e.message || e}`)
    } finally {
      // 关闭遮罩
      isLoading.value = false
      // 上次更新没走完的话先提示用户（必须排在收尾之前，否则状态会被改成 ok）
      await checkUpdateStatus()
      // 界面确实起来了 -> 通知后端收尾更新流程（写 ok + 清理回滚备份/临时文件）
      try {
        await withTimeout(window.pywebview.api.mark_update_ok(), 10000)
      } catch (e) {
        console.error('[ERROR] 收尾更新流程失败:', e)
      }
    }
    
    if (source === 'error' && !ssrStore.isRefreshing) {
      ElMessage.error('无法加载五星数据')
    }
  })

  onUnmounted(() => {
    disposed = true
    if (statusTimer) clearInterval(statusTimer)
    clearTimeout(prefetchTimer)
    ssrStore.stopRefresh()
  })

</script>
  
<style scoped>
  /* 固定顶部栏：半透白 + 高斯模糊（磨砂质感）+ 一条细微下阴影 */
  .app-header{
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 1000;
    height: 64px;
    padding: 0 20px;
    box-sizing: border-box;
    display: flex;
    justify-content: space-between;
    align-items: center;          /* 这一行在顶栏里上下居中 */

    background: rgba(255, 255, 255, 0.72);
    -webkit-backdrop-filter: blur(14px) saturate(180%);
    backdrop-filter: blur(14px) saturate(180%);
    border-bottom: 1px solid rgba(255, 255, 255, 0.6);
    box-shadow:
      0 1px 0 rgba(0, 0, 0, 0.03),
      0 4px 16px rgba(0, 0, 0, 0.06);
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
  .log-dialog-body {
    display: flex;
    flex-direction: column;
    gap: 12px;
    font-size: 14px;
    color: #303133;
  }
  .status-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .status-label {
    color: #909399;
    width: 72px;
    flex: none;
  }
  .status-value {
    word-break: break-all;
  }
  .status-path {
    color: #606266;
    font-size: 13px;
  }
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
  }
  .dot-ok {
    background: #67c23a;
  }
  .dot-bad {
    background: #f56c6c;
  }
  .status-hint {
    color: #909399;
    line-height: 1.6;
    padding-top: 4px;
    border-top: 1px solid #ebeef5;
  }
  .app-main{
    /* background-color: blue; */
    height: 100%;
    /* 顶栏是 fixed 的，这里补上它占掉的高度，避免内容被压在栏下面 */
    padding-top: 84px;
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

  /* 离屏截图容器样式 */
  .screenshot-container {
    position: fixed;
    left: -9999px;
    top: 0;
    width: auto;
    background: #ffffff;
    padding: 20px 24px;
    z-index: -1;
  }

  .screenshot-pools-row {
    display: flex;
    gap: 16px;
    align-items: flex-start;
  }

  .screenshot-pool-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 280px;
    max-width: 320px;
    flex: 1;
  }

  .update-notice p {
    margin: 0 0 10px;
    line-height: 1.7;
    font-size: 14px;
    color: #303133;
  }
  .update-notice-error {
    color: #f56c6c;
  }
  .update-notice-tip {
    color: #909399;
    font-size: 12.5px;
    word-break: break-all;
  }
  .share-pool-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .share-pool-name {
    font-size: 14px;
  }
  .share-pool-empty {
    color: #c0c4cc;
    font-size: 12px;
    margin-left: 4px;
  }
  .screenshot-pool-title {
    font-size: 18px;
    font-weight: bold;
    color: #303133;
    margin-bottom: 8px;
  }
</style>

<!-- 全局样式：不能加 scoped，否则选择器会变成 html[data-v-xxx]，匹配不到 html/body -->
<style>
  /* 去掉窗口右侧的系统默认滚动条（WebView2 / Chromium）。
     滚动本身仍然可用，只是不再显示那条灰条 */
  html,
  body {
    scrollbar-width: none;      /* 新版 Chromium / Firefox */
    -ms-overflow-style: none;   /* 旧 Edge */
  }
  html::-webkit-scrollbar,
  body::-webkit-scrollbar,
  *::-webkit-scrollbar {
    width: 0 !important;
    height: 0 !important;
    display: none !important;
  }
</style>
