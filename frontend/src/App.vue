<template>
  <div class="app-shell">
    <!-- 自绘窗口标题栏 -->
    <header class="window-titlebar">
      <div class="window-titlebar-drag pywebview-drag-region">
        <img class="window-titlebar-logo" :src="appIconUrl" alt="" aria-hidden="true">
        <span class="window-titlebar-title">夏克里助手</span>
        <span class="window-titlebar-sub">XKL // DESKTOP TERMINAL</span>
      </div>
      <div class="window-controls" aria-label="窗口控制">
        <button type="button" class="window-control" aria-label="最小化" title="最小化" @click="windowControl('window_minimize')">
          <AppIcon name="window-minimize" :size="13" />
        </button>
        <button type="button" class="window-control" :aria-label="windowMaximized ? '还原' : '最大化'" :title="windowMaximized ? '还原' : '最大化'" @click="windowControl('window_toggle_maximize')">
          <AppIcon :name="windowMaximized ? 'window-restore' : 'window-maximize'" :size="12" />
        </button>
        <button type="button" class="window-control window-control--close" aria-label="关闭" title="关闭" @click="windowControl('window_close')">
          <AppIcon name="close" :size="14" />
        </button>
      </div>
    </header>

    <!-- 全屏加载遮罩 -->
    <div v-if="isLoading" class="loading-overlay">
      <div class="loading-content">
        <span class="app-spinner spinner-big" />
        <span class="loading-text">正在加载角色数据...</span>
      </div>
    </div>

    <!-- 侧边导航 -->
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark"><img :src="appIconUrl" alt="夏克里助手 Logo"></div>
        <div class="brand-text">
          <div class="brand-name">夏克里助手</div>
          <div class="brand-sub">GF2 // ARCHIVE UNIT</div>
        </div>
      </div>
      <div class="nav-label">TACTICAL MENU</div>
      <nav class="side-nav">
        <button type="button" class="nav-item" :class="{ active: view === 'overview' }" @click="view = 'overview'">
          <AppIcon name="grid" :size="16" />
          <span class="nav-copy"><strong>总览</strong><small>OVERVIEW</small></span>
          <span class="nav-index">01</span>
        </button>
        <button type="button" class="nav-item" :class="{ active: view === 'tools' }" @click="switchToTools">
          <AppIcon name="tool" :size="16" />
          <span class="nav-copy"><strong>工具</strong><small>SYSTEMS</small></span>
          <span class="nav-index">02</span>
        </button>
        <button type="button" class="nav-item" :class="{ active: view === 'community' }" @click="switchToCommunity">
          <AppIcon name="gift" :size="16" />
          <span class="nav-copy"><strong>社区</strong><small>COMMUNITY</small></span>
          <span class="nav-index">03</span>
        </button>
      </nav>
      <div class="side-footer">
        <div class="side-status">
          <span class="app-dot" :class="statusDotClass" />
          <span>{{ statusShort }}</span>
        </div>
        <div class="side-meta"><span>v{{ currentVersion }}</span><span>LOCAL AUTH</span></div>
      </div>
    </aside>

    <!-- 主列：顶栏 + 内容 -->
    <div class="main-col">
      <header class="topbar">
        <div class="topbar-left">
          <div class="archive-code"><span>ARCHIVE</span><strong>01</strong></div>
          <div class="record-field">
            <span class="record-label">抽卡记录 / DRAW LOG</span>
            <AppSelect
              v-model="selectedRecordId"
              :options="recordList"
              placeholder="选择抽卡记录"
              @change="onRecordChange"
            />
          </div>
        </div>
        <div class="topbar-right">
          <AppButton variant="primary" :loading="isUpdating" @click="updateRecord">
            <AppIcon name="refresh" :size="14" />
            更新记录
          </AppButton>
          <AppButton variant="quiet" @click="switchToTools">
            <AppIcon name="key" :size="14" />
            导出到小程序
          </AppButton>
          <AppButton variant="quiet" :loading="isSharing" @click="openShareDialog">
            <AppIcon name="share" :size="14" />
            分享
          </AppButton>
          <button
            type="button"
            class="bell-btn"
            :class="{ unread: announcementUnread }"
            aria-label="查看公告"
            @click="openAnnouncement"
          >
            <AppIcon name="bell" :size="16" />
            <span v-if="announcementUnread" class="bell-badge" />
          </button>
        </div>
      </header>

      <main ref="contentRef" class="content" @scroll.passive="onContentScroll">
        <transition name="view-shift" mode="out-in">
          <!-- 总览 -->
          <section v-if="view === 'overview'" key="overview" class="view-panel">
            <div class="overview-hero">
              <div class="hero-copy">
                <div class="section-kicker"><span class="section-index">01</span> OPERATIONS / RECORD MONITOR</div>
                <h2 class="page-title">抽卡总览</h2>
                <p class="page-desc">追踪作战档案、五星获取与当前保底进度。</p>
              </div>
              <div class="hero-side">
                <div class="quick-stats" aria-label="抽卡数据摘要">
                  <div class="quick-stat"><span>记录总数</span><strong>{{ overviewStats.draws }}</strong><small>DRAWS</small></div>
                  <div class="quick-stat"><span>五星记录</span><strong>{{ overviewStats.ssr }}</strong><small>SSR</small></div>
                  <div class="quick-stat"><span>活跃卡池</span><strong>{{ overviewStats.activePools }}</strong><small>POOLS</small></div>
                </div>
                <div class="display-mode-wrap">
                  <span>DISPLAY MODE</span>
                  <div class="display-mode-switch" role="group" aria-label="抽卡显示模式">
                    <button type="button" :class="{ active: homeMode === 'records' }" :aria-pressed="homeMode === 'records'" @click="homeMode = 'records'">
                      <AppIcon name="grid" :size="12" />记录
                    </button>
                    <button type="button" :class="{ active: homeMode === 'analytics' }" :aria-pressed="homeMode === 'analytics'" @click="homeMode = 'analytics'">
                      <AppIcon name="chart" :size="12" />统计
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <transition name="mode-shift" mode="out-in">
            <div v-if="homeMode === 'records'" key="records" class="home-mode-panel">
            <div class="section-bar">
              <div>
                <span class="section-kicker">02 / ARCHIVE BREAKDOWN</span>
                <h3>卡池记录</h3>
              </div>
              <div class="section-actions">
                <span class="section-status">LIVE DATA · {{ overviewStats.activePools }} ACTIVE</span>
                <button
                  type="button"
                  class="row-collapse-btn"
                  :class="{ collapsed: collapsedPoolRows.main }"
                  :aria-expanded="!collapsedPoolRows.main"
                  @click="togglePoolRow('main')"
                >
                  {{ collapsedPoolRows.main ? '展开本行' : '收起本行' }}
                  <AppIcon name="chevron-down" :size="11" class="row-collapse-icon" />
                </button>
              </div>
            </div>

            <div class="pool-grid" :class="{ 'is-collapsed': collapsedPoolRows.main }">
              <article class="pool-card">
                <header class="pool-card-head">
                  <div><span class="pool-code">POOL / 01</span><h4 class="pool-name">角色池</h4></div>
                  <span class="pool-type">CHARACTER</span>
                </header>
                <GachaItem pool_type="character" :collapsed="collapsedPoolRows.main" />
              </article>
              <article class="pool-card">
                <header class="pool-card-head">
                  <div><span class="pool-code">POOL / 02</span><h4 class="pool-name">武器池</h4></div>
                  <span class="pool-type">WEAPON</span>
                </header>
                <GachaItem pool_type="weapon" :collapsed="collapsedPoolRows.main" />
              </article>
              <article class="pool-card">
                <header class="pool-card-head">
                  <div><span class="pool-code">POOL / 03</span><h4 class="pool-name">常驻池</h4></div>
                  <span class="pool-type">STANDARD</span>
                </header>
                <GachaItem pool_type="permanent" :collapsed="collapsedPoolRows.main" />
              </article>
            </div>

            <div class="custom-pools-block">
              <div class="section-bar section-bar--compact">
                <div>
                  <span class="section-kicker">03 / CUSTOM PROCUREMENT</span>
                  <h3>自选采购记录</h3>
                </div>
                <div class="section-actions">
                  <span class="section-status">AUTO TARGETING</span>
                  <button
                    type="button"
                    class="row-collapse-btn"
                    :class="{ collapsed: collapsedPoolRows.custom }"
                    :aria-expanded="!collapsedPoolRows.custom"
                    @click="togglePoolRow('custom')"
                  >
                    {{ collapsedPoolRows.custom ? '展开本行' : '收起本行' }}
                    <AppIcon name="chevron-down" :size="11" class="row-collapse-icon" />
                  </button>
                </div>
              </div>
              <div class="pool-grid pool-grid--two" :class="{ 'is-collapsed': collapsedPoolRows.custom }">
                <article class="pool-card">
                  <header class="pool-card-head">
                    <div><span class="pool-code">POOL / C1</span><h4 class="pool-name">自选角色池</h4></div>
                    <span class="pool-type">TARGET</span>
                  </header>
                  <GachaItem pool_type="custom_character" :collapsed="collapsedPoolRows.custom" />
                </article>
                <article class="pool-card">
                  <header class="pool-card-head">
                    <div><span class="pool-code">POOL / C2</span><h4 class="pool-name">自选武器池</h4></div>
                    <span class="pool-type">TARGET</span>
                  </header>
                  <GachaItem pool_type="custom_weapon" :collapsed="collapsedPoolRows.custom" />
                </article>
              </div>
            </div>
            </div>

            <div v-else key="analytics" class="home-mode-panel analytics-mode">
              <div class="section-bar">
                <div>
                  <span class="section-kicker">02 / COMBAT STATISTICS</span>
                  <h3>卡池统计</h3>
                </div>
                <span class="section-status">RARITY ANALYSIS · {{ analyticsPools.length }} POOLS</span>
              </div>
              <div class="analytics-grid">
                <PoolAnalytics v-for="pool in analyticsPools" :key="pool.key" :pool="pool" />
              </div>
            </div>
            </transition>
          </section>
          <!-- 工具 -->
          <section v-else-if="view === 'tools'" key="tools" class="tools-view view-panel">
            <div class="tools-intro">
              <div>
                <div class="section-kicker"><span class="section-index">02</span> SYSTEMS / DIAGNOSTICS</div>
                <h2 class="page-title">工具与状态</h2>
                <p class="page-desc">检查捕获链路、导出凭证并维护本地运行环境。</p>
              </div>
              <div class="system-ready">
                <span class="app-dot" :class="statusDotClass" />
                <div><strong>{{ statusShort }}</strong><small>SYSTEM STATUS</small></div>
              </div>
            </div>
            <div class="tools-grid">          <div class="tool-card">
            <div class="tool-head">
              <AppIcon name="key" :size="16" class="tool-icon" />
              <h3>小程序导入钥匙</h3>
            </div>
            <p class="tool-desc">
              把当前捕获的游戏凭证导出成 XKL1 钥匙，在微信小程序「夏克里助手」→ 抽卡分析
              里粘贴导入。钥匙是短期凭证，导入完成后不要保存。
            </p>
            <div class="key-grid">
              <div class="key-field">
                <span class="key-label">捕获状态</span>
                <span class="key-value">{{ keyCaptureText }}</span>
              </div>
              <div class="key-field">
                <span class="key-label">游戏渠道</span>
                <span class="key-value">{{ keyStatus?.channel_label || '—' }}</span>
              </div>
              <div class="key-field">
                <span class="key-label">凭证有效期</span>
                <span class="key-value" :class="{ expired: keyStatus?.expired }">{{ keyStatus?.remaining_text || '未知' }}</span>
              </div>
            </div>
            <div v-if="keyStatus?.needs_manual_uid && keyReady" class="key-uid-row">
              <label class="key-label" for="key-uid-input">B服钥匙需要补填游戏 UID（游戏内个人信息页可见）</label>
              <input
                id="key-uid-input"
                v-model="keyUidInput"
                class="app-input"
                placeholder="游戏 UID（4-32 位数字）"
                inputmode="numeric"
                maxlength="32"
              />
            </div>
            <div class="tool-actions">
              <AppButton size="sm" variant="ghost" :loading="keyStatusLoading" @click="refreshKeyStatus">
                <AppIcon name="refresh" :size="13" />
                刷新状态
              </AppButton>
              <AppButton size="sm" variant="primary" :loading="keyVerifying" :disabled="!keyReady" @click="startExportKey">
                生成导出钥匙
              </AppButton>
            </div>
          </div>

          <!-- 运行状态 -->
          <div class="tool-card">
            <div class="tool-head">
              <span class="app-dot" :class="statusDotClass" />
              <h3>运行状态</h3>
            </div>
            <div class="status-rows">
              <div class="status-row">
                <span class="status-label">代理</span>
                <span class="status-value">{{ proxyStatusText }}</span>
              </div>
              <div class="status-row">
                <span class="status-label">捕获</span>
                <span class="status-value">{{ captureText }}</span>
              </div>
              <div class="status-row">
                <span class="status-label">日志文件</span>
                <span class="status-value status-path">{{ logPath || '（尚未生成）' }}</span>
              </div>
              <div class="status-hint">{{ statusHint }}</div>
            </div>
            <div class="tool-actions">
              <AppButton size="sm" variant="quiet" @click="openLogFile">
                <AppIcon name="external" :size="13" />
                打开日志文件
              </AppButton>
            </div>
          </div>

          <!-- 抓包证书 -->
          <div class="tool-card">
            <div class="tool-head">
              <AppIcon name="shield" :size="16" class="tool-icon" />
              <h3>抓包证书</h3>
            </div>
            <p class="tool-desc">安装一次本工具生成的专属证书，游戏流量才能被解密捕获；卸载会移除证书并解除系统代理。</p>
            <div class="tool-actions">
              <AppButton size="sm" variant="quiet" @click="installCert">安装证书</AppButton>
              <AppButton size="sm" variant="danger" @click="uninstallCert">卸载证书</AppButton>
            </div>
          </div>

          <!-- 版本 -->
          <div class="tool-card">
            <div class="tool-head">
              <h3>版本</h3>
            </div>
            <div class="status-rows">
              <div class="status-row">
                <span class="status-label">当前版本</span>
                <span class="status-value">v{{ currentVersion }}</span>
              </div>
            </div>
            <div class="tool-actions">
              <AppButton size="sm" variant="quiet" @click="checkUpdate">
                <AppIcon name="refresh" :size="13" />
                检查更新
              </AppButton>
              <AppButton size="sm" variant="ghost" @click="openGitHub">
                <AppIcon name="github" :size="13" />
                GitHub 主页
              </AppButton>
            </div>
          </div>
            </div>
          </section>

          <!-- 社区 -->
          <section v-else key="community" class="tools-view view-panel">
            <div class="tools-intro">
              <div>
                <div class="section-kicker"><span class="section-index">03</span> COMMUNITY / DAILY OPS</div>
                <h2 class="page-title">社区日常</h2>
                <p class="page-desc">复用游戏凭证登录社区，一键完成签到、每日任务与积分兑换。</p>
              </div>
              <div class="system-ready">
                <span class="app-dot" :class="communityDotClass" />
                <div><strong>{{ communityStatusText }}</strong><small>COMMUNITY LINK</small></div>
              </div>
            </div>

            <div class="tools-grid community-grid">
              <!-- 账号 / 一键 -->
              <div class="tool-card is-wide">
                <div class="tool-head">
                  <AppIcon name="gift" :size="16" class="tool-icon" />
                  <h3>社区账号</h3>
                </div>
                <div v-if="community?.bound" class="status-rows status-rows--inline">
                  <div class="status-row">
                    <span class="status-label">昵称</span>
                    <span class="status-value">{{ community.nick_name || '—' }}</span>
                  </div>
                  <div class="status-row">
                    <span class="status-label">积分</span>
                    <span class="status-value">{{ community.score ?? '—' }}</span>
                  </div>
                  <div class="status-row">
                    <span class="status-label">等级</span>
                    <span class="status-value">{{ community.level ?? '—' }}（{{ community.exp ?? 0 }} 经验）</span>
                  </div>
                  <div class="status-row">
                    <span class="status-label">令牌有效期</span>
                    <span class="status-value" :class="{ expired: communityTokenExpired }">{{ community.token_exp }}</span>
                  </div>
                  <div class="status-row">
                    <span class="status-label">今日签到</span>
                    <span class="status-value">{{ community.signed_in ? '已签到' : '未签到' }}</span>
                  </div>
                </div>
                <p v-else class="tool-desc">
                  {{ community?.message || '尚未绑定：先在游戏里打开「招募 · 访问详情」并点一次「更新记录」，再点「绑定社区」。' }}
                </p>
                <div class="tool-actions">
                  <template v-if="community?.bound">
                    <AppButton size="sm" variant="ghost" :loading="communityLoading" @click="refreshCommunity(true)">
                      <AppIcon name="refresh" :size="13" />
                      刷新状态
                    </AppButton>
                    <AppButton
                      size="sm"
                      variant="quiet"
                      :loading="communityBinding"
                      title="用当前游戏凭证换一张新票；换游戏账号时用"
                      @click="bindCommunity"
                    >
                      重新绑定
                    </AppButton>
                  </template>
                  <AppButton v-else size="sm" variant="primary" :loading="communityBinding" @click="bindCommunity">
                    绑定社区
                  </AppButton>
                  <AppButton
                    size="sm"
                    variant="primary"
                    :loading="communityRunning"
                    :disabled="!community?.bound"
                    @click="communityOneClick"
                  >
                    一键签到 + 任务 + 兑换
                  </AppButton>
                </div>
              </div>

              <!-- 每日任务 -->
              <div class="tool-card">
                <div class="tool-head">
                  <h3>每日任务</h3>
                </div>
                <div class="status-rows status-rows--split">
                  <div v-for="task in communityTasks" :key="task.task_name" class="status-row">
                    <span class="status-label">{{ task.task_name }}</span>
                    <span class="status-value">{{ task.complete_count }}/{{ task.max_complete_count }}</span>
                  </div>
                  <div v-if="!communityTasks.length" class="status-hint">绑定后显示任务进度</div>
                </div>
                <p class="tool-desc">浏览 3 次、点赞 3 次、分享 1 次；动作即计数，没有领取按钮。</p>
              </div>

              <!-- 兑换 -->
              <div class="tool-card">
                <div class="tool-head">
                  <h3>积分兑换</h3>
                </div>
                <div class="status-rows status-rows--split">
                  <div v-for="item in communityExchange" :key="item.exchange_id" class="status-row">
                    <span class="status-label">{{ item.item_name }} ×{{ item.item_count }}</span>
                    <span class="status-value">需 {{ item.use_score }} 分 · 已换 {{ item.exchange_count }}/{{ item.max_exchange_count }}</span>
                  </div>
                  <div v-if="!communityExchange.length" class="status-hint">绑定后显示兑换清单</div>
                </div>
                <p class="tool-desc">
                  一键兑换顺序：基原信息核 → 情报拼图 ×2 → 萨狄斯金 → 战场报告 → 解析图纸；积分不够或兑换次数用完会自动跳过。
                </p>
              </div>

              <!-- 最近一次执行：执行中也要占位，避免卡片出现/消失导致网格重排 -->
              <div v-if="communityRunning || communitySteps.length" class="tool-card is-wide">
                <div class="tool-head">
                  <h3>最近一次执行</h3>
                </div>
                <div class="status-rows status-rows--inline">
                  <div v-if="communityRunning" class="status-row">
                    <span class="status-label">进行中</span>
                    <span class="status-value">正在签到 / 做任务 / 兑换，请稍候…</span>
                  </div>
                  <div v-for="(step, index) in communitySteps" :key="index" class="status-row">
                    <span class="status-label">{{ step.name }}</span>
                    <span class="status-value" :class="{ expired: step.status === 'error' }">{{ step.message }}</span>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </transition>
        <transition name="backtop">
          <button v-if="showBackToTop && view === 'overview'" type="button" class="back-to-top" aria-label="回到顶部" title="回到顶部" @click="scrollOverviewToTop">
            <AppIcon name="chevron-down" :size="14" />
            <span>TOP</span>
          </button>
        </transition>
      </main>
    </div>

    <!-- 离屏截图容器（用于生成分享图片，保持浅色样式） -->
    <div ref="screenshotContainerRef" class="screenshot-container" :class="{ 'is-analytics-share': shareStyle === 'analytics' }">
      <div v-show="shareStyle === 'records'" class="share-record-layout">
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

      <div v-show="shareStyle === 'analytics'" class="share-analytics-layout">
        <header class="share-report-head">
          <div class="share-report-brand"><span>XKL</span> / FIELD RECORD ANALYSIS</div>
          <div class="share-report-title">抽卡统计报告</div>
          <div class="share-report-meta">
            <span>卡池 {{ shareAnalyticsSummary.pools }}</span>
            <span>累计 {{ shareAnalyticsSummary.total }} 抽</span>
            <span>五星 {{ shareAnalyticsSummary.ssr }}</span>
          </div>
        </header>
        <div class="share-analytics-grid">
          <PoolAnalytics v-for="pool in shareAnalyticsPools" :key="pool.key" :pool="pool" />
        </div>
      </div>
    </div>

    <!-- 分享：先勾选要分享的卡池，再出图 -->
    <AppDialog v-model="shareDialogVisible" title="生成分享图" width="500px">
      <div class="share-style-section">
        <span class="share-section-label">分享样式 / SHARE STYLE</span>
        <div class="share-style-options">
          <button type="button" class="share-style-option" :class="{ active: shareStyle === 'records' }" @click="shareStyle = 'records'">
            <AppIcon name="grid" :size="15" />
            <span><strong>记录视图</strong><small>卡池详情与五星记录</small></span>
          </button>
          <button type="button" class="share-style-option" :class="{ active: shareStyle === 'analytics' }" @click="shareStyle = 'analytics'">
            <AppIcon name="chart" :size="15" />
            <span><strong>统计视图</strong><small>星级分布与作战指标</small></span>
          </button>
        </div>
      </div>
      <span class="share-section-label share-section-label--pools">选择卡池 / POOLS</span>
      <div class="share-pool-list">
        <AppCheck
          v-for="pool in sharePoolOptions"
          :key="pool.key"
          :model-value="selectedSharePools.includes(pool.key)"
          :disabled="!sharePoolHasRecords(pool.storeKey)"
          @change="(val) => toggleSharePool(pool.key, val)"
        >
          <span class="share-pool-name">{{ pool.label }}</span>
          <span v-if="!sharePoolHasRecords(pool.storeKey)" class="share-pool-empty">（无记录）</span>
        </AppCheck>
      </div>
      <template #footer>
        <AppButton variant="quiet" @click="shareDialogVisible = false">取消</AppButton>
        <AppButton
          variant="primary"
          :disabled="selectedSharePools.length === 0"
          :loading="isSharing"
          @click="confirmShare"
        >生成分享图</AppButton>
      </template>
    </AppDialog>

    <!-- 上次更新未完成：查看日志 / 一键回滚 / 继续使用 -->
    <AppDialog
      v-model="updateNoticeVisible"
      :title="updateNotice.rolled_back ? '更新失败，已自动回滚' : '上次更新未完成'"
      width="540px"
      :close-on-click-outside="false"
    >
      <div class="update-notice">
        <p class="update-notice-text">{{ updateNoticeText }}</p>
        <p v-if="updateNotice.error" class="update-notice-error">原因：{{ updateNotice.error }}</p>
        <p class="update-notice-tip">更新日志：{{ updateNotice.updater_log }}</p>
      </div>
      <template #footer>
        <AppButton variant="quiet" @click="openUpdateLog">查看更新日志</AppButton>
        <AppButton v-if="updateNotice.can_rollback" variant="danger" @click="rollbackUpdate">回滚到上一版本</AppButton>
        <AppButton variant="primary" @click="dismissUpdateNotice">继续使用</AppButton>
      </template>
    </AppDialog>

    <!-- 公告：文字 + 图片，首次出现新公告时自动打开 -->
    <AppDialog v-model="announcementDialogVisible" width="680px" :show-close="false" :close-on-click-outside="false">
      <template #header>
        <div class="announcement-header">
          <div class="announcement-kicker"><span class="announcement-kicker-line"></span>ANNOUNCEMENT / 公告</div>
          <button type="button" class="announcement-close" aria-label="关闭公告" @click="announcementDialogVisible = false">
            <AppIcon name="close" :size="16" />
          </button>
          <div class="announcement-title">{{ announcement?.title || '公告' }}</div>
          <div v-if="announcementDate" class="announcement-meta">{{ announcementDate }}</div>
        </div>
      </template>
      <div class="announcement-content">
        <div v-if="announcement?.body" class="announcement-copy">{{ announcement.body }}</div>
        <div v-if="announcementImages.length" class="announcement-images">
          <img
            v-for="(image, index) in announcementImages"
            :key="`${image}-${index}`"
            class="announcement-image"
            :src="image"
            alt="公告图片"
            loading="lazy"
            @click="openLightbox(index)"
          />
        </div>
      </div>
      <template #footer>
        <AppButton variant="primary" @click="announcementDialogVisible = false">知道了</AppButton>
      </template>
    </AppDialog>

    <!-- 钥匙已核验：确认后复制（复制动作不再发网络请求） -->
    <AppDialog v-model="keyDialogVisible" title="钥匙已核验" width="460px" :close-on-click-outside="false">
      <div class="key-confirm-rows">
        <div class="status-row">
          <span class="status-label">UID</span>
          <span class="status-value">{{ keyVerified?.uid }}</span>
        </div>
        <div class="status-row">
          <span class="status-label">渠道</span>
          <span class="status-value">{{ keyVerified?.channel_label }}</span>
        </div>
        <div class="status-row">
          <span class="status-label">有效期</span>
          <span class="status-value" :class="{ expired: keyVerified?.expired }">{{ keyVerified?.remaining_text || '未知' }}</span>
        </div>
      </div>
      <p class="key-confirm-tip">
        点「复制到剪贴板」后，打开微信小程序「夏克里助手」→ 抽卡分析 → 粘贴钥匙即可导入。
        钥匙是短期凭证，导入完成后不要保存或发给他人。
      </p>
      <template #footer>
        <AppButton variant="quiet" @click="keyDialogVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="copyingKey" @click="copyKey">复制到剪贴板</AppButton>
      </template>
    </AppDialog>

    <AppLightbox v-model="lightboxVisible" v-model:index="lightboxIndex" :images="announcementImages" />
    <AppToastHost />
    <AppConfirmHost />
  </div>
</template>

<script setup>
  import {ref, computed, watch, onMounted, onUnmounted, nextTick} from 'vue'
  import GachaItem from './components/GachaItem.vue'
  import PoolAnalytics from './components/PoolAnalytics.vue'
  import html2canvas from 'html2canvas'
  import {useGachaRecordStore} from '@/stores/gachaRecord'
  import {useSSRStore} from '@/stores/ssr'
  import {useImageCacheStore} from '@/stores/imageCache'
  import versionInfo from '@/../../version.json'
  import {waitForApi, withTimeout} from './utils/bridge'
  import appIconUrl from '../public/favicon.ico'

  import AppButton from './ui/AppButton.vue'
  import AppCheck from './ui/AppCheck.vue'
  import AppDialog from './ui/AppDialog.vue'
  import AppIcon from './ui/AppIcon.vue'
  import AppLightbox from './ui/AppLightbox.vue'
  import AppSelect from './ui/AppSelect.vue'
  import AppToastHost from './ui/AppToastHost.vue'
  import AppConfirmHost from './ui/AppConfirmHost.vue'
  import {toast} from './ui/toast'
  import {confirmDialog} from './ui/confirm'

  const gachaRecordStore = useGachaRecordStore()
  const ssrStore = useSSRStore()
  const imageCacheStore = useImageCacheStore()

  const recordList = ref([])
  const selectedRecordId = ref('')
  const currentVersion = ref(versionInfo.current_version)
  const announcement = ref(null)
  const announcementDialogVisible = ref(false)
  const announcementUnread = ref(false)
  const announcementLoading = ref(false)
  const announcementImages = computed(() => {
    const images = announcement.value?.images
    return Array.isArray(images) ? images : []
  })
  const announcementDate = computed(() => {
    const timestamp = Number(announcement.value?.published_at || 0)
    if (!Number.isFinite(timestamp) || timestamp <= 0) return ''
    try {
      return new Intl.DateTimeFormat('zh-CN', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', hour12: false,
      }).format(new Date(timestamp * 1000))
    } catch (e) {
      return ''
    }
  })
  const isUpdating = ref(false)
  const isLoading = ref(true)
  const isSharing = ref(false)
  const screenshotContainerRef = ref(null)
  const windowMaximized = ref(false)
  const contentRef = ref(null)
  const showBackToTop = ref(false)
  const collapsedPoolRows = ref({ main: false, custom: false })

  // 总览摘要：按卡池去重统计展示，不改变 GachaItem 的保底计算口径
  const overviewStats = computed(() => {
    const permanent = ssrStore.SSR_permanent || {}
    const pools = [
      { records: gachaRecordStore.characterGacha, map: { ...permanent, ...(ssrStore.SSR_character || {}) } },
      { records: gachaRecordStore.weaponGacha, map: { ...permanent, ...(ssrStore.SSR_weapon || {}) } },
      { records: gachaRecordStore.permanentGacha, map: permanent },
      { records: gachaRecordStore.customCharacterGacha, map: { ...permanent, ...(ssrStore.SSR_custom_character || {}) } },
      { records: gachaRecordStore.customWeaponGacha, map: { ...permanent, ...(ssrStore.SSR_custom_weapon || {}) } },
    ]
    let draws = 0
    let ssr = 0
    let activePools = 0
    for (const pool of pools) {
      const pages = Array.isArray(pool.records) ? pool.records : []
      const list = pages.flatMap((page) => page?.data?.list || [])
      if (list.length) activePools++
      draws += list.length
      for (const draw of list) {
        if (Object.prototype.hasOwnProperty.call(pool.map, String(draw.item))) ssr++
      }
    }
    return { draws, ssr, activePools }
  })

  const analyticsPools = computed(() => {
    const permanent = ssrStore.SSR_permanent || {}
    const permanentSet = new Set(Object.keys(permanent).map(String))
    const srMap = { ...(ssrStore.SR_character || {}), ...(ssrStore.SR_weapon || {}) }
    const definitions = [
      { key: 'character', code: 'POOL / 01', label: '角色池', type: 'CHARACTER', records: gachaRecordStore.characterGacha, ssrMap: { ...permanent, ...(ssrStore.SSR_character || {}) }, isPermanent: false },
      { key: 'weapon', code: 'POOL / 02', label: '武器池', type: 'WEAPON', records: gachaRecordStore.weaponGacha, ssrMap: { ...permanent, ...(ssrStore.SSR_weapon || {}) }, isPermanent: false },
      { key: 'permanent', code: 'POOL / 03', label: '常驻池', type: 'STANDARD', records: gachaRecordStore.permanentGacha, ssrMap: permanent, isPermanent: true },
      { key: 'custom_character', code: 'POOL / C1', label: '自选角色池', type: 'TARGET', records: gachaRecordStore.customCharacterGacha, ssrMap: { ...permanent, ...(ssrStore.SSR_custom_character || {}) }, isPermanent: false },
      { key: 'custom_weapon', code: 'POOL / C2', label: '自选武器池', type: 'TARGET', records: gachaRecordStore.customWeaponGacha, ssrMap: { ...permanent, ...(ssrStore.SSR_custom_weapon || {}) }, isPermanent: false },
    ]

    return definitions.map((definition) => {
      const pages = Array.isArray(definition.records) ? definition.records : []
      const draws = pages.flatMap((page, pageIndex) =>
        (page?.data?.list || []).map((draw) => ({ ...draw, pageIndex }))
      ).sort((a, b) => {
        if (b.time !== a.time) return b.time - a.time
        return a.pageIndex - b.pageIndex
      }).map((draw, drawIndex) => ({ ...draw, drawIndex }))

      const rarity = { 5: 0, 4: 0, 3: 0 }
      for (const draw of draws) {
        const item = String(draw.item)
        if (Object.prototype.hasOwnProperty.call(definition.ssrMap, item)) rarity[5]++
        else if (Object.prototype.hasOwnProperty.call(srMap, item)) rarity[4]++
        else rarity[3]++
      }

      const ssrDraws = draws
        .filter((draw) => Object.prototype.hasOwnProperty.call(definition.ssrMap, String(draw.item)))
        .map((draw) => ({
          item: String(draw.item),
          name: definition.ssrMap[String(draw.item)],
          time: draw.time,
          drawIndex: draw.drawIndex,
          isWai: !definition.isPermanent && permanentSet.has(String(draw.item)),
        }))

      const fiveStars = ssrDraws.map((item, index) => {
        const next = ssrDraws[index + 1]
        const costDraws = next ? next.drawIndex - item.drawIndex : draws.length - item.drawIndex
        return { ...item, costDraws }
      })
      const upCount = fiveStars.filter((item) => !item.isWai).length
      const waiCount = fiveStars.filter((item) => item.isWai).length
      const expectedPulls = (hits) => hits > 0 ? (draws.length / hits).toFixed(1) : '—'

      return {
        ...definition,
        total: draws.length,
        pad: fiveStars.length ? fiveStars[0].drawIndex : draws.length,
        rarity,
        fiveStars,
        avgSSR: expectedPulls(rarity[5]),
        avgUp: definition.isPermanent ? '—' : expectedPulls(upCount),
        waiRate: definition.isPermanent ? '—' : (fiveStars.length ? ((waiCount / fiveStars.length) * 100).toFixed(1) : '0.0'),
      }
    })
  })
  // ---------------- 视图与卡池行收缩 ----------------
  const view = ref('overview')
  const onContentScroll = () => {
    showBackToTop.value = (contentRef.value?.scrollTop || 0) > 360
  }
  const scrollOverviewToTop = () => {
    contentRef.value?.scrollTo({ top: 0, behavior: 'smooth' })
  }
  const homeMode = ref('records')
  const togglePoolRow = (row) => {
    collapsedPoolRows.value[row] = !collapsedPoolRows.value[row]
  }

  // 自绘标题栏控制；浏览器预览时接口不存在则静默跳过
  const windowControl = async (method) => {
    const api = window.pywebview?.api
    if (!api || typeof api[method] !== 'function') return
    try {
      const result = await api[method]()
      if (method === 'window_toggle_maximize' && result?.status === 'success') {
        windowMaximized.value = !!result.maximized
      }
    } catch (e) {
      toast.error(`窗口操作失败: ${e.message || e}`)
    }
  }
  const switchToTools = () => {
    view.value = 'tools'
    // 状态面板的信息要新；钥匙状态是纯本地解码，顺手刷一次也不贵
    refreshStatus(false)
    if (!keyStatus.value) refreshKeyStatus()
  }

  // ---------------- 社区（签到 / 每日任务 / 兑换） ----------------
  // 令牌与请求细节都在 backend/community.py；这里只负责展示与按钮反馈。
  const community = ref(null)
  const communityLoading = ref(false)
  const communityBinding = ref(false)
  const communityRunning = ref(false)
  const communitySteps = ref([])
  const communityReady = computed(() => !!community.value?.bound)
  const communityTasks = computed(() => [
    ...(community.value?.tasks?.daily || []),
    ...(community.value?.tasks?.more || []),
  ])
  const communityExchange = computed(() => community.value?.exchange || [])
  const communityTokenExpired = computed(
    () => !!community.value?.token_exp_ts && community.value.token_exp_ts * 1000 < Date.now(),
  )
  const communityDotClass = computed(() => {
    if (!communityReady.value) return 'bad'
    return community.value?.signed_in ? 'ok' : 'warn'
  })
  const communityStatusText = computed(() => {
    if (communityLoading.value) return '读取中'
    if (!community.value) return '未连接'
    if (!communityReady.value) return '未绑定'
    return communityTokenExpired.value ? '令牌过期' : '已连接'
  })

  const refreshCommunity = async (notify = false) => {
    const api = window.pywebview?.api
    if (!api || typeof api.get_community_status !== 'function') return
    communityLoading.value = true
    try {
      const res = await withTimeout(api.get_community_status(), 20000)
      if (res?.status === 'success') {
        community.value = res.data || {}
        if (notify) toast.success('社区状态已刷新')
      } else {
        toast.error(res?.msg || '读取社区状态失败')
      }
    } catch (e) {
      toast.error(`读取社区状态失败: ${e.message || e}`)
    } finally {
      communityLoading.value = false
    }
  }

  const switchToCommunity = () => {
    view.value = 'community'
    if (!community.value && !communityLoading.value) refreshCommunity(false)
  }

  const bindCommunity = async () => {
    const api = window.pywebview?.api
    if (!api || typeof api.bind_community !== 'function') return
    communityBinding.value = true
    try {
      const res = await withTimeout(api.bind_community(), 30000)
      if (res?.status === 'success') {
        community.value = res.data || {}
        toast.success(`已绑定社区账号${community.value?.nick_name ? '：' + community.value.nick_name : ''}`)
      } else {
        toast.error(res?.msg || '绑定社区失败')
      }
    } catch (e) {
      toast.error(`绑定社区失败: ${e.message || e}`)
    } finally {
      communityBinding.value = false
    }
  }

  const communityOneClick = async () => {
    const api = window.pywebview?.api
    if (!api || typeof api.community_one_click !== 'function') return
    if (communityRunning.value) return
    communityRunning.value = true
    communitySteps.value = []
    try {
      const res = await withTimeout(api.community_one_click(), 120000)
      if (res?.status === 'success') {
        const data = res.data || {}
        communitySteps.value = data.steps || []
        if (data.account) community.value = data.account
        const failed = communitySteps.value.some((step) => step.status === 'error')
        if (failed) toast.warning('部分步骤失败，请看「最近一次执行」')
        else toast.success('社区日常已完成')
      } else {
        toast.error(res?.msg || '一键执行失败')
      }
    } catch (e) {
      toast.error(`一键执行失败: ${e.message || e}`)
    } finally {
      communityRunning.value = false
    }
  }

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
  const shareStyle = ref('records')
  const shareAnalyticsPools = computed(() =>
    analyticsPools.value.filter((pool) => selectedSharePools.value.includes(pool.key))
  )
  const shareAnalyticsSummary = computed(() => ({
    pools: shareAnalyticsPools.value.length,
    total: shareAnalyticsPools.value.reduce((sum, pool) => sum + pool.total, 0),
    ssr: shareAnalyticsPools.value.reduce((sum, pool) => sum + (pool.rarity?.[5] || 0), 0),
  }))
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
      toast.warning('还没有抽卡记录，先点「更新记录」或导入一份记录吧')
      return
    }
    selectedSharePools.value = withRecords.map((pool) => pool.key)
    shareStyle.value = homeMode.value === 'analytics' ? 'analytics' : 'records'
    shareDialogVisible.value = true
  }

  const confirmShare = async () => {
    if (selectedSharePools.value.length === 0) return
    shareDialogVisible.value = false
    await shareScreenshot()
  }

  // 将 html2canvas 暴露到全局，供后端 evaluate_js 调用
  window.html2canvas = html2canvas

  // 角色/武器图片走 24 小时磁盘缓存，避免每次重启都重新拉取
  const isWeaponImage = (itemId) => {
    const key = String(itemId)
    const weaponMaps = [ssrStore.SSR_weapon, ssrStore.SSR_custom_weapon]
    const characterMaps = [ssrStore.SSR_character, ssrStore.SSR_custom_character]
    if (weaponMaps.some((map) => map && Object.prototype.hasOwnProperty.call(map, key))) return true
    if (characterMaps.some((map) => map && Object.prototype.hasOwnProperty.call(map, key))) return false
    return key.length === 5
  }
  const collectGachaImageUrls = (gacha = gachaRecordStore.gacha) => {
    const draws = Object.values(gacha || {}).flatMap((pages) =>
      (Array.isArray(pages) ? pages : []).flatMap((page) => page?.data?.list || [])
    )
    const urls = draws.map((draw) => {
      const item = String(draw.item)
      return `https://static.gf2gacha-xkl.uk/images/${isWeaponImage(item) ? 'weapon' : 'character'}/${item}.png`
    })
    return [...new Set(urls)]
  }
  const preloadGachaImages = async (gacha = gachaRecordStore.gacha) => {
    const urls = collectGachaImageUrls(gacha)
    if (urls.length) await imageCacheStore.ensureImages(urls)
  }
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
  watch(() => gachaRecordStore.gacha, () => {
    preloadGachaImages()
    prefetchShareIcons()
  })

  // ---------------- 代理 / 捕获状态 ----------------
  // 「更新记录」只是重放上一次抓到的游戏请求，所以界面上必须能看出来
  // 代理有没有起来、有没有抓到过请求，否则用户只会看到一句没头没尾的失败。
  const proxyReady = ref(false)
  const proxyApplied = ref(false)
  const proxyError = ref('')
  const proxyPort = ref(null)
  const captureInfo = ref({})
  const lastSeenCapture = ref('')
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

  const proxyStatusText = computed(() => {
    if (!proxyReady.value) return '未启动（请重启本工具）'
    if (!proxyApplied.value) {
      return proxyError.value
        ? `系统代理未接管：${proxyError.value}`
        : '已启动，系统代理未接管（请先安装证书）'
    }
    return `运行中（仅解密抽卡接口） 127.0.0.1:${proxyPort.value}`
  })

  const statusDotClass = computed(() => (proxyReady.value && proxyApplied.value ? 'ok' : 'bad'))
  const statusShort = computed(() => {
    if (!proxyReady.value) return '代理未启动'
    if (!proxyApplied.value) return '代理未接管'
    return '代理运行中'
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
      toast.success('已捕获到游戏抽卡请求，现在可以点「更新记录」了')
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

  // 用系统默认程序直接打开日志文件本身
  const openLogFile = async () => {
    if (!(await waitForApi())) return
    try {
      const res = await window.pywebview.api.open_log_file()
      if (!res || res.status !== 'success') {
        toast.error((res && res.msg) || '打开日志文件失败')
      }
    } catch (e) {
      toast.error(`打开日志文件失败: ${e.message || e}`)
    }
  }

  // ---------------- 小程序钥匙导出 ----------------
  const keyStatus = ref(null)
  const keyStatusLoading = ref(false)
  const keyUidInput = ref('')
  const keyVerifying = ref(false)
  const keyVerified = ref(null)
  const keyDialogVisible = ref(false)
  const copyingKey = ref(false)

  const keyReady = computed(() => !!(keyStatus.value && keyStatus.value.has_credential))

  const keyCaptureText = computed(() => {
    const status = keyStatus.value
    if (!status) return '读取中…'
    const capture = status.capture || {}
    if (!capture.exists) return '尚未捕获（先在游戏里打开「招募 · 访问详情」页面）'
    if (!status.has_credential) return '捕获异常：缺少 Authorization'
    return `已捕获${capture.age_text ? ` ${capture.age_text}` : ''}`
  })

  const refreshKeyStatus = async () => {
    if (disposed || !(await waitForApi())) return
    keyStatusLoading.value = true
    try {
      const res = await withTimeout(window.pywebview.api.get_key_export_status())
      if (!disposed && res && res.ok !== false) keyStatus.value = res
    } catch (e) {
      console.error('[ERROR] 读取钥匙导出状态失败:', e)
    } finally {
      keyStatusLoading.value = false
    }
  }

  const startExportKey = async () => {
    if (!(await waitForApi()) || keyVerifying.value) return
    keyVerifying.value = true
    try {
      // B服钥匙需要用户补填 UID；官服不填（官服 UID 由后端向官方接口核对）
      const uid = keyUidInput.value.trim() || null
      const res = await withTimeout(window.pywebview.api.start_key_export(uid), 30000)
      if (res.status === 'success') {
        keyVerified.value = res.data
        keyDialogVisible.value = true
      } else {
        toast.error(res.msg || '导出失败')
      }
    } catch (e) {
      toast.error(`导出失败: ${e.message || e}`)
    } finally {
      keyVerifying.value = false
    }
  }

  const copyKey = async () => {
    if (!(await waitForApi()) || copyingKey.value) return
    copyingKey.value = true
    try {
      const res = await withTimeout(window.pywebview.api.copy_key_to_clipboard())
      if (res.status === 'success') {
        toast.success(res.msg)
        keyDialogVisible.value = false
      } else {
        toast.error(res.msg || '复制失败')
      }
    } catch (e) {
      toast.error(`复制失败: ${e.message || e}`)
    } finally {
      copyingKey.value = false
    }
  }

  // 游戏侧重新抓包（captured_at 变化）后，过期时间等要跟着刷新（纯本地解码，代价为零）
  watch(() => captureInfo.value.captured_at, () => refreshKeyStatus())

  // ---------------- R2 公告 ----------------
  // 只在应用打开时自动检查一次；手动点「公告」会绕过缓存强制刷新。
  let announcementPending = false

  const markAnnouncementSeen = async (announcementId) => {
    if (!announcementId || !(await waitForApi())) return
    try {
      await withTimeout(window.pywebview.api.mark_announcement_seen(announcementId))
    } catch (e) {
      console.error('[ERROR] 保存公告已读状态失败:', e)
    }
  }

  const refreshAnnouncement = async (force = false, manual = false) => {
    if (disposed || announcementPending) return
    announcementPending = true
    if (manual) announcementLoading.value = true
    try {
      if (!(await waitForApi()) || disposed) return
      const res = await withTimeout(window.pywebview.api.get_announcement(!!force), 20000)
      if (disposed) return
      if (!res || res.status !== 'success') {
        if (manual) toast.error((res && res.message) || '公告获取失败')
        return
      }
      if (manual && res.warning) toast.warning(res.warning)
      const latest = res.announcement
      if (!latest) {
        if (manual) toast.info('暂无公告')
        return
      }
      announcement.value = latest
      announcementUnread.value = !!res.unread
      const canAutoShow = !updateNoticeVisible.value && !shareDialogVisible.value && !keyDialogVisible.value
      if (manual || (res.unread && canAutoShow)) {
        announcementDialogVisible.value = true
        announcementUnread.value = false
        markAnnouncementSeen(latest.id)
      } else if (res.unread && announcementDialogVisible.value) {
        // 弹窗正开着时清单又更新了：新内容已经显示在当前弹窗里，直接记为已读。
        announcementUnread.value = false
        markAnnouncementSeen(latest.id)
      }
    } catch (e) {
      console.error('[ERROR] 获取公告失败:', e)
      if (manual) toast.error(`公告获取失败: ${e.message || e}`)
    } finally {
      announcementPending = false
      if (manual) announcementLoading.value = false
    }
  }

  const openAnnouncement = () => refreshAnnouncement(true, true)

  // 公告图片放大查看
  const lightboxVisible = ref(false)
  const lightboxIndex = ref(0)
  const openLightbox = (index) => {
    lightboxIndex.value = index
    lightboxVisible.value = true
  }

  // 显示更新通知（远端 version.json 里带 update_info 时一并展示更新说明）
  const showUpdateNotification = (latestVersion, notes = '') => {
    const detail = notes ? `\n\n更新内容：\n${notes}` : ''
    confirmDialog({
      title: '更新提示',
      message: `发现新版本 v${latestVersion}，是否更新？${detail}`,
      confirmText: '更新',
      cancelText: '稍后',
    }).then((ok) => {
      if (ok) startUpdate()
    })
  }

  // 开始更新
  const startUpdate = async () => {
    try {
      const res = await window.pywebview.api.start_update()
      if (res.status == 'success') {
        toast.success('正在启动更新器...')
        // 更新器会自动关闭主程序
      } else {
        toast.error(`启动更新失败: ${res.message || '未知错误'}`)
      }
    } catch (e) {
      console.error('[ERROR] 启动更新异常:', e)
      toast.error(`启动更新失败: ${e.message || e}`)
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
        toast.error(`加载记录列表失败: ${res.msg}`)
      }
    } catch (e) {
      console.error('[ERROR] 加载记录列表异常:', e)
      toast.error(`加载记录列表失败: ${e.message || e}`)
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
    const ok = await confirmDialog({
      title: '回滚确认',
      message: '将回滚到上一个版本并自动重新启动程序，确定吗？',
      confirmText: '回滚',
      danger: true,
    })
    if (!ok) return
    updateNoticeVisible.value = false
    try {
      const res = await window.pywebview.api.rollback_update()
      if (!res || res.status !== 'success') {
        toast.error((res && res.msg) || '启动回滚失败')
      }
    } catch (e) {
      toast.error(`启动回滚失败: ${e.message || e}`)
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
          toast.success('当前已是最新版本')
        }
      } else {
        console.error('[ERROR] 检查更新失败:', res.message)
        toast.error(`检查更新失败: ${res.message || '未知错误'}`)
      }
    } catch (e) {
      console.error('[ERROR] 检查更新异常:', e)
      toast.error(`检查更新失败: ${e.message || e}`)
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
        toast.error(res.msg)
      }
    } catch (e) {
      console.error('[ERROR] 导入记录异常:', e)
      toast.error(`导入记录失败: ${e.message || e}`)
    }
  }

  // 打开GitHub主页
  const openGitHub = async () => {
    try {
      const res = await window.pywebview.api.open_github()
      if (res.status !== 'success') {
        console.error('[ERROR] 打开GitHub主页失败:', res.message)
        toast.error(`打开GitHub主页失败: ${res.message || '未知错误'}`)
      }
    } catch (e) {
      console.error('[ERROR] 打开GitHub主页异常:', e)
      toast.error(`打开GitHub主页失败: ${e.message || e}`)
    }
  }

  // 更新记录
  const updateRecord = async () => {
    // 先确认本地有一份「可重放」的捕获：没有就直接告诉用户该做什么，
    // 而不是让他等一句和网络故障长得一模一样的失败提示
    await refreshStatus(false)
    if (!captureReplayable.value) {
      toast.warning(statusHint.value)
      return
    }

    isUpdating.value = true
    const closeLoading = toast.loading('正在获取抽卡记录...')

    try{
       const res = await window.pywebview.api.get_gacha()
       closeLoading()

       if (res.status == 'success'){
          toast.success(res.msg)
          // 新的数据结构包含uid和gacha
          gachaRecordStore.gacha = res.data.gacha

          // 自动保存记录，使用uid作为记录名称
          if (res.data.uid) {
            const uid = res.data.uid.toString()
            const saveRes = await window.pywebview.api.export_record(uid, gachaRecordStore.gacha)
            if (saveRes.status == 'success') {
              toast.success(`记录已自动保存: ${uid}`)
              // 刷新记录列表并选中刚保存的记录
              await loadRecordList()
              selectedRecordId.value = uid
            } else {
              console.error('[ERROR] 自动保存记录失败:', saveRes.msg)
              toast.error(`自动保存记录失败: ${saveRes.msg}`)
            }
          }
       }else{
          console.error('[ERROR] 获取记录失败:', res.code, res.msg)
          toast.error(res.msg)
          // 失败原因可能来自 token 过期 / 接口变动，刷新状态让用户看到最新情况
          refreshStatus(false)
        }
   }catch (e) {
      closeLoading()
      console.error('[ERROR] 获取记录异常:', e)
      toast.error(`获取记录失败: ${e.message || e}`)
   } finally {
      isUpdating.value = false
   }
  }

  // 安装证书
  const installCert = async () => {
    try{
      const res = await window.pywebview.api.install_cert()
      if (res.status == 'success'){
        toast.success(res.msg || '证书安装成功')
      }else{
        console.error('[ERROR] 安装证书失败:', res.msg)
        toast.error(res.msg)
      }
    }catch (e) {
      console.error('[ERROR] 安装证书异常:', e)
      toast.error(`安装证书失败: ${e.message || e}`)
    }
  }

  // 卸载证书
  const uninstallCert = async () => {
    const ok = await confirmDialog({
      title: '警告',
      message: '确定要卸载 gf2gacha_XKL 证书吗？',
      confirmText: '确定',
      danger: true,
    })
    if (!ok) return

    try {
      const res = await window.pywebview.api.uninstall_cert()
      if (res.status == 'success'){
        toast.success(res.msg || '证书卸载成功')
      }else{
        console.error('[ERROR] 卸载证书失败:', res.msg)
        toast.error(res.msg)
      }
    } catch (e) {
      console.error('[ERROR] 卸载证书异常:', e)
      toast.error(`卸载证书失败: ${e.message || e}`)
    }
  }


  // 分享截图功能
  const shareScreenshot = async () => {
    if (!screenshotContainerRef.value) {
      toast.error('截图容器未就绪')
      return
    }

    isSharing.value = true

    try {
      await nextTick()
      // 截图和剪贴板操作全部由后端通过 evaluate_js 完成（避免大数据通过 api 参数被截断）
      const res = await window.pywebview.api.copy_image_to_clipboard()
      if (res && res.status === 'success') {
        toast.success('截图已复制到剪贴板，可直接粘贴使用')
      } else {
        toast.error(`复制失败: ${res?.message || '未知错误'}`)
      }
    } catch (e) {
      console.error('[ERROR] 截图失败:', e)
      toast.error(`截图失败: ${e.message || e}`)
    } finally {
      isSharing.value = false
    }
  }

  // 后台刷新结束后按最终来源提示；内置表只用于让页面先显示。
  watch(() => [ssrStore.source, ssrStore.isRefreshing], ([source, refreshing]) => {
    if (disposed || refreshing) return
    if (source === 'local-proto') {
      toast.success('正在使用最新五星数据')
    } else if (source === 'remote') {
      toast.success('正在使用远端五星数据')
    } else if (source === 'local-json') {
      toast.warning('正在使用本地五星数据(可能不是最新)')
    } else if (source === 'error') {
      toast.error('无法加载五星数据')
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

      // 钥匙导出的无网络预览（捕获状态 / 渠道 / 过期时间）
      refreshKeyStatus()

      // 加载SSR数据（前端主动控制）
      source = await ssrStore.loadData()
      preloadGachaImages()
    } catch (e) {
      console.error('[ERROR] 初始化失败:', e)
      toast.error(`初始化失败: ${e.message || e}`)
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
      toast.error('无法加载五星数据')
    }

    refreshAnnouncement(false)
  })

  onUnmounted(() => {
    disposed = true
    if (statusTimer) clearInterval(statusTimer)
    clearTimeout(prefetchTimer)
    ssrStore.stopRefresh()
  })

</script>

<style>
  /* ============================================================
     Application shell — GF2 tactical operations console
     ============================================================ */
  .app-shell {
    height: 100vh;
    display: grid;
    grid-template-columns: 224px minmax(0, 1fr);
    grid-template-rows: 31px minmax(0, 1fr);
    overflow: hidden;
    background: var(--ink-1000);
  }

  /* ---------- Custom window title bar ---------- */
  .window-titlebar {
    position: relative;
    z-index: 10000;
    grid-column: 1 / -1;
    grid-row: 1;
    height: 31px;
    display: flex;
    align-items: stretch;
    color: #8d9498;
    background: #090b0d;
    border-bottom: 1px solid #282d31;
    user-select: none;
  }
  .window-titlebar-drag {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 9px;
    padding-left: 12px;
    cursor: default;
    -webkit-app-region: drag;
  }
  .window-titlebar-logo {
    width: 16px;
    height: 16px;
    flex: none;
    object-fit: contain;
  }
  .window-titlebar-title {
    color: #c6c8c5;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.6px;
  }
  .window-titlebar-sub {
    padding-left: 9px;
    border-left: 1px solid #30363a;
    color: #555d62;
    font: 7.5px/1 var(--font-technical);
    letter-spacing: 1.05px;
  }
  .window-controls {
    display: flex;
    height: 100%;
    flex: none;
    -webkit-app-region: no-drag;
  }
  .window-control {
    width: 43px;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    border: 0;
    border-left: 1px solid transparent;
    background: transparent;
    color: #777f84;
    cursor: pointer;
    transition: background 0.13s ease, color 0.13s ease;
  }
  .window-control:hover { background: #20252a; color: #fff; }
  .window-control:focus-visible { outline: 1px solid var(--signal); outline-offset: -2px; }
  .window-control--close:hover { background: #b84136; color: #fff; }

  /* ---------- Left command rail ---------- */
  .sidebar {
    position: relative;
    z-index: 5;
    grid-column: 1;
    grid-row: 2;
    min-width: 0;
    display: flex;
    flex-direction: column;
    background:
      linear-gradient(180deg, rgba(239, 100, 47, 0.08), transparent 180px),
      repeating-linear-gradient(90deg, transparent 0 31px, rgba(255, 255, 255, 0.018) 31px 32px),
      var(--ink-950);
    border-right: 1px solid var(--ink-700);
  }
  .sidebar::after {
    content: "";
    position: absolute;
    top: 0;
    right: -1px;
    width: 2px;
    height: 96px;
    background: linear-gradient(180deg, var(--signal), transparent);
    pointer-events: none;
  }

  .brand {
    position: relative;
    flex: none;
    height: 80px;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 18px;
    border-bottom: 1px solid var(--ink-700);
    background: rgba(0, 0, 0, 0.12);
  }
  .brand-mark {
    position: relative;
    width: 43px;
    height: 43px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex: none;
    overflow: hidden;
    background: #0b0d0f;
    border: 1px solid #4a3a2a;
    clip-path: polygon(0 0, calc(100% - 9px) 0, 100% 9px, 100% 100%, 9px 100%, 0 calc(100% - 9px));
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
  }
  .brand-mark img { display: block; width: 100%; height: 100%; object-fit: cover; }
  .brand-text { min-width: 0; }
  .brand-name {
    color: var(--text-1);
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.8px;
    white-space: nowrap;
  }
  .brand-sub {
    margin-top: 4px;
    color: var(--text-3);
    font: 8.5px/1.2 var(--font-technical);
    letter-spacing: 1.25px;
    white-space: nowrap;
  }

  .nav-label {
    flex: none;
    padding: 20px 18px 8px;
    color: #5f666b;
    font: 8.5px/1 var(--font-technical);
    letter-spacing: 1.8px;
  }
  .side-nav {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 0 10px;
  }
  .nav-item {
    position: relative;
    width: 100%;
    height: 50px;
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 0 12px 0 14px;
    border: 0;
    border-radius: 0;
    background: transparent;
    color: var(--text-2);
    font-family: inherit;
    text-align: left;
    cursor: pointer;
    transition: background 0.16s ease, color 0.16s ease;
  }
  .nav-item::before {
    content: "";
    position: absolute;
    left: 0;
    top: 50%;
    width: 3px;
    height: 0;
    background: var(--signal);
    transform: translateY(-50%);
    transition: height 0.16s ease;
  }
  .nav-item:hover { background: rgba(255, 255, 255, 0.045); color: var(--text-1); }
  .nav-item:focus-visible { outline: 1px solid var(--signal); outline-offset: -3px; }
  .nav-item.active {
    background: linear-gradient(90deg, rgba(239, 100, 47, 0.16), rgba(239, 100, 47, 0.025));
    color: #fff;
  }
  .nav-item.active::before { height: 25px; }
  .nav-item .app-icon { flex: none; opacity: 0.86; }
  .nav-item.active .app-icon { color: var(--signal-hi); opacity: 1; }
  .nav-copy { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
  .nav-copy strong { font-size: 13.5px; font-weight: 650; letter-spacing: 0.6px; }
  .nav-copy small { color: #666d72; font: 8px/1 var(--font-technical); letter-spacing: 1.2px; }
  .nav-item.active .nav-copy small { color: #9b7563; }
  .nav-index {
    margin-left: auto;
    color: #4e555a;
    font: 9px/1 var(--font-technical);
    letter-spacing: 0.8px;
  }
  .nav-item.active .nav-index { color: var(--signal-hi); }

  .side-footer {
    margin-top: auto;
    padding: 15px 18px 17px;
    border-top: 1px solid var(--ink-700);
    background: rgba(0, 0, 0, 0.12);
  }
  .side-status {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-2);
    font-size: 11px;
  }
  .side-meta {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    margin-top: 8px;
    color: #555d62;
    font: 8.5px/1 var(--font-technical);
    letter-spacing: 0.65px;
  }
  .side-meta span:last-child::before { content: "· "; color: var(--signal); }

  /* ---------- Main column / top bar ---------- */
  .main-col {
    grid-column: 2;
    grid-row: 2;
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .topbar {
    position: relative;
    z-index: 4;
    flex: none;
    height: 72px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    padding: 0 22px;
    background:
      linear-gradient(90deg, rgba(255, 255, 255, 0.025), transparent 34%),
      var(--ink-900);
    border-bottom: 1px solid var(--ink-700);
    box-shadow: 0 7px 20px rgba(0, 0, 0, 0.16);
  }
  .topbar::after {
    content: "";
    position: absolute;
    left: 0;
    bottom: -1px;
    width: 72px;
    height: 2px;
    background: var(--signal);
  }
  .topbar-left { min-width: 0; display: flex; align-items: center; gap: 15px; }
  .archive-code {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 52px;
    height: 38px;
    flex: none;
    border-right: 1px solid var(--ink-700);
    color: #727a80;
    font: 8px/1.1 var(--font-technical);
    letter-spacing: 1.1px;
  }
  .archive-code strong { margin-top: 4px; color: var(--text-1); font-size: 13px; letter-spacing: 0.8px; }
  .record-field { min-width: 0; display: flex; flex-direction: column; gap: 5px; }
  .record-label { color: #777e83; font: 8px/1 var(--font-technical); letter-spacing: 1.1px; }
  .topbar .app-select { width: 258px; }
  .topbar-right { display: flex; align-items: center; gap: 9px; flex: none; }

  .bell-btn {
    position: relative;
    width: 38px;
    height: 38px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    border: 1px solid var(--ink-700);
    border-radius: var(--radius-control);
    background: var(--ink-850);
    color: var(--text-2);
    cursor: pointer;
    transition: background 0.16s ease, border-color 0.16s ease, color 0.16s ease;
  }
  .bell-btn:hover { border-color: var(--ink-600); background: var(--ink-800); color: #fff; }
  .bell-btn:focus-visible { outline: 2px solid var(--signal); outline-offset: 2px; }
  .bell-btn.unread { color: var(--signal-hi); border-color: rgba(239, 100, 47, 0.55); }
  .bell-badge {
    position: absolute;
    top: 7px;
    right: 7px;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--signal);
    box-shadow: 0 0 0 2px var(--ink-850), 0 0 8px var(--signal-glow);
  }

  /* ---------- Field-paper workspace ---------- */
  .content {
    position: relative;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    scrollbar-width: none;
    -ms-overflow-style: none;
    padding: 24px 26px 42px;
    background-color: var(--paper-1);
    background-image:
      linear-gradient(rgba(35, 38, 39, 0.045) 1px, transparent 1px),
      linear-gradient(90deg, rgba(35, 38, 39, 0.045) 1px, transparent 1px),
      radial-gradient(circle at 88% 5%, rgba(239, 100, 47, 0.09), transparent 27%);
    background-size: 32px 32px, 32px 32px, auto;
  }
  .content::-webkit-scrollbar {
    width: 0;
    height: 0;
    display: none;
  }  .content::before {
    content: "";
    position: fixed;
    right: 28px;
    top: 96px;
    width: 84px;
    height: 84px;
    opacity: 0.18;
    pointer-events: none;
    background:
      linear-gradient(var(--ink-900), var(--ink-900)) center / 1px 100% no-repeat,
      linear-gradient(90deg, var(--ink-900), var(--ink-900)) center / 100% 1px no-repeat;
    border: 1px solid var(--ink-900);
    border-radius: 50%;
  }
  .view-panel { position: relative; z-index: 1; max-width: 1320px; margin: 0 auto; }

  .section-kicker {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-3);
    font: 8.5px/1 var(--font-technical);
    letter-spacing: 1.35px;
    text-transform: uppercase;
  }
  .section-index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 23px;
    height: 16px;
    padding: 0 4px;
    background: var(--signal);
    color: #fff;
    font: 700 8.5px/1 var(--font-technical);
    letter-spacing: 0.8px;
  }
  .page-title {
    margin: 7px 0 0;
    color: var(--text-1);
    font-family: var(--font-display);
    font-size: 30px;
    font-weight: 800;
    line-height: 1.1;
    letter-spacing: 1.2px;
  }
  .page-desc {
    margin: 7px 0 0;
    color: var(--text-3);
    font-size: 11.5px;
    line-height: 1.5;
    letter-spacing: 0.2px;
  }

  /* overview hero */
  .overview-hero {
    position: relative;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 28px;
    min-height: 142px;
    padding: 22px 24px;
    overflow: hidden;
    color: var(--text-1);
    background:
      linear-gradient(112deg, rgba(255, 255, 255, 0.045), transparent 40%),
      var(--ink-900);
    border-left: 3px solid var(--signal);
    box-shadow: 0 12px 30px rgba(31, 31, 28, 0.18);
  }
  .overview-hero::before {
    content: "";
    position: absolute;
    top: -24px;
    right: 88px;
    width: 170px;
    height: 210px;
    transform: skewX(-23deg);
    background: repeating-linear-gradient(90deg, rgba(239, 100, 47, 0.105) 0 3px, transparent 3px 14px);
    pointer-events: none;
  }
  .overview-hero::after {
    content: "";
    position: absolute;
    right: 17px;
    top: 16px;
    width: 19px;
    height: 19px;
    border-top: 1px solid rgba(255, 255, 255, 0.31);
    border-right: 1px solid rgba(255, 255, 255, 0.31);
  }
  .hero-copy,
  .hero-side { position: relative; z-index: 1; }
  .hero-copy .page-title { color: #fff; font-size: 34px; }
  .hero-copy .page-desc { max-width: 450px; color: #9da2a5; }
  .hero-side {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    justify-content: flex-end;
    gap: 13px;
  }
  .quick-stats { display: flex; gap: 7px; }
  .quick-stat {
    min-width: 70px;
    padding: 8px 10px 7px;
    border: 1px solid rgba(255, 255, 255, 0.11);
    background: rgba(255, 255, 255, 0.045);
  }
  .quick-stat span { display: block; color: #858c91; font-size: 8.5px; letter-spacing: 0.5px; }
  .quick-stat strong {
    display: inline-block;
    margin-top: 3px;
    color: #fff;
    font: 600 22px/1 var(--font-technical);
    font-variant-numeric: tabular-nums;
  }
  .quick-stat small { margin-left: 5px; color: var(--signal-hi); font: 7.5px/1 var(--font-technical); letter-spacing: 0.7px; }
  .display-mode-wrap { display: flex; align-items: center; gap: 8px; }
  .display-mode-wrap > span { color: #626a6f; font: 7px/1 var(--font-technical); letter-spacing: 1px; }
  .display-mode-switch { display: inline-flex; gap: 2px; padding: 2px; background: rgba(0,0,0,.28); border: 1px solid rgba(255,255,255,.13); border-radius: var(--radius-control); }
  .display-mode-switch button { height: 24px; display: inline-flex; align-items: center; gap: 5px; padding: 0 9px; border: 0; border-radius: 1px; background: transparent; color: #8e9599; font: 9.5px/1 var(--font-ui); cursor: pointer; transition: background .16s ease, color .16s ease; }
  .display-mode-switch button:hover { color: #fff; background: rgba(255,255,255,.06); }
  .display-mode-switch button.active { color: #191c1e; background: #ede9df; }
  .display-mode-switch button:focus-visible { outline: 1px solid var(--signal); outline-offset: 1px; }
  /* section heading */
  .section-bar {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin: 25px 0 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(31, 35, 37, 0.24);
  }
  .section-bar h3 {
    margin: 5px 0 0;
    color: var(--text-1);
    font-size: 18px;
    font-weight: 750;
    letter-spacing: 0.6px;
  }
  .section-status {
    color: var(--text-3);
    font: 8.5px/1 var(--font-technical);
    letter-spacing: 1px;
    white-space: nowrap;
  }
  .section-status::before { content: "■"; margin-right: 6px; color: var(--signal); font-size: 7px; }
  .section-actions { display: flex; align-items: center; gap: 11px; }
  .row-collapse-btn {
    height: 24px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 0 7px;
    border: 1px solid #aaa395;
    border-radius: var(--radius-control);
    background: rgba(246, 243, 235, 0.62);
    color: #66645e;
    font: 9px/1 var(--font-ui);
    cursor: pointer;
    transition: color 0.16s ease, border-color 0.16s ease, background 0.16s ease;
  }
  .row-collapse-btn:hover { color: #222529; border-color: #7f7a70; background: var(--paper-0); }
  .row-collapse-btn:focus-visible { outline: 2px solid var(--signal); outline-offset: 2px; }
  .row-collapse-icon { transition: transform 0.28s cubic-bezier(0.22, 1, 0.36, 1); }
  .row-collapse-btn:not(.collapsed) .row-collapse-icon { transform: rotate(180deg); }
  .section-bar--compact { margin-top: 22px; }
  .analytics-mode { min-width: 0; }
  .analytics-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; gap: 14px; }
  /* pool cards */
  .pool-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    align-items: start;
    gap: 14px;
  }
  .pool-grid--two { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .pool-card {
    position: relative;
    min-width: 0;
    padding: 13px;
    background: var(--paper-0);
    border: 1px solid #b8b1a3;
    border-top: 3px solid var(--ink-900);
    box-shadow: var(--shadow-panel);
  }
  .pool-card::before {
    content: "";
    position: absolute;
    top: -3px;
    left: 14px;
    width: 38px;
    height: 3px;
    background: var(--signal);
  }
  .pool-card::after {
    content: "";
    position: absolute;
    right: 7px;
    bottom: 7px;
    width: 10px;
    height: 10px;
    border-right: 1px solid #bbb4a5;
    border-bottom: 1px solid #bbb4a5;
    pointer-events: none;
  }
  .pool-card-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
    padding-bottom: 9px;
    margin-bottom: 9px;
    border-bottom: 1px solid #d4cec1;
  }
  .pool-code { display: block; color: #8b877d; font: 7.5px/1 var(--font-technical); letter-spacing: 1px; }
  .pool-name {
    margin: 4px 0 0;
    color: #171a1c;
    font-size: 16px;
    font-weight: 760;
    line-height: 1.2;
    letter-spacing: 0.5px;
  }
  .pool-type {
    padding: 3px 5px 2px;
    color: #6f6a60;
    border: 1px solid #c2bbad;
    font: 7.5px/1 var(--font-technical);
    letter-spacing: 0.8px;
  }
  .custom-pools-block { animation: section-reveal 0.22s ease both; }

  /* ---------- Tools / systems ---------- */
  .tools-view { display: flex; flex-direction: column; gap: 0; }
  .tools-intro {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 24px;
    padding: 2px 0 18px;
    border-bottom: 1px solid rgba(31, 35, 37, 0.28);
  }
  .system-ready {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 150px;
    padding: 9px 12px;
    background: var(--paper-0);
    border: 1px solid var(--paper-line);
    border-left: 2px solid var(--signal);
  }
  .system-ready div { display: flex; flex-direction: column; gap: 3px; }
  .system-ready strong { color: var(--text-1); font-size: 11.5px; font-weight: 650; }
  .system-ready small { color: var(--text-3); font: 7.5px/1 var(--font-technical); letter-spacing: 1px; }
  .tools-grid {
    counter-reset: toolcard;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
    margin-top: 16px;
  }
  .tool-card {
    counter-increment: toolcard;
    position: relative;
    min-width: 0;
    padding: 18px 19px 16px;
    background: var(--paper-0);
    border: 1px solid #b8b1a3;
    border-top: 3px solid var(--ink-900);
    box-shadow: var(--shadow-panel);
  }
  .tool-card::before {
    content: "";
    position: absolute;
    top: -3px;
    left: 15px;
    width: 46px;
    height: 3px;
    background: var(--signal);
  }
  .tool-card::after {
    content: "SYS-0" counter(toolcard);
    position: absolute;
    top: 9px;
    right: 12px;
    color: #a09a8e;
    font: 7.5px/1 var(--font-technical);
    letter-spacing: 0.9px;
  }
  .tool-card:first-child,
  .tool-card:last-child { grid-column: 1 / -1; }
  /* 社区视图：卡片宽度写死，避免结果卡片出现/消失时网格重新排布（原截图里「每日任务」右侧留空） */
  .community-grid > .tool-card { grid-column: auto; }
  .community-grid > .tool-card.is-wide { grid-column: 1 / -1; }
  /* 竖排信息（账号 / 执行结果）：标签定宽、值紧跟其后，不贴右边缘 */
  .status-rows--inline .status-row { align-items: baseline; }
  .status-rows--inline .status-label { width: 84px; flex: none; }
  .status-rows--inline .status-value { flex: 1; min-width: 0; white-space: normal; overflow-wrap: anywhere; }
  /* 任务 / 兑换（半宽卡）：名称在左、数值贴右，才好扫读 */
  .status-rows--split .status-row { align-items: center; }
  .status-rows--split .status-label { width: auto; flex: 1 1 auto; min-width: 0; }
  .status-rows--split .status-value { flex: none; white-space: nowrap; }
  .tool-head {
    display: flex;
    align-items: center;
    gap: 9px;
    margin-bottom: 9px;
    padding-right: 48px;
  }
  .tool-head h3 {
    margin: 0;
    color: #171a1c;
    font-size: 16px;
    font-weight: 750;
    letter-spacing: 0.5px;
  }
  .tool-icon { color: var(--signal); }
  .tool-desc {
    margin: 0 0 14px;
    max-width: 780px;
    color: var(--text-3);
    font-size: 11.5px;
    line-height: 1.75;
  }
  .tool-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 15px; }

  .status-rows { display: flex; flex-direction: column; gap: 8px; }
  .status-row {
    display: flex;
    align-items: baseline;
    gap: 10px;
    min-width: 0;
    font-size: 12.5px;
  }
  .status-label {
    width: 70px;
    flex: none;
    color: var(--text-3);
    font-size: 10.5px;
    letter-spacing: 0.35px;
  }
  .status-value { color: var(--text-1); word-break: break-all; }
  .status-value.expired { color: var(--bad); }
  .status-path { color: var(--text-2); font: 10.5px/1.6 var(--font-mono); }
  .status-hint {
    margin-top: 2px;
    padding-top: 9px;
    border-top: 1px solid #d7d1c5;
    color: var(--text-3);
    font-size: 10.5px;
    line-height: 1.65;
  }

  .key-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; }
  .key-field {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 5px;
    padding: 9px 11px;
    background: var(--paper-1);
    border: 1px solid #d2ccbf;
    border-left: 2px solid #9b9589;
  }
  .key-label { color: var(--text-3); font-size: 9.5px; letter-spacing: 0.4px; }
  .key-value {
    overflow: hidden;
    color: var(--text-1);
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .key-value.expired { color: var(--bad); }
  .key-uid-row { display: flex; flex-direction: column; gap: 6px; margin-top: 12px; }
  .key-confirm-rows { margin-bottom: 13px; }
  .key-confirm-tip {
    margin: 0;
    padding-top: 11px;
    border-top: 1px solid var(--border);
    color: var(--text-3);
    font-size: 11.5px;
    line-height: 1.75;
  }

  /* ---------- Loading ---------- */
  .loading-overlay {
    position: fixed;
    inset: 0;
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
    background:
      repeating-linear-gradient(90deg, transparent 0 39px, rgba(255, 255, 255, 0.018) 39px 40px),
      rgba(11, 13, 15, 0.95);
    backdrop-filter: blur(7px);
    -webkit-backdrop-filter: blur(7px);
  }
  .loading-content { position: relative; display: flex; flex-direction: column; align-items: center; gap: 17px; }
  .loading-content::before {
    content: "XKL // DESKTOP TERMINAL";
    position: absolute;
    bottom: calc(100% + 18px);
    color: #696f73;
    font: 8px/1 var(--font-technical);
    letter-spacing: 1.8px;
    white-space: nowrap;
  }
  .spinner-big { width: 34px; height: 34px; border-width: 2px; color: var(--signal); }
  .loading-text { color: #aaaeb0; font-size: 11.5px; letter-spacing: 1.1px; }

  /* ---------- Offscreen share canvas: keep light and poster-like ---------- */
  .screenshot-container {
    position: fixed;
    left: -9999px;
    top: 0;
    width: auto;
    padding: 20px 24px;
    background: #fff;
    z-index: -1;
  }
  .screenshot-container.is-analytics-share {
    width: 1040px;
    padding: 24px;
    background:
      linear-gradient(rgba(35, 38, 39, .045) 1px, transparent 1px),
      linear-gradient(90deg, rgba(35, 38, 39, .045) 1px, transparent 1px),
      #e9e5da;
    background-size: 28px 28px;
  }
  .share-analytics-layout { width: 992px; }
  .share-report-head {
    position: relative;
    margin-bottom: 16px;
    padding: 18px 20px 16px;
    color: #f2efe7;
    background: #15191c;
    border-left: 3px solid var(--signal);
    overflow: hidden;
  }
  .share-report-head::after {
    content: "";
    position: absolute;
    top: -18px;
    right: 44px;
    width: 140px;
    height: 150px;
    transform: skewX(-22deg);
    background: repeating-linear-gradient(90deg, rgba(239,100,47,.1) 0 3px, transparent 3px 14px);
  }
  .share-report-brand { position: relative; z-index: 1; color: #8e969a; font: 8px/1 var(--font-technical); letter-spacing: 1.4px; }
  .share-report-brand span { display: inline-block; margin-right: 6px; padding: 3px 5px; color: #fff; background: var(--signal); font-size: 9px; }
  .share-report-title { position: relative; z-index: 1; margin-top: 8px; font-size: 26px; font-weight: 800; letter-spacing: 1px; }
  .share-report-meta { position: relative; z-index: 1; display: flex; gap: 17px; margin-top: 8px; color: #9fa5a8; font-size: 9.5px; }
  .share-report-meta span::before { content: "■"; margin-right: 5px; color: var(--signal); font-size: 6px; }
  .share-analytics-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; align-items: start; }
  .share-analytics-grid > :last-child:nth-child(odd) {
    grid-column: 1 / -1;
    width: calc(50% - 7px);
    justify-self: center;
  }
  .screenshot-pools-row { display: flex; gap: 16px; align-items: flex-start; }
  .screenshot-pool-item {
    min-width: 280px;
    max-width: 320px;
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  .screenshot-pool-title {
    margin-bottom: 8px;
    color: #242629;
    font-size: 18px;
    font-weight: 700;
  }

  /* ---------- Dialog content ---------- */
  .app-dialog {
    --text-1: #efede5;
    --text-2: #b7b9b7;
    --text-3: #81878b;
    --border: #343a3e;
    --border-strong: #485056;
    --bg-panel: #191d21;
    --bg-panel-soft: #22272c;
    --bg-hover: rgba(255, 255, 255, 0.06);
  }
  .share-section-label {
    display: block;
    margin-bottom: 7px;
    color: var(--text-3);
    font: 8px/1 var(--font-technical);
    letter-spacing: 1.1px;
  }
  .share-section-label--pools { margin-top: 16px; }
  .share-style-section { margin-bottom: 2px; }
  .share-style-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .share-style-option {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 10px 11px;
    text-align: left;
    color: var(--text-2);
    background: var(--bg-panel-soft);
    border: 1px solid var(--border);
    border-radius: var(--radius-control);
    cursor: pointer;
    transition: border-color .16s ease, background .16s ease, color .16s ease;
  }
  .share-style-option:hover { border-color: var(--border-strong); color: var(--text-1); }
  .share-style-option.active { border-color: var(--signal); background: var(--signal-soft); color: var(--text-1); }
  .share-style-option:focus-visible { outline: 2px solid var(--signal); outline-offset: 2px; }
  .share-style-option span { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
  .share-style-option strong { font-size: 11px; font-weight: 650; }
  .share-style-option small { color: var(--text-3); font-size: 8.5px; }
  .share-pool-list { display: flex; flex-direction: column; gap: 8px; }
  .share-pool-list .app-check {
    width: 100%;
    padding: 9px 11px;
    border: 1px solid var(--border);
    background: var(--bg-panel-soft);
  }
  .share-pool-name { font-size: 12.5px; }
  .share-pool-empty { margin-left: 4px; color: var(--text-3); font-size: 10.5px; }

  .update-notice p { margin: 0 0 10px; color: var(--text-1); font-size: 12.5px; line-height: 1.75; }
  .update-notice-error { color: #ef8d80 !important; }
  .update-notice-tip { color: var(--text-3) !important; font: 10px/1.6 var(--font-mono); word-break: break-all; }

  /* ---------- Announcement ---------- */
  .announcement-header {
    position: relative;
    padding: 4px 42px 8px 0;
    border-top: 3px solid var(--signal);
  }
  .announcement-kicker {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #858a8d;
    font: 8.5px/1 var(--font-technical);
    letter-spacing: 1.6px;
  }
  .announcement-kicker-line { width: 6px; height: 6px; background: var(--signal); }
  .announcement-close {
    position: absolute;
    top: -2px;
    right: -6px;
    width: 29px;
    height: 29px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    border: 1px solid transparent;
    border-radius: var(--radius-control);
    background: transparent;
    color: var(--text-3);
    cursor: pointer;
  }
  .announcement-close:hover { border-color: var(--border); background: var(--bg-hover); color: var(--text-1); }
  .announcement-title {
    margin-top: 12px;
    color: var(--text-1);
    font: 750 23px/1.35 var(--font-ui);
    letter-spacing: 0.8px;
  }
  .announcement-meta { margin-top: 7px; color: var(--text-3); font: 10px/1 var(--font-mono); }
  .announcement-content {
    max-height: 54vh;
    overflow-y: auto;
    padding-top: 16px;
    overscroll-behavior: contain;
  }
  .announcement-copy {
    color: var(--text-1);
    font-size: 13px;
    line-height: 1.9;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .announcement-images { display: flex; flex-direction: column; gap: 14px; margin-top: 18px; }
  .announcement-image {
    width: 100%;
    max-height: 500px;
    object-fit: contain;
    border: 1px solid var(--border);
    background: var(--bg-panel-soft);
    cursor: zoom-in;
  }

  .back-to-top {
    position: fixed;
    right: 28px;
    bottom: 24px;
    z-index: 20;
    width: 42px;
    height: 42px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1px;
    padding: 0;
    color: #eeeae0;
    background: #191d21;
    border: 1px solid #4b5257;
    border-top: 2px solid var(--signal);
    border-radius: var(--radius-control);
    box-shadow: 0 8px 22px rgba(20, 20, 18, 0.28);
    cursor: pointer;
    transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
  }
  .back-to-top .app-icon { transform: rotate(180deg); color: var(--signal-hi); }
  .back-to-top span { color: #8b9296; font: 7px/1 var(--font-technical); letter-spacing: 0.7px; }
  .back-to-top:hover { transform: translateY(-2px); background: #22272b; border-color: var(--signal); }
  .back-to-top:focus-visible { outline: 2px solid var(--signal); outline-offset: 2px; }
  .backtop-enter-active, .backtop-leave-active { transition: opacity 0.2s ease, transform 0.2s ease; }
  .backtop-enter-from, .backtop-leave-to { opacity: 0; transform: translateY(8px); }
  /* ---------- Motion ---------- */
  .mode-shift-enter-active,
  .mode-shift-leave-active { transition: opacity 0.2s ease, transform 0.2s ease; }
  .mode-shift-enter-from { opacity: 0; transform: translateY(7px); }
  .mode-shift-leave-to { opacity: 0; transform: translateY(-5px); }  .view-shift-enter-active,
  .view-shift-leave-active { transition: opacity 0.16s ease, transform 0.16s ease; }
  .view-shift-enter-from { opacity: 0; transform: translateY(7px); }
  .view-shift-leave-to { opacity: 0; transform: translateY(-4px); }
  @keyframes section-reveal {
    from { opacity: 0; transform: translateY(-5px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @media (max-width: 1060px) {
    .app-shell { grid-template-columns: 78px minmax(0, 1fr); }
    .brand { justify-content: center; padding: 0; }
    .brand-text, .nav-label, .nav-copy, .nav-index, .side-meta { display: none; }
    .side-nav { padding: 14px 9px; }
    .nav-item { justify-content: center; padding: 0; }
    .nav-item::before { left: -9px; }
    .side-footer { display: flex; justify-content: center; padding: 15px 0; }
    .side-status span:last-child { display: none; }
    .content { padding: 20px; }
    .overview-hero { grid-template-columns: 1fr; }
    .hero-side { align-items: flex-start; }
    .pool-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .pool-grid--two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .analytics-grid { grid-template-columns: 1fr; }
    .community-grid { grid-template-columns: 1fr; }
    .display-mode-wrap > span { display: none; }  }
</style>