import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './styles/tokens.css'

// 组件层全部手写（src/ui/），不再依赖 Element Plus —— 见 docs/decisions-desktop-enterprise.md D5
const app = createApp(App)

app.use(createPinia())

app.mount('#app')
