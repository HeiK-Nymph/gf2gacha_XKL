<template>
  <router-view />
</template>

<script setup lang="ts">
// App root component - only renders router-view
</script>

<style>
/* Global reset & base styles */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  width: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  background-color: #f0f2f5;
}

/* Scrollbar styling */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-thumb {
  background-color: rgba(144, 147, 153, 0.35);
  border-radius: 3px;

  &:hover {
    background-color: rgba(144, 147, 153, 0.55);
  }
}

/* NProgress custom color */
#nprogress .bar {
  background: #409eff !important;
}
</style>
