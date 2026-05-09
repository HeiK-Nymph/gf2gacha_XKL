import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { SysUser, MenuRoute } from '@/types'

// 静态路由配置（根据后端 sys_user.role 动态过滤）
export const constantRoutes: MenuRoute[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录', hidden: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/register/index.vue'),
    meta: { title: '注册', hidden: true },
  },
  {
    path: '/',
    component: () => import('@/layout/index.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '仪表盘', icon: 'Odometer', roles: [0, 1], affix: true },
      },
      {
        path: 'gacha-query',
        name: 'GachaQuery',
        component: () => import('@/views/gacha/query.vue'),
        meta: { title: '抽卡查询', icon: 'Search', roles: [0, 1] },
      },
      {
        path: 'ranking',
        name: 'Ranking',
        component: () => import('@/views/gacha/ranking.vue'),
        meta: { title: '排行榜', icon: 'Trophy', roles: [0, 1] },
      },
      {
        path: 'ssr-item',
        name: 'SsrItem',
        component: () => import('@/views/ssr/item-manage.vue'),
        meta: { title: 'SSR物品管理', icon: 'Box', roles: [1] },
      },
      {
        path: 'user-manage',
        name: 'UserManage',
        component: () => import('@/views/system/user-manage.vue'),
        meta: { title: '用户管理', icon: 'UserFilled', roles: [1] },
      },
      {
        path: 'system-config',
        name: 'SystemConfig',
        component: () => import('@/views/system/config.vue'),
        meta: { title: '系统设置', icon: 'Setting', roles: [1] },
      },
      {
        path: 'guide',
        name: 'Guide',
        component: () => import('@/views/guide/index.vue'),
        meta: { title: '操作指南', icon: 'DocumentCopy', roles: [0, 1], hidden: true },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/404.vue'),
    meta: { title: '404', hidden: true },
  },
]

const useUserStore = defineStore('user', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const userInfo = ref<SysUser | null>(null)

  function setToken(val: string) {
    token.value = val
    localStorage.setItem('token', val)
  }

  function setUserInfo(user: SysUser) {
    userInfo.value = user
    localStorage.setItem('userInfo', JSON.stringify(user))
  }

  // 根据角色过滤可访问的路由菜单
  function getAccessibleRoutes(): MenuRoute[] {
    const role = userInfo.value?.role ?? 0
    return filterRoutesByRole(constantRoutes, role)
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
  }

  // 初始化：从 localStorage 恢复
  function initFromStorage() {
    const savedInfo = localStorage.getItem('userInfo')
    if (savedInfo) {
      try {
        userInfo.value = JSON.parse(savedInfo)
      } catch {
        userInfo.value = null
      }
    }
  }

  return {
    token,
    userInfo,
    setToken,
    setUserInfo,
    getAccessibleRoutes,
    logout,
    initFromStorage,
  }
})

// 递归过滤路由（仅用于侧边栏菜单展示，hidden 路由不显示在菜单中）
function filterRoutesByRole(routes: MenuRoute[], role: number): MenuRoute[] {
  return routes
    .filter((route) => {
      // hidden 路由（如 /login、404）不显示在侧边栏菜单中
      if (route.meta?.hidden) return false
      // 按角色权限过滤
      if (route.meta?.roles && !route.meta.roles.includes(role)) return false
      return true
    })
    .map((route) => ({
      ...route,
      children: route.children ? filterRoutesByRole(route.children, role) : undefined,
    }))
}

export default useUserStore
