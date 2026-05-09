<template>
  <div class="not-found">
    <h1 class="code">404</h1>
    <p class="desc">抱歉，您访问的页面不存在</p>
    <el-button type="primary" @click="$router.push('/')">返回首页</el-button>
  </div>
</template>

<script setup lang="ts">
</script>

<style lang="scss" scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;

  .code {
    font-size: 120px;
    font-weight: 900;
    color: #c0c4cc;
    line-height: 1;
    margin: 0 0 16px;
  }

  .desc {
    font-size: 18px;
    color: #909399;
    margin: 0 0 32px;
  }
}
</style>
