import request from '@/utils/request'
import type { Result, LoginReq, RegisterReq, LoginRes, SysUser, GfUserDTO, GfSsrItem, GfSsrItemDTO, GfSsrItemBatchDTO, GfGachaRankingListDTO, FirstRequestDTO } from '@/types'

// ========== 认证相关（后端待实现）==========
export const loginApi = (data: LoginReq): Promise<Result<LoginRes>> =>
  request.post('/sys-auth/login', data)

export const registerApi = (data: RegisterReq): Promise<Result<null>> =>
  request.post('/sys-auth/register', data)

// ========== 系统用户管理（后端待实现）==========
export const getSysUserListApi = (): Promise<Result<SysUser[]>> =>
  request.get('/sys-user/list')

export const updateSysUserRoleApi = (username: string, role: number): Promise<Result<null>> =>
  request.post('/sys-user/updateRole', { username, role })

export const updateSysUserStatusApi = (username: string, status: string): Promise<Result<null>> =>
  request.post('/sys-user/updateStatus', { username, status })

export const removeSysUserApi = (username: string): Promise<Result<null>> =>
  request.post('/sys-user/remove', { username })

// ========== 游戏用户 / 抽卡数据 ==========
export const getGfUserByUidApi = (uid: number): Promise<Result<GfUserDTO>> =>
  request.get('/gf-user/get', { params: { uid } })

export const fetchGachaFromWebApi = (data: FirstRequestDTO): Promise<Result<GfUserDTO>> =>
  request.post('/gacha-web/get', data)

// ========== SSR物品管理 ==========
export const getSsrItemAllApi = (): Promise<Result<GfSsrItem[]>> =>
  request.get('/gf-ssr-item/getAll')

export const getSsrItemByItemIdApi = (itemId: number): Promise<Result<GfSsrItem>> =>
  request.get('/gf-ssr-item/getByItemId', { params: { itemId } })

export const insertSsrItemBatchApi = (data: GfSsrItemBatchDTO): Promise<Result<null>> =>
  request.post('/gf-ssr-item/insertList', data)

export const removeSsrItemByItemIdApi = (itemId: number): Promise<Result<null>> =>
  request.post('/gf-ssr-item/removeByItemId', { itemId })

export const restoreAllSsrItemsApi = (): Promise<Result<null>> =>
  request.post('/gf-ssr-item/restoreAll')

export const getDeletedSsrItemsApi = (): Promise<Result<GfSsrItem[]>> =>
  request.get('/gf-ssr-item/getDeleted')

export const restoreSsrItemByItemIdApi = (itemId: number): Promise<Result<null>> =>
  request.post('/gf-ssr-item/restoreByItemId', { itemId })

export const deleteSsrItemsByIsDeletedApi = (): Promise<Result<null>> =>
  request.post('/gf-ssr-item/deleteByIsDeleted')

// ========== 排行榜 ==========
export const getRankingListApi = (): Promise<Result<GfGachaRankingListDTO>> =>
  request.get('/gf-gacha-ranking/get')

// ========== 仪表盘统计（仅管理员）==========
export const getUserCountApi = (): Promise<Result<number>> =>
  request.get('/sys-user/count')

export const getSsrItemCountApi = (): Promise<Result<number>> =>
  request.get('/gf-ssr-item/count')

export const getActiveUserCountApi = (): Promise<Result<number>> =>
  request.get('/gf-gacha-ranking/count')
