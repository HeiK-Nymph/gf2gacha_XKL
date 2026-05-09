import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import useUserStore from '@/stores/user'
import { constantRoutes } from '@/stores/user'

NProgress.configure({ showSpinner: false })

/**
 * 从 constantRoutes 中递归查找目标路径对应的 meta.roles
 * 正确处理嵌套路由的路径拼接：父级 path + 子级 path = 完整路径
 */
function getRouteRoles(targetPath: string, routes: typeof constantRoutes, parentPath: string = ''): number[] | undefined {
  for (const route of routes) {
    // 计算完整路径：父路径 + 当前路由路径（去除重复斜杠）
    const fullPath = parentPath
      ? `${parentPath.replace(/\/$/, '')}/${route.path.replace(/^\//, '')}`
      : route.path

    if (fullPath === targetPath) {
      return route.meta?.roles
    }
    if (route.children) {
      const childRoles = getRouteRoles(targetPath, route.children, fullPath)
      if (childRoles !== undefined) return childRoles
    }
  }
  return undefined
}

// 将 MenuRoute 转换为 Vue Router 可用的路由
// 注意：不在此处过滤 hidden 路由，hidden 仅用于侧边栏菜单展示过滤
function convertToVueRoutes(routes: typeof constantRoutes): RouteRecordRaw[] {
  return routes
    .map((route) => ({
      path: route.path,
      name: route.name as string,
      component: route.component,
      redirect: route.redirect,
      meta: route.meta || {},
      children: route.children ? convertToVueRoutes(route.children) : undefined,
    })) as RouteRecordRaw[]
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: convertToVueRoutes(constantRoutes),
})

// 白名单（不需要登录即可访问）
const whiteList = ['/login', '/register']

router.beforeEach((_to, _from, next) => {
  NProgress.start()
  const userStore = useUserStore()

  if (userStore.token) {
    if (_to.path === '/login') {
      next({ path: '/' })
    } else {
      // 初始化用户信息
      if (!userStore.userInfo) {
        userStore.initFromStorage()
      }

      // ===== 角色权限校验 =====
      if (!userStore.userInfo) {
        NProgress.done()
        userStore.logout()
        next('/login')
        return
      }

      const requiredRoles = getRouteRoles(_to.path, constantRoutes)
      if (requiredRoles && requiredRoles.length > 0) {
        const currentRole = userStore.userInfo.role
        if (!requiredRoles.includes(currentRole)) {
          NProgress.done()
          next({ path: '/' })
          return
        }
      }
      // ============================
      next()
    }
  } else {
    if (whiteList.includes(_to.path)) {
      next()
    } else {
      next(`/login?redirect=${_to.path}`)
    }
  }
})

router.afterEach(() => {
  NProgress.done()
})

export default router
