<template>
  <div class="page-container">
    <el-card shadow="never" class="guide-card">
      <template #header>
        <div class="card-header">
          <el-icon :size="22" color="#13c2c2"><DocumentCopy /></el-icon>
          <span>操作指南</span>
        </div>
      </template>

      <!-- 自定义步骤列表 -->
      <div class="guide-steps">
        <!-- 第一步：桌面端抓取数据 -->
        <div class="main-step">
          <div class="main-step__head" @click="toggleStep(0)">
            <div class="main-step__icon" style="background: #409eff">
              <el-icon><Monitor /></el-icon>
            </div>
            <span class="main-step__title">第一步：在电脑上获取抽卡数据</span>
            <el-icon class="main-step__arrow" :class="{ 'is-expanded': expandedSteps[0] }"><ArrowDown /></el-icon>
          </div>
          <transition name="step-collapse">
            <div v-show="expandedSteps[0]" class="main-step__body">
              <el-alert type="info" :closable="false" show-icon class="step-alert">
                <p>你需要使用<strong>桌面端工具</strong>来捕获游戏中的抽卡记录数据。整个过程只需几分钟。</p>
              </el-alert>

              <h4 class="sub-title">准备工作</h4>
              <ol class="step-list">
                <li>确保电脑已连接互联网</li>
                <li>确认游戏客户端已安装并可以正常运行</li>
                <li>关闭可能占用网络代理的其他软件（VPN、加速器等）</li>
              </ol>

              <h4 class="sub-title">操作步骤</h4>
              <ol class="step-list">
                <li><strong>启动桌面端程序</strong> — 双击运行后，程序会自动完成证书配置和网络代理设置。首次运行时如果弹出安全提示，请选择"允许/信任"。</li>
                <li><strong>进入游戏并抽取卡牌</strong> — 打开游戏客户端，正常进行任意一次或多次抽卡操作。程序会在后台自动捕获你的抽卡数据。</li>
                <li><strong>获取数据</strong> — 抽卡完成后，回到桌面端程序，点击"<strong>获取抽卡记录</strong>"按钮。程序会自动从游戏中拉取完整的抽卡历史记录。</li>
                <li><strong>复制数据</strong> — 程序会显示一个包含数据的文本框，点击"<strong>复制</strong>"按钮将内容复制到剪贴板。这就是我们下一步需要用到的东西。</li>
              </ol>
            </div>
          </transition>
        </div>

        <!-- 第二步：移动端分析 -->
        <div class="main-step">
          <div class="main-step__head" @click="toggleStep(1)">
            <div class="main-step__icon" style="background: #67c23a">
              <el-icon><Iphone /></el-icon>
            </div>
            <span class="main-step__title">第二步：在手机上分析抽卡结果</span>
            <el-icon class="main-step__arrow" :class="{ 'is-expanded': expandedSteps[1] }"><ArrowDown /></el-icon>
          </div>
          <transition name="step-collapse">
            <div v-show="expandedSteps[1]" class="main-step__body">
              <el-alert type="success" :closable="false" show-icon class="step-alert">
                <p>将刚刚复制的数据粘贴到手机端的<strong>追放夏克里助手</strong>中即可查看完整分析报告！</p>
              </el-alert>

              <h4 class="sub-title">操作步骤</h4>
              <ol class="step-list">
                <li><strong>打开小程序</strong> — 在微信中搜索并打开「追放夏克里助手」小程序。</li>
                <li><strong>进入抽卡分析</strong> — 首页点击「<strong>抽卡分析</strong>」入口。</li>
                <li><strong>粘贴数据</strong> — 在页面中找到输入框，长按后选择"<strong>粘贴</strong>"，将刚才从电脑端复制的内容粘贴进去。</li>
                <li><strong>开始分析</strong> — 点击「<strong>开始分析</strong>」按钮，等待几秒钟后系统会自动处理数据。</li>
                <li><strong>查看报告</strong> — 分析完成后会自动跳转到详情页，展示以下信息：
                  <ul class="inner-list">
                    <li><strong>总体概览</strong>：总抽数、SSR 数量、保底率、歪的次数</li>
                    <li><strong>各池子详情</strong>：角色池、武器池、常驻池、自选池分别统计</li>
                    <li><strong>每条 SSR 记录</strong>：道具名称、类型、花费抽数、是否歪了</li>
                    <li><strong>欧皇值评分</strong>：综合评价你的运气水平</li>
                  </ul>
                </li>
              </ol>

              <h4 class="sub-title">后续功能</h4>
              <ul class="step-list">
                <li><strong>查看历史</strong> — 分析过的 UID 会自动保存，可以在「历史记录」中快速回看</li>
                <li><strong>排行榜对比</strong> — 在「排行榜」中查看全服玩家的欧皇/非酋/氪佬排名</li>
                <li><strong>重复查询</strong> — 再次获取新数据后重新粘贴分析即可更新记录</li>
              </ul>
            </div>
          </transition>
        </div>

        <!-- 第三步：常见问题 -->
        <div class="main-step">
          <div class="main-step__head" @click="toggleStep(2)">
            <div class="main-step__icon" style="background: #e6a23c">
              <el-icon><QuestionFilled /></el-icon>
            </div>
            <span class="main-step__title">常见问题与提示</span>
            <el-icon class="main-step__arrow" :class="{ 'is-expanded': expandedSteps[2] }"><ArrowDown /></el-icon>
          </div>
          <transition name="step-collapse">
            <div v-show="expandedSteps[2]" class="main-step__body">
              <div class="faq-list">
                <div
                  v-for="(faq, index) in faqList"
                  :key="'faq' + index"
                  class="faq-item"
                >
                  <div class="faq-item__head" @click.stop="toggleFaq(index)">
                    <span class="faq-item__num">{{ index + 1 }}</span>
                    <span class="faq-item__title">{{ faq.title }}</span>
                    <el-icon class="faq-item__arrow" :class="{ 'is-expanded': activeFaqIndex === index }"><ArrowRight /></el-icon>
                  </div>
                  <transition name="step-collapse">
                    <div v-show="activeFaqIndex === index" class="faq-item__body">
                      <p>{{ faq.content }}</p>
                    </div>
                  </transition>
                </div>
              </div>
            </div>
          </transition>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { DocumentCopy, Monitor, Iphone, QuestionFilled, ArrowDown, ArrowRight } from '@element-plus/icons-vue'

const expandedSteps = reactive([true, false, false])
const activeFaqIndex = ref(-1)

const faqList = [
  {
    title: '复制的数据是什么？安全吗？',
    content: '复制的内容是你在游戏中进行抽卡操作时产生的标准游戏请求信息，仅包含你的抽卡记录数据（UID、抽到了什么、花了多少抽等），不含任何密码或敏感个人信息。数据仅用于本地分析，不会发送给任何第三方。'
  },
  {
    title: "提示'证书不受信任'怎么办？",
    content: "首次使用桌面端工具时，Windows 会弹出安全证书安装提示。请选择\"是/允许\"来安装证书。这是为了让工具能够识别和读取游戏的加密通信数据。如果你不小心点了\"否\"，可以重新运行程序再次尝试。"
  },
  {
    title: "为什么粘贴后显示'解析失败'？",
    content: "请检查以下几点：① 确认你复制的是桌面端程序中\"获取抽卡记录\"后的完整文本 ② 确认没有多余的前缀或后缀字符（如空格、换行） ③ 确认游戏账号已经进行过至少一次抽卡操作  如果仍然失败，请在桌面端重新执行一次\"获取抽卡记录\"步骤。"
  },
  {
    title: "'歪了'是什么意思？",
    content: "在限定卡池（角色池/武器池）中抽到常驻 SSR（即该池子 UP 以外的固定五星物品），就称为\"歪了\"。比如你在角色 UP 池里抽到的却是常驻角色，那就是\"歪了\"。系统会自动帮你标记每条记录是否歪了。"
  },
  {
    title: '数据多久更新一次？',
    content: "每次你在桌面端点击\"获取抽卡记录\"都会拉取最新的完整数据。你可以随时重新操作并将新的数据粘贴到手机端进行分析，系统会自动覆盖更新你之前的记录。"
  },
  {
    title: '欧皇值是怎么计算的？',
    content: "欧皇值综合考量三个维度：• 平均抽数：每出一个 SSR 平均花多少抽（越少越好）• 不歪率：在限定池中没歪的概率（越高越好）• 早出率：在前 30 抽内出 SSR 的比例（越高越好）  三项加权得出最终评分，分数越高说明运气越好！"
  }
]

function toggleStep(index: number) {
  expandedSteps[index] = !expandedSteps[index]
}

function toggleFaq(index: number) {
  if (expandedSteps[2]) {
    activeFaqIndex.value = activeFaqIndex.value === index ? -1 : index
  }
}
</script>

<style lang="scss" scoped>
.guide-card {
  border-radius: 12px;

  .card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 700;
    font-size: 18px;
    color: #303133;
  }
}

/* ===== 主步骤 ===== */
.guide-steps {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.main-step {
  background: #fff;
  border-radius: 10px;
  border: 1px solid #ebeef5;
  overflow: hidden;
  transition: box-shadow 0.25s ease;

  &:hover {
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  }
}

.main-step__head {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 20px;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s ease;

  &:hover {
    background-color: #f8fafc;
  }
}

.main-step__icon {
  width: 38px;
  height: 38px;
  min-width: 38px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;

  .el-icon {
    font-size: 19px;
  }
}

.main-step__title {
  font-size: 15px;
  font-weight: 700;
  color: #303133;
  line-height: 1.4;
  flex: 1;
}

.main-step__arrow {
  color: #909399;
  font-size: 13px;
  flex-shrink: 0;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);

  &.is-expanded {
    transform: rotate(180deg);
  }
}

.main-step__body {
  padding: 0 20px 20px 72px;
  color: #606266;
  line-height: 1.8;
  overflow: hidden;
}

/* ===== 小步骤 / 内容区域 ===== */
.step-alert {
  margin-bottom: 18px;

  p {
    margin: 0;
    line-height: 1.8;
  }
}

.sub-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin: 18px 0 8px;

  &:first-of-type {
    margin-top: 0;
  }
}

.step-list {
  padding-left: 18px;
  margin: 0;

  li {
    margin-bottom: 6px;
    line-height: 1.8;

    strong {
      color: #303133;
    }
  }
}

.inner-list {
  margin: 6px 0 6px 22px;
  padding-left: 0;

  li {
    list-style-type: disc;
    margin-bottom: 3px;
  }
}

/* ===== FAQ 子列表（第三步的小步骤） ===== */
.faq-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.faq-item {
  background: #f7f9fc;
  border-radius: 8px;
  overflow: hidden;
}

.faq-item__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 16px;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s ease;

  &:hover {
    background-color: #edf1f7;
  }
}

.faq-item__num {
  width: 22px;
  height: 22px;
  min-width: 22px;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.faq-item__title {
  font-size: 14px;
  font-weight: 600;
  color: #409eff;
  line-height: 1.5;
  flex: 1;
}

.faq-item__arrow {
  color: #409eff;
  font-size: 12px;
  flex-shrink: 0;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);

  &.is-expanded {
    transform: rotate(90deg);
  }
}

.faq-item__body {
  padding: 12px 16px 14px 48px;
  background: #f0f7ff;
  border-radius: 0 0 8px 8px;

  p {
    margin: 0;
    font-size: 13px;
    color: #606266;
    line-height: 1.8;
  }
}

/* ===== 折叠动画 ===== */
.step-collapse-enter-active,
.step-collapse-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.step-collapse-enter-from,
.step-collapse-leave-to {
  opacity: 0;
  max-height: 0 !important;
  padding-top: 0;
  padding-bottom: 0;
  margin-top: 0;
  margin-bottom: 0;
}
</style>
