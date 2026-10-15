import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: './',
  build: {
    // 产物扁平化：GitHub Pages 的网页版「上传文件」不保留子目录，
    // 把 js/css 直接放在 html 旁边，上传后路径才不会断。
    assetsDir: '',
  },
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
