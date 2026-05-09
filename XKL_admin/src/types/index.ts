// ========== 统一响应结构 ==========
export interface Result<T = any> {
  code: number
  msg: string
  data: T
}

// ========== 系统用户相关 ==========
export interface SysUser {
  id: number
  username: string
  password?: string
  role: number // 0=普通用户, 1=管理员
  status: string // '0'=封禁, '1'=正常
  lastLoginTime: string | null
  isDeleted: number
  createdAt: string
  updatedAt: string
  _loading?: boolean // UI 行级 loading 状态（非后端字段）
}

export interface LoginReq {
  username: string
  password: string
}

export interface RegisterReq {
  username: string
  password: string
  inviteCode: string
}

export interface LoginRes {
  token: string
  user: SysUser
}

// ========== 游戏用户相关 ==========
export interface GfUser {
  id: number
  uid: number
  sysUserId: number | null
  isDeleted: number
  createdAt: string
  updatedAt: string
  _loading?: boolean // UI 行级 loading 状态（非后端字段）
}

export interface GfUserDTO {
  uid: number
  totalDraws: number
  totalSSR: number
  safeRate: number
  waiCnt: number
  avgCharacter: number
  avgWeapon: number
  avgPermanent: number
  gachaRecordsList: GachaRecordsVO[]
}

// ========== 抽卡记录相关 ==========
export interface GachaRecordsVO {
  poolType: number // 1常驻/3角色/4武器/6自选角色/7自选武器
  totalDraws: number
  totalSSR: number
  waiCnt: number
  gachaItems: GachaItemVO[]
}

export interface GachaItemVO {
  itemId: number
  itemName: string
  itemType: number // 0占位/10人形/20武器
  ssrType: number // 0占位/1限定角色/2限定武器/3常驻
  costDraws: number
  drawOrder: number
  poolType: number
  isWai: number
}

// ========== SSR物品相关 ==========
export interface GfSsrItem {
  id: number
  itemId: number
  itemName: string
  itemType: number // 10=人形, 20=武器
  ssrType: number // 1=限定角色, 2=限定武器, 3=常驻
  isDeleted: number
  createdAt: string
  updatedAt: string
  _loading?: boolean // UI 行级 loading 状态（非后端字段）
}

export interface GfSsrItemDTO {
  itemId: number
  itemName: string
  itemType: number
  ssrType: number
}

export interface GfSsrItemBatchDTO {
  GfSsrItemList: GfSsrItemDTO[]
}

// ========== Web端抽卡数据请求 ==========
export interface FirstRequestDTO {
  firstJson: Record<string, any>
}

// ========== 排行榜相关 ==========
export interface GfGachaRankingListVO {
  userId: number
  luckValue: number
  totalDraws: number
}

export interface GfGachaRankingListDTO {
  gfGachaRankingListOrderByLuckValueDesc: GfGachaRankingListVO[]
  gfGachaRankingListOrderByTotalDrawsDesc: GfGachaRankingListVO[]
}

// ========== 路由菜单相关 ==========
export interface RouteMeta {
  title: string
  icon?: string
  hidden?: boolean
  roles?: number[] // 允许的角色列表
  affix?: boolean
  single?: boolean // 是否单级菜单（不折叠）
}

export interface MenuRoute {
  path: string
  name?: string
  component?: any
  redirect?: string
  meta?: RouteMeta
  children?: MenuRoute[]
}
