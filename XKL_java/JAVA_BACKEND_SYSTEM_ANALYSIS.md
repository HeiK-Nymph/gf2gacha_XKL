# XKL_java 后端系统分析文档

> **项目**: 少女前线2 (GF2) 抽卡管理系统后端服务  
> **框架**: Spring Boot 4.0.5 + MyBatis + MySQL + WebFlux WebClient  
> **Java版本**: 17  
> **架构模式**: Controller → Service → Mapper 三层架构 + JWT RBAC 权限控制

---

## 目录

- [一、系统总体架构](#一系统总体架构)
- [二、技术栈与依赖](#二技术栈与依赖)
- [三、数据库设计](#三数据库设计)
- [四、模块详解与类关系图](#四模块详解与类关系图)
- [五、API接口完整链路分析（逐个端点）](#五api接口完整链路分析逐个端点)
- [六、核心业务逻辑深度剖析](#六核心业务逻辑深度剖析)
- [七、安全认证机制](#七安全认证机制)
- [八、异常处理体系](#八异常处理体系)

---

## 一、系统总体架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                          客户端层                                     │
│   XKL_admin(管理后台) / XKL_uniapp(UniApp移动端)                      │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ HTTP/JSON REST API
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       Controller 控制层 (6个)                         │
│                                                                      │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────┐                 │
│  │GachaWebCtrl │ │ SysAuthCtrl  │ │ SysUserCtrl   │  @RequireRole  │
│  │ /api/gacha- │ │ /api/sys-auth│ │ /api/sys-user │    (1)         │
│  │  web/get    │ │ login/register│ │ CRUD+RBAC     │                │
│  └──────┬──────┘ └──────┬───────┘ └───────┬───────┘                 │
│         │               │                  │                          │
│  ┌──────┴──────┐ ┌──────┴───────┐ ┌───────┴───────┐                 │
│  │ GfUserCtrl  │ │GfSsrItemCtrl │ │RankingListCtrl│                 │
│  │/api/gf-user │ │/api/gf-ssr-  │ │/api/gf-gacha- │                │
│  │  /get(uid)  │ │ item (CRUD)  │ │ ranking       │                 │
│  └──────┬──────┘ └──────┬───────┘ └───────┬───────┘                 │
└─────────┼───────────────┼─────────────────┼──────────────────────────┘
          │               │                 │
          ▼               ▼                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        Service 业务逻辑层 (5个)                       │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │              GachaWebService [核心 - 645行]              │        │
│  │  异步抓取GF2官方API → fakeId去重合并 → SSR记录构建 →      │        │
│  │  历史持久化 → 欧皇值计算 → 排行榜更新                     │        │
│  └──────────────────────┬───────────────────────────────────┘        │
│                         │                                            │
│  ┌────────────┐ ┌──────┴──────┐ ┌──────────┐ ┌────────────────┐    │
│  │SysAuthService│ │GfUserService│ │SsrItemSvc│ │RankingListSvc  │    │
│  │JWT签发/RBAC  │ │DTO组装/统计  │ │SSR字典CRUD│ │排行榜查询      │    │
│  └──────┬───────┘ └──────┬──────┘ └────┬─────┘ └───────┬────────┘   │
└─────────┼────────────────┼─────────────┼────────────────┼────────────┘
          │                │             │                │
          ▼                ▼             ▼                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Mapper 持久层 (6对 接口+XML)                       │
│                                                                      │
│  GfGachaHistoryMapper  |  GfGachaSsrRecordMapper  |  GfUserMapper   │
│  GfSsrItemMapper       |  RankingListMapper        |  SysUserMapper │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     MySQL 数据库 (6张表)                              │
│  sys_user | gf_user | gf_ssr_item | gf_gacha_history |              │
│  gf_gacha_ssr_record | gf_gacha_ranking_list                            │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 二、技术栈与依赖

| 分类 | 技术 | 版本 | 用途说明 |
|------|------|------|----------|
| **核心框架** | Spring Boot (spring-boot-starter-webmvc) | 4.0.5 | MVC Web层，REST API |
| **ORM** | MyBatis (mybatis-spring-boot-starter) | 4.0.1 | 半自动ORM，SQL映射 |
| **数据库** | MySQL Connector/J | managed | JDBC驱动 |
| **异步HTTP** | WebFlux WebClient (reactor-netty) | managed | 非阻塞异步调用GF2官方API |
| **JWT认证** | JJWT (jjwt-api/impl/jackson) | 0.12.6 | Token生成与校验 |
| **密码加密** | Spring Security Crypto (BCrypt) | managed | 密码哈希存储 |
| **序列化** | Jackson (jackson-databind) | 2.20.1 | JSON处理 |
| **简化代码** | Lombok | managed | 注解生成Getter/Setter/Constructor |

### 外部API端点

| 端点URL | 用途 | 调用方式 |
|---------|------|----------|
| `https://gf2-gacha-record.sunborngame.com/list` | 获取抽卡记录（分页） | POST, form-urlencoded |
| `https://gf2-zoneinfo.sunborngame.com/account/info` | 获取用户UID | POST, JSON |

---

## 三、数据库设计

### 3.1 ER关系图

```
sys_user (1) ────< (N) gf_user (1) ────< (N) gf_gacha_history (1) ────< (N) gf_gacha_ssr_record
                                                                                    |
                                                                                    |
                                                                              gf_ssr_item (1)
                                                                                    
gf_user (1) ────< (1) gf_gacha_ranking_list
```

### 3.2 表结构详解

#### sys_user — 系统用户表 (RBAC)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK, AUTO_INCREMENT | 主键 |
| username | VARCHAR(64) | NOT NULL, UNIQUE | 用户名 |
| password | VARCHAR(128) | NOT NULL | BCrypt哈希密码 |
| role | INT | DEFAULT 0 | 0=普通用户, 1=管理员 |
| status | CHAR(1) | DEFAULT '1' | 0=封禁, 1=正常 |
| last_login_time | DATETIME | NULLABLE | 最后登录时间 |
| is_deleted | INT | DEFAULT 0 | 逻辑删除标记 |
| created_at / updated_at | DATETIME | AUTO | 时间戳 |

> 默认管理员: **admin / admin123**

#### gf_user — 游戏玩家表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 主键 |
| uid | INT UNIQUE | 游戏内UID（来自GF2账号信息API） |
| sys_user_id | BIGINT | 关联系统用户（可选绑定） |

#### gf_ssr_item — SSR物品字典表

| 字段 | 说明 |
|------|------|
| item_id (INT UNIQUE) | 游戏道具原始ID |
| item_name | 物品名称 |
| item_type | 10=人形, 20=武器 |
| ssr_type | 1=限定角色, 2=限定武器, 3=常驻 |
| is_deleted | 逻辑删除（支持回收站功能） |

#### gf_gacha_history — 抽卡历史记录表（快照式存储）

| 字段 | 说明 |
|------|------|
| user_id (FK→gf_user.id) | 所属玩家 |
| permanent_pool_json (TEXT) | 常驻池数据 (poolType=1), JSON数组格式 |
| character_pool_json (TEXT) | 角色池数据 (poolType=3) |
| weapon_pool_json (TEXT) | 武器池数据 (poolType=4) |
| custom_character_pool_json (TEXT) | 自选角色池数据 (poolType=6) |
| custom_weapon_pool_json (TEXT) | 自选武器池数据 (poolType=7) |

> **关键设计**: JSON字段存储的是重建后的分页格式 `[{code:0, message:"OK", data:{list:[6条], next:""}}]`，保持与GF2官方API响应格式一致以实现向后兼容。

#### gf_gacha_ssr_record — SSR抽卡明细表（规范化存储）

| 字段 | 说明 |
|------|------|
| user_id (FK→gf_user.id) | 所属玩家 |
| history_id (FK→gf_gacha_history.id) | 关联的历史快照 |
| pool_type | 卡池类型: 1常驻/3角色/4武器/6自选角色/7自选武器 |
| item_id | SSR物品ID (0=占位符"question")，关联 gf_ssr_item.id |
| draw_order | 池内顺序号（0=最新垫刀状态, 1+=真实SSR序号） |
| cost_draws | 抽出该SSR所花费的抽数（含自身1抽）；itemId=0时表示垫抽数 |

#### gf_gacha_ranking_list — 排行榜表

| 字段 | 说明 |
|------|------|
| user_id (FK→gf_user.id, UNIQUE) | 所属玩家（唯一） |
| luck_value | 欧皇值（综合评分算法计算） |
| total_draws | 总抽数 |

---

## 四、模块详解与类关系图

### 4.1 完整包结构与职责

```
org.example.xkl_java/
├── XklJavaApplication.java          # 启动入口, @MapperScan("...mapper")
├── bean/                            # [实体层] 数据库表映射对象
│   ├── SysUser.java                 # 系统用户
│   ├── GfUser.java                  # 游戏玩家
│   ├── GfGachaHistory.java          # 抽卡历史快照
│   ├── GfGachaSsrRecord.java        # SSR抽卡明细
│   ├── GfSsrItem.java               # SSR物品字典
│   └── GfGachaRankingList.java      # 排行榜记录
├── common/
│   └── Result.java                  # 统一响应封装 {code, msg, data}
├── config/
│   ├── SecurityConfig.java          # WebMvcConfigurer: 注册JWT拦截器+CORS
│   ├── WebClientConfig.java         # WebClient Bean配置(连接池/超时/内存)
│   ├── RestTemplateConfig.java      # (备用同步HTTP客户端)
│   └── MyBatisConfig.java           # MyBatis配置
├── controller/                      # [控制层] REST API入口
│   ├── GachaWebController.java      # POST /api/gacha-web/get
│   ├── SysAuthController.java       # 登录/注册
│   ├── SysUserController.java       # 用户管理CRUD (@RequireRole(1))
│   ├── GfUserController.java        # GET /api/gf-user/get?uid=
│   ├── GfSsrItemController.java     # SSR物品CRUD+回收站 (@RequireRole(1))
│   └── GfGachaRankingListController.java  # 排行榜查询
├── dto/                             # [请求入参]
│   ├── firstRequestDTO.java         # {firstJson: {headers, body, params}}
│   ├── SysAuthDTO.java              # {username, password, inviteCode}
│   ├── GfUserDTO.java               # 抽卡数据汇总响应DTO
│   ├── GfSsrItemDTO.java            # SSR物品传输对象
│   ├── GfSsrItemBatchDTO.java       # 批量插入DTO
│   ├── GfGachaRankingListDTO.java   # 排行榜响应DTO
│   ├── SysUserListDTO.java          # 用户列表查询参数
│   └── SysUserListVO.java           # 用户列表视图输出
├── vo/                              # [响应出参] 视图对象
│   ├── GachaItemVO.java             # 单条抽卡物品视图
│   ├── GachaRecordsVO.java          # 单池抽卡统计视图
│   └── GfGachaRankingListVO.java    # 排行榜条目视图
├── exception/
│   ├── BusinessException.java       # 业务异常 {code, message}
│   └── GlobalExceptionHandler.java  # @RestControllerAdvice 全局异常兜底
├── mapper/                          # [持久层] MyBatis Mapper接口 + XML
│   ├── *Mapper.java (6个接口)
│   └── resources/mapper/*.xml (6个映射文件)
├── security/                        # [安全层]
│   ├── JwtUtil.java                 # JWT工具: 生成/解析/校验Token
│   ├── JwtAuthInterceptor.java      # HandlerInterceptor: 认证+鉴权拦截器
│   ├── LoginUser.java               # 当前登录用户上下文(ThreadLocal)
│   └── RequireRole.java             # @RequireRole 角色权限注解
└── service/                         # [业务逻辑层]
    ├── GachaWebService.java         # [★核心★] 抽卡数据全流程处理
    ├── SysAuthService.java          # 认证授权+用户管理
    ├── GfUserService.java           # 抽卡数据查询+DTO组装+欧皇值计算
    ├── GfSsrItemService.java        # SSR字典CRUD
    └── GfGachaRankingListService.java  # 排行榜查询
```

### 4.2 核心依赖注入关系

```
GachaWebService (★核心★)
  ├─ GfGachaHistoryMapper        // 历史快照CRUD
  ├─ GfGachaRankingListMapper    // 排行榜Upsert
  ├─ GfGachaSsrRecordMapper      // SSR明细批量操作
  ├─ GfSsrItemMapper             // SSR字典查询
  ├─ GfUserMapper                // 玩家查找/创建
  ├─ GfUserService               // DTO组装 + 欧皇值计算
  └─ WebClient                   // 异步HTTP客户端(Spring Bean)

SysAuthService
  ├─ SysUserMapper               // 用户CRUD
  └─ JwtUtil                     // JWT签发

GfUserService
  └─ GfGachaSsrRecordMapper      // 查询SSR记录(含JOIN gf_ssr_item)

GfSsrItemService
  └─ GfSsrItemMapper             // SSR字典完整CRUD+回收站

GfGachaRankingListService
  └─ GfGachaRankingListMapper    // 排行榜排序查询+计数
```

---

## 五、API接口完整链路分析（逐个端点）

### 5.1 `POST /api/sys-auth/login` — 用户登录

**权限**: 公开（白名单，无需Token）

#### 代码执行链路

```
[HTTP请求] POST /api/sys-auth/login
  Body: {"username":"admin", "password":"admin123"}
  │
  ▼
[SecurityConfig.addInterceptors]
  → excludePathPatterns 包含 "/api/sys-auth/login"
  → JwtAuthInterceptor.preHandle(): 白名单匹配 → 直接放行 true
  │
  ▼
[SysAuthController.login()]  (第28-31行)
  → sysAuthService.login(dto)
  │
  ▼
[SysAuthService.login()]  (第57-102行)
  │
  ├─ 步骤1: 参数校验 (第59-64行)
  │   ├─ username为空? → throw BusinessException("用户名不能为空")
  │   └─ password为空? → throw BusinessException("密码不能为空")
  │
  ├─ 步骤2: 查询用户 (第67行)
  │   └─ sysUserMapper.getSysUserByUsername(username)
  │      → SQL: SELECT * FROM sys_user WHERE BINARY username=? AND is_deleted=0
  │      → user == null? → throw BusinessException(LOGIN_FAIL_MSG)  // 安全防枚举!
  │
  ├─ 步骤3: BCrypt密码校验 (第74行)
  │   └─ PASSWORD_ENCODER.matches(inputPwd, storedHash)
  │      → 不匹配? → throw BusinessException(LOGIN_FAIL_MSG)  // 同样模糊提示!
  │
  ├─ 步骤4: 账号状态检查 (第79行)
  │   └─ status=="0"? → throw BusinessException("该账号已被封禁")
  │
  ├─ 步骤5: 生成JWT (第84行)
  │   └─ jwtUtil.generateToken(username, userId, role)
  │      → Claims: {subject: username, userId: xxx, role: 0|1}
  │      → HS256签名, 过期时间 = now + 86400000ms (24小时)
  │
  ├─ 步骤6: 更新最后登录时间 (第87行)
  │   └─ sysUserMapper.updateLastLoginTimeByUsername(username, now)
  │      → SQL: UPDATE sys_user SET last_login_time=? WHERE username=?
  │
  └─ 步骤7: 构造返回数据 (第89-101行)
      └─ Result<Map> {
          code: 200,
          msg: "success",
          data: {
            token: "eyJhbGciOiJIUzI1NiJ9...",
            user: {id, username, role, loginTime}
          }
        }
```

#### 业务逻辑意图

- **安全设计**: 用户不存在和密码错误返回完全相同的提示 `"登录失败，请检查用户名和密码"`，防止通过响应差异枚举有效用户名
- **BCrypt哈希**: 密码使用BCrypt单向哈希存储，每次加密结果不同（内置随机salt），验证时用 `matches()` 方法
- **JWT Payload**: 携带 `userId`(Long)、`role`(Integer) 用于后续请求的权限判断
- **登录时间追踪**: 每次成功登录更新 `last_login_time`，便于审计

---

### 5.2 `POST /api/sys-auth/register` — 用户注册

**权限**: 公开（白名单）

#### 代码执行链路

```
[HTTP请求] POST /api/sys-auth/register
  Body: {"username":"newuser", "password":"123456", "inviteCode":"52894"}
  │
  ▼
[SysAuthController.register()]  (第39-42行)
  → sysAuthService.register(dto)
  │
  ▼
[SysAuthService.register()]  (第107-146行)
  │
  ├─ 步骤1: 参数校验 (第109-120行)
  │   ├─ username/password 非空检查
  │   ├─ password.length >= 4?
  │   └─ inviteCode非空?
  │
  ├─ 步骤2: 邀请码映射角色 (第123行)
  │   └─ INVITE_CODE_ROLE_MAP.get(inviteCode)
  │      "52894" → 1 (管理员)
  │      "52614" → 0 (普通用户)
  │      其他   → null → throw BusinessException("邀请码无效")
  │
  ├─ 步骤3: 用户名唯一性检查 (第129行)
  │   └─ existing != null? → throw BusinessException("该用户名已被注册")
  │
  ├─ 步骤4: 创建用户 (第135-144行)
  │   ├─ password = PASSWORD_ENCODER.encode(rawPassword)  // BCrypt加密
  │   ├─ role = assignedRole  // 由邀请码决定
  │   ├─ status = "1"  // 正常状态
  │   └─ sysUserMapper.insertSysUser(newUser)
  │      → SQL: INSERT INTO sys_user(username,password,role,status,...)
  │
  └─ 返回: Result.successMsg("注册成功")
```

#### 业务逻辑意图

- **邀请码制**: 通过硬编码的邀请码映射表控制注册用户的初始角色，避免开放注册导致的管理员权限泄露
- **角色分配逻辑**: 管理员邀请码(`52894`)分配 `role=1`，普通邀请码(`52614`)分配 `role=0`
- **BCrypt加密**: 注册时即进行密码哈希，明文密码永不落库

---

### 5.3 `POST /api/gacha-web/get` — 核心抽卡数据获取 ★

**权限**: 公开（UniApp核心入口，无需Token）

> **这是整个系统最复杂的接口**，涉及异步并发HTTP调用、去重合并算法、多表事务写入等。

#### 代码执行链路

```
[HTTP请求] POST /api/gacha-web/get
  Body: {"firstJson": {
    "headers": {"Authorization":"Bearer ...", "User-Agent":"...", "X-Unity-Version":"..."},
    "body": {"type_id":"1", "some_param":"value"},
    "params": {"extra_param":"value"}
  }}
  │
  ▼
[SecurityConfig] → 白名单包含 "/api/gacha-web/get" → 放行
  │
  ▼
[GachaWebController.getGachaWeb()]  (第20-24行)
  → gachaWebService.getGachaFromWeb(request)
  │
  ▼
[GachaWebService.getGachaFromWeb()]  (第72-155行) — ★核心方法★
  │
  ════════════════════════════════════════════════════════════
  阶段1: 解析请求数据 (第75-84行)
  ════════════════════════════════════════════════════════════
  ├─ firstJsonMap = request.getFirstJson()
  ├─ headers = firstJsonMap.get("headers")  // Map<String,String>
  ├─ body = firstJsonMap.get("body")        // Map<String,String>
  ├─ params = firstJsonMap.get("params")    // Map<String,String>
  └─ authorization = headers.get("Authorization")
  │
  ════════════════════════════════════════════════════════════
  阶段2: 异步获取用户UID (第87-91行)
  ════════════════════════════════════════════════════════════
  ├─ getUidFromServerAsync(authorization, headers)
  │   │
  │   ▼ [getUidFromServerAsync()] (第160-186行)
  │   └─ webClient.post()
  │      → URI: https://gf2-zoneinfo.sunborngame.com/account/info
  │      → Headers: Authorization, User-Agent, Accept, X-Unity-Version
  │      → Body: "{}" (JSON)
  │      → Retry: backoff(3次, 初始500ms), 仅重试SocketException/WebClientRequestException
  │      → .block()  // 同步等待响应
  │      │
  │   └─ 解析响应:
  │      response.code == "0"? → return data.uid (Integer)
  │      否则? → return null
  │
  └─ uid == null? → throw BusinessException("获取用户UID失败")
  │
  ════════════════════════════════════════════════════════════
  阶段3: 获取或创建游戏玩家 (第94行)
  ════════════════════════════════════════════════════════════
  └─ getOrCreateGfUser(uid)  (第191-201行)
     ├─ gfUserMapper.getGfUserByUid(uid)  // 查找已有玩家
     │   → SELECT * FROM gf_user WHERE uid=? AND is_deleted=0
     ├─ 存在? → return existingUser.getId()  // 返回数据库主键ID(Long)
     └─ 不存在?
        ├─ newUser = new GfUser(uid, isDeleted=0)
        ├─ gfUserMapper.insertGfUser(newUser)  // INSERT
        └─ 再次查询返回新ID (利用AUTO_INCREMENT)
  │
  ════════════════════════════════════════════════════════════
  阶段4: 加载SSR物品字典到内存 (第97-103行)
  ════════════════════════════════════════════════════════════
  ├─ ssrItemList = gfSsrItemMapper.getGfSsrItemList()
  │   → SELECT * FROM gf_ssr_item WHERE is_deleted=0
  │
  ├─ ssrItemMap: Map<Integer itemId, GfSsrItem>     // 用于匹配抽卡记录是否为SSR
  └─ ssrItemMapById: Map<Long dbId, GfSsrItem>     // 用于前端展示时查物品详情
  │
  ════════════════════════════════════════════════════════════
  阶段5: 异步并发获取5个池子数据 ★ (第106-107行)
  ════════════════════════════════════════════════════════════
  └─ fetchAllPoolsAsync(headers, params, body, authorization)
     │
     ▼ [fetchAllPoolsAsync()] (第206-244行)
     │
     ├─ 初始化: synchronizedMap + CountDownLatch(5)
     │
     ├─ 并发启动5个异步任务 (for POOL_TYPES: [1,3,4,6,7]):
     │   │
     │   ▼ [fetchSinglePoolAsync(poolType)] (第249-284行)
     │   │
     │   ├─ 构造requestBody = body + {type_id: poolType} (去掉next字段)
     │   │
     │   ├─ fetchPageAsync(...)  // 获取第一页
     │   │   │
     │   │   ▼ [fetchPageAsync()] (第289-325行)
     │   │   ├─ 将body+params组装为 MultiValueMap (form-urlencoded)
     │   │   ├─ webClient.post()
     │   │   │   → URI: https://gf2-gacha-record.sunborngame.com/list
     │   │   │   → Content-Type: application/x-www-form-urlencoded
     │   │   │   → Body: type_id=X&... (form data)
     │   │   │   → Retry: backoff(3次, 500ms)
     │   │   │   → 返回 Mono<Map> (单页响应)
     │   │   │
     │   │   └─ doOnSuccess/doOnError 日志记录
     │   │
     │   └─ .expand(operator)  // Reactor展开操作符
     │      │
     │      ├─ 解析当前页: data.next 是否为空?
     │      │   ├─ 空 → Mono.empty() (终止)
     │      │   └─ 非空 → fetchPageAsync(nextBody) (递归获取下一页)
     │      │
     │      └─ .collectList() → 收集所有页为 List<Map>
     │         │
     │         └─ 展平处理:
     │            for each page:
     │              list.addAll(page.data.list)  // 提取每页的记录列表
     │            return allRecords  // 返回该池子的全部扁平化记录
     │
     └─ CountDownLatch.await(120秒超时)
        ├─ 所有任务完成? → 返回 result (Map<poolType, records>)
        └─ 超时? → log.warn + 继续执行(可能数据不完整)
  │
  ════════════════════════════════════════════════════════════
  阶段6: 合并新旧数据 ★ (第110-111行)
  ════════════════════════════════════════════════════════════
  ├─ latestHistory = gfGachaHistoryMapper.getLatestGfGachaHistoryByUserId(userId)
  │   → SELECT * FROM gf_gacha_history WHERE user_id=? AND is_deleted=0
  │     ORDER BY created_at DESC LIMIT 1  // 取最近一次快照
  │
  └─ mergedPoolJsons = mergePoolData(latestHistory, allPoolRecords)
     │
     ▼ [mergePoolData()] (第330-373行)
     │
     ├─ for each poolType in [1,3,4,6,7]:
     │   │
     │   ├─ newRecords = allPoolRecords.get(poolType)  // 本次从API新拉取的数据
     │   │
     │   ├─ oldRecords = 从 latestHistory 的JSON字段反序列化展平
     │   │   → getPoolJson(history, poolType): 根据 poolType 选择对应的JSON字段
     │   │   → objectMapper.readValue(oldJson): JSON → List<Map>
     │   │   → for each page in pages: oldRecords.addAll(page.data.list)
     │   │
     │   ├─ merged = mergeRecords(newRecords, oldRecords)  // ★核心去重算法
     │   │   │
     │   │   ▼ [mergeRecords()] (第397-438行)
     │   │   │
     │   │   ├─ generateFakeId(newRecords)  // 为新记录生成fakeId
     │   │   ├─ generateFakeId(oldRecords)  // 为旧记录生成fakeId
     │   │   │
     │   │   ▼ [generateFakeId()] (第447-474行)
     │   │   │   │
     │   │   │   ├─ 遍历records列表(已按time排序):
     │   │   │   │   ├─ timestamp != preTimestamp? → order = 0  (新的一抽)
     │   │   │   │   └─ timestamp == preTimestamp? → order++    (连抽数+1)
        │   │   │   │   └─ order > 9? → log.warn (超过十连的非标准数据)
        │   │   │   │
        │   │   │   └─ fakeId = timestamp * 100 + order
        │   │   │      record.put("_fake_id", fakeId)  // 临时字段
        │   │   │
        │   │   ├─ Set<Long> seenIds 去重容器
        │   │   ├─ 先遍历 newRecords:
        │   │   │   └─ fakeId不在seenIds中 → 加入merged + 加入seenIds
        │   │   ├─ 再遍历 oldRecords:
        │   │   │   └─ fakeId不在seenIds中 → 加入merged + 补充旧数据
        │   │   └─ merged.sort((a,b) => timeB - timeA)  // 按时间降序(最新在前)
        │   │
        │   └─ pages = rebuildPages(merged)  // 重建分页格式
        │      │
        │      ▼ [rebuildPages()] (第476-494行)
        │      └─ 每6条记录为一组:
        │         page = {code:0, message:"OK", data:{list:[6条], next:""}}
        │         return List<page>
        │
        └─ result.put(poolType, objectMapper.writeValueAsString(pages))  // 序列化为JSON字符串
  │
  ════════════════════════════════════════════════════════════
  阶段7: 插入新的历史快照 (第114-122行)
  ════════════════════════════════════════════════════════════
  ├─ newHistory = new GfGachaHistory()
  │   ├─ userId = userId
  │   ├─ permanentPoolJson = mergedPoolJsons.get(1)   // 常驻池
  │   ├─ characterPoolJson = mergedPoolJsons.get(3)   // 角色池
  │   ├─ weaponPoolJson = mergedPoolJsons.get(4)      // 武器池
  │   ├─ customCharacterPoolJson = mergedPoolJsons.get(6)  // 自选角色
  │   └─ customWeaponPoolJson = mergedPoolJsons.get(7)    // 自选武器
  │
  └─ gfGachaHistoryMapper.insertGfGachaHistory(newHistory)
     → INSERT INTO gf_gacha_history(user_id, permanent_pool_json, ...)
     → useGeneratedKeys="true" → newHistory.id 被回填为自增主键
  │
  ════════════════════════════════════════════════════════════
  阶段8: 清除并重建SSR记录 (第125-129行)
  ════════════════════════════════════════════════════════════
  ├─ gfGachaSsrRecordMapper.deleteGfGachaSsrRecordByUserId(userId)
  │   → DELETE FROM gf_gacha_ssr_record WHERE user_id=?
  │   │
  ├─ ssrRecords = buildSsrRecords(userId, historyId, mergedPoolJsons,
  │                                ssrItemMap, ssrItemMapById)
  │   │
  │   ▼ [buildSsrRecords()] (第496-600行) — ★SSR记录构建算法★
  │   │
  │   ├─ for each poolType in [1,3,4,6,7]:
  │   │   │
  │   │   ├─ 反序列化 mergedPoolJsons.get(poolType) → 展平为 records 列表
  │   │   │
  │   │   ├─ 从末尾向前遍历 (i = records.size()-1 → 0) 【从旧到新】
  │   │   │
  │   │   ├─ 对每条record:
  │   │   │   ├─ itemId = record.get("item")  // 注意: 原始字段名为"item"不是"item_id"
  │   │   │   ├─ rank = ssrItemMap.containsKey(itemId)? 3(SSR) : 1(非SSR)
  │   │   │   │
  │   │   │   ├─ if rank==3 (是SSR):
  │   │   │   │   ├─ ssrCount++
  │   │   │   │   ├─ 创建 GfGachaSsrRecord:
  │   │   │   │   │   ├─ itemId = ssrItem.id (gf_ssr_item表的主键, 不是游戏道具ID!)
  │   │   │   │   │   ├─ drawOrder = ssrCount
  │   │   │   │   │   └─ costDraws = totalDraws + 1  // 含自身1抽
  │   │   │   │   ├─ totalDraws = 0  // 重置垫刀计数器
  │   │   │   │   └─ 加入 poolSsrRecords
  │   │   │   │
  │   │   │   └─ else (非SSR):
  │   │   │       └─ totalDraws++  // 累加垫刀数
  │   │   │
  │   │   └─ 处理question占位符:
  │   │       ├─ if poolSsrRecords.isEmpty (无SSR):
  │   │       │   └─ 创建 placeholder: itemId=0, drawOrder=0, costDraws=totalDraws
  │   │       │
  │   │       └─ else (有SSR):
  │   │           ├─ Collections.reverse(poolSsrRecords)  // 反转为从新到旧
  │   │           ├─ 在index=0插入 placeholder:
  │   │           │   └─ drawOrder=0, costDraws=drawsAfterLatestSsr
  │   │           └─ 重新编号真实SSR: drawOrder从1开始递增
  │   │
  │   └─ allRecords.addAll(poolSsrRecords)
  │
  └─ if !ssrRecords.isEmpty:
     └─ gfGachaSsrRecordMapper.insertGfGachaSsrRecordList(ssrRecords)
        → INSERT INTO gf_gacha_ssr_record(user_id,history_id,pool_type,... )
           VALUES (...),(...),(...)  // 批量插入
  │
  ════════════════════════════════════════════════════════════
  阶段9: 组装返回DTO (第132-134行)
  ════════════════════════════════════════════════════════════
  ├─ allItems = buildGachaItemsFromRecords(ssrRecords, ssrItemMapById)
  │   │
  │   ▼ [buildGachaItemsFromRecords()] (第607-644行)
  │   └─ for each GfGachaSsrRecord record:
  │      ├─ vo = new GachaItemVO()
  │      ├─ vo.poolType/costDraws/drawOrder = record对应字段
  │      │
  │      ├─ if record.itemId == 0:
  │      │   └─ vo = {itemId:0, itemName:"question", itemType:0, ssrType:0}
  │      │
  │      └─ else:
  │          └─ ssrItem = ssrItemMapById.get(record.itemId)  // 用db主键查找
  │             └─ vo = {itemId:ssrItem.itemId(游戏ID), itemName, itemType, ssrType}
  │
  ├─ recordsList = gfUserService.buildGachaRecordsList(allItems)
  │   → 按poolType分组 → 统计totalSSR/waiCnt/totalDraws → List<GachaRecordsVO>
  │
  └─ result = gfUserService.buildGfUserDTO(String.valueOf(uid), recordsList)
      → 汇总全局统计数据(totalDraws/totalSSR/safeRate/avgCharacter/avgWeapon/avgPermanent)
  │
  ════════════════════════════════════════════════════════════
  阶段10: 欧皇值计算 & 排行榜Upsert (第137-145行)
  ════════════════════════════════════════════════════════════
  ├─ luckValue = gfUserService.calculateLuckValue(allItems)
  │   │
  │   ▼ [calculateLuckValue()] (第153-211行) — ★欧皇值算法★
  │   │
  │   ├─ 统计指标:
  │   │   ├─ totalSSR: 总SSR数 (排除question)
  │   │   ├─ sumCostDraws: 总花费抽数
  │   │   ├─ waiCnt: 歪的数量 (仅限定池)
  │   │   ├─ limitedSSR: 限定池SSR总数
  │   │   └─ earlyCnt: 30抽以内早出的SSR数量
  │   │
  │   └─ 三维度评分公式:
  │      ├─ 维度1 出率分 = floor(8000 / avgCostDraws)
  │      │   └─ 样本衰减: SSR<5个时 × (totalSSR/5)
  │      │
  │      ├─ 维度2 不歪分 = floor(noWaiRate × 300)
  │      │   ├─ noWaiRate = 1 - waiCnt/limitedSSR
  │      │   └─ 样本衰减: limitedSSR<3个时 × (limitedSSR/3)
  │      │   └─ 无限定池数据时默认150分(及格分)
  │      │
  │      ├─ 维度3 早出分 = floor((earlyCnt/totalSSR) × 150)
  │      │
  │      └─ luckValue = rateScore + waiScore + earlyScore
  │
  ├─ ranking = new GfGachaRankingList(userId, luckValue, totalDraws)
  │
  └─ Upsert操作:
     ├─ gfGachaRankingListMapper.updateGfGachaRankingListByUserId(ranking)
     │   → UPDATE SET luck_value=?, total_draws=? WHERE user_id=? AND is_deleted=0
     │
     └─ 影响行数==0 (不存在)?
        └─ gfGachaRankingListMapper.insertGfGachaRankingList(ranking)
           → INSERT INTO gf_gacha_ranking_list(user_id, luck_value, total_draws)

  ════════════════════════════════════════════════════════════
  返回: Result<GfUserDTO> (完整抽卡数据汇总)
  ════════════════════════════════════════════════════════════
```

#### 业务逻辑意图

**整体流程设计理念**:

1. **数据来源**: 从UniApp客户端接收GF2游戏的原始HTTP请求头和参数，代理转发至GF2官方服务器获取真实抽卡记录
2. **幂等性与增量更新**: 每次调用都拉取全量数据，然后与本地历史快照做基于 `fakeId` 的去重合并，确保多次调用不会产生重复数据
3. **快照式存储**: 每次成功拉取都生成一条全新的 `gf_gacha_history` 记录（追加写入），同时清空并重建 `gf_gacha_ssr_record`（始终只保留最新的SSR明细）
4. **fakeId去重算法**: 参考Go参考项目(gf2gacha_Matcha)的 `MergeRecord.go` 实现，`fakeId = time * 100 + order` 数学上保证同一抽的唯一性，不依赖JSON序列化比对
5. **分页兼容**: 合并后的数据通过 `_rebuild_pages()` 重建为 `{code:0, message:"OK", data:{list:[6], next:""}}` 格式，与官方API响应结构一致，保证向后兼容
6. **SSR识别机制**: 通过 `gf_ssr_item` 字典表的 `item_id` 匹配来判定一条抽卡记录是否为SSR；未在字典中的物品视为非SSR（rank=1）
7. **Question占位符**: 每个池子的第一条记录是一个 `itemId=0` 的占位符，用于表达"最新SSR之后又垫了多少抽"，drawOrder=0标识其特殊身份
8. **欧皇值**: 综合评价用户的抽卡运气，三个维度分别衡量出货效率、不歪概率、小保底内出货率

---

### 5.4 `GET /api/gf-user/get?uid=` — 查询用户抽卡记录

**权限**: 公开

#### 代码执行链路

```
[HTTP请求] GET /api/gf-user/get?uid=123456
  │
  ▼
[SecurityConfig] → 白名单包含 "/api/gf-user/get" → 放行
  │
  ▼
[GfUserController.getGfUserInfoByUid()]  (第19-22行)
  → gfUserService.getGachaInfoByUid(uid)
  │
  ▼
[GfUserService.getGachaInfoByUid()]  (第26-33行)
  │
  ├─ allItems = getAllPoolGachaItems(uid)  (第37-39行)
  │   └─ gfGachaSsrRecordMapper.getGachaItemVOListByUid(uid)
  │      → SQL (见 GfGachaSsrRecordMapper.xml 第30-37行):
  │         SELECT COALESCE(i.item_id, r.item_id) as item_id,
  │                i.item_name, i.item_type, i.ssr_type,
  │                r.cost_draws, r.pool_type, r.draw_order
  │         FROM gf_user AS u
  │         LEFT JOIN gf_gacha_ssr_record AS r ON u.id = r.user_id
  │         LEFT JOIN gf_ssr_item AS i ON r.item_id = i.id
  │         WHERE u.uid = #{uid} AND u.is_deleted = 0
  │         ORDER BY r.pool_type, r.draw_order
  │      → 返回 List<GachaItemVO> (直接JOIN了SSR物品名称等信息)
  │
  ├─ allItems.isEmpty()? → throw BusinessException("该用户没有抽卡记录")
  │
  ├─ recordsList = buildGachaRecordsList(allItems)  (第52-96行)
  │   ├─ Stream.groupingBy(GachaItemVO::getPoolType)  // 按池类型分组
  │   ├─ for each group:
  │   │   ├─ 遍历items统计:
  │   │   │   ├─ itemId==0? → question占位符, itemName="question", 累加costDraws到totalDraws
  │   │   │   └─ itemId!=0? → 真实SSR:
  │   │   │       ├─ totalSSR++
  │   │   │       ├─ isWai = (poolType!=1 && ssrType==3)? 1 : 0  // 限定池中出常驻=歪
  │   │   │       └─ 累加 costDraws 到 totalDraws
  │   │   └─ vo = {poolType, totalSSR, waiCnt, totalDraws, gachaItems}
  │   └─ return List<GachaRecordsVO>
  │
  └─ result = buildGfUserDTO(uid, recordsList)  (第104-147行)
     ├─ 汇总全部池子: totalDraws, totalSSR, waiCnt
     ├─ 分类统计: permanent(池1)/character(池3,6)/weapon(池4,7) 各自的SSR数和抽数
     ├─ safeRate = floor((totalSSR - waiCnt) * 100 / totalSSR)  // 保底不歪率(%)
     ├─ avgCharacter = floor(characterCnt / characterSSRCnt)  // 平均角色抽数
     ├─ avgWeapon = floor(weaponCnt / weaponSSRCnt)           // 平均武器抽数
     ├─ avgPermanent = floor(permanentCnt / permanentSSRCnt)   // 平均常驻抽数
     └─ return GfUserDTO {uid, gachaRecordsList, totalDraws, totalSSR, safeRate, ...}

返回: Result<GfUserDTO>
```

#### 关键SQL说明

```sql
-- getGachaItemVOListByUid: 三表JOIN一次查出所有需要的数据
SELECT 
  COALESCE(i.item_id, r.item_id) as item_id,  -- 优先取物品表的item_id(游戏ID)，否则用record的item_id(db主键)
  i.item_name,                                  -- SSR物品名称
  i.item_type,                                  -- 物品类型: 10人形/20武器
  i.ssr_type,                                   -- SSR类型: 1限定角色/2限定武器/3常驻
  r.cost_draws,                                 -- 花费抽数
  r.pool_type,                                  -- 卡池类型
  r.draw_order                                  -- 池内顺序号
FROM gf_user AS u
LEFT JOIN gf_gacha_ssr_record AS r ON u.id = r.user_id
LEFT JOIN gf_ssr_item AS i ON r.item_id = i.id  -- JOIN SSR字典表获取物品详情
WHERE u.uid = #{uid} AND u.is_deleted = 0
ORDER BY r.pool_type, r.draw_order
```

> **COALESCE的作用**: 当 `r.item_id=0`（question占位符）时，JOIN不到 `gf_ssr_item` 记录，此时COALESCE确保返回record自身的item_id值(0)，而非NULL。

---

### 5.5 排行榜相关接口

#### `GET /api/gf-gacha-ranking/get` — 获取排行榜

**权限**: 公开

```
[GfGachaRankingListController.getGfGachaRankingList()]
  → gfGachaRankingListService.getGfGachaRankingList()
     │
     ▼ [GfGachaRankingListService.getGfGachaRankingList()] (第17-26行)
     ├─ dto.setOrderByLuckValueDesc(
     │   mapper.getGfGachaRankingListOrderByLuckValueDesc())
     │   → SQL: SELECT r.luck_value, r.total_draws, u.uid as userId
     │          FROM gf_gacha_ranking_list r LEFT JOIN gf_user u ON r.user_id=u.id
     │          WHERE r.is_deleted=0 ORDER BY r.luck_value DESC LIMIT 1000
     │
     ├─ dto.setOrderByTotalDrawsDesc(
     │   mapper.getGfGachaRankingListOrderByTotalDrawsDesc())
     │   → 同上结构, ORDER BY r.total_draws DESC LIMIT 1000
     │
     └─ return dto  // 包含两个排序维度的排行榜

返回: Result<GfGachaRankingListDTO>
```

#### `GET /api/gf-gacha-ranking/count` — 活跃用户数

**权限**: 公开

```
→ mapper.countActiveUsers()
  → SQL: SELECT COUNT(DISTINCT user_id) FROM gf_gacha_ranking_list WHERE is_deleted=0

返回: Result<Integer>
```

---

### 5.6 SSR物品管理接口 (`/api/gf-ssr-item/*`) — 需要管理员权限

**权限**: 需要 `role=1` (管理员)，类级别标注 `@RequireRole(1)`

#### 代码执行链路总览

| HTTP方法 | 路径 | 功能 | Service方法 | Mapper方法 |
|---------|------|------|-------------|------------|
| POST | `/insertList` | 批量添加SSR物品 | `batchInsert()` | `insertGfSsrItemList()` → batch INSERT |
| GET | `/getByItemId?itemId=` | 单条查询 | `getGfSsrItemByItemId()` | `getGfSsrItemByItemId()` → SELECT |
| GET | `/getAll` | 查询全部 | `getGfSsrItemAll()` | `getGfSsrItemList()` → SELECT ALL |
| GET | `/count` | 物品总数 | `getSsrItemCount()` | `countSsrItems()` → COUNT |
| POST | `/removeByItemId` | 逻辑删除 | `removeGfSsrItemByItemId()` | `remove()` → UPDATE is_deleted=1 |
| POST | `/restoreAll` | 恢复全部 | `restoreGfSsrItemAll()` | `restoreAll()` → UPDATE is_deleted=0 |
| GET | `/getDeleted` | 回收站列表 | `getDeletedGfSsrItemList()` | `getDeleted()` → SELECT is_deleted=1 |
| POST | `/restoreByItemId` | 恢复单条 | `restoreGfSsrItemByItemId()` | `restore()` → UPDATE is_deleted=0 |
| POST | `/deleteByIsDeleted` | 物理删除 | `deleteGfSsrItemByIsDeleted()` | `delete()` → DELETE is_deleted=1 |

#### 典型链路: 批量添加

```
POST /api/gf-ssr-item/insertList
Body: {"gfSsrItemList":[{itemId:80001,itemName:"薇拉",itemType:10,ssrType:1}, ...]}
  │
  ▼ [JwtAuthInterceptor.preHandle()]
  ├─ Token校验通过 ✓
  ├─ @RequireRole(1) 类级注解检测 → loginUser.role == 1? ✓
  └─ 放行
  │
  ▼ [GfSsrItemController.insertGfSsrItemList()]
  → gfSsrItemService.batchInsert(dto)
     → gfSsrItemMapper.insertGfSsrItemList(list)
        → INSERT INTO gf_ssr_item(item_id,item_name,item_type,ssr_type)
           VALUES (80001,'薇拉',10,1),(80002,'...',...),(...)
  │
  └─ return Result.successMsg("插入成功")
```

#### 典型链路: 回收站恢复

```
POST /api/gf-ssr-item/restoreByItemId
Body: {"itemId": 80001}
  │
  ▼
→ gfSsrItemMapper.restoreGfSsrItemByItemId(itemId)
  → UPDATE gf_ssr_item SET is_deleted=0, updated_at=NOW()
     WHERE item_id=#{itemId} AND is_deleted=1
  │
  ├─ rows > 0? → 成功
  └─ rows == 0? → throw RuntimeException("未找到可恢复的物品或该物品未被删除")
```

#### 业务逻辑意图

- **回收站模式**: 采用 `is_deleted` 软删除 + 恢复机制，防止误删不可逆
- **两阶段物理删除**: 先软删除进入回收站，确认后再通过 `deleteByIsDeleted` 物理清除
- **DTO转换**: Entity(GfSsrItem) ↔ DTO(GfSsrItemDTO) 使用 `BeanUtils.copyProperties` 自动属性拷贝

---

### 5.7 系统用户管理接口 (`/api/sys-user/*`) — 仅管理员

**权限**: 类级别 `@RequireRole(1)`，所有方法需管理员权限

| HTTP方法 | 路径 | 功能 | Service方法 |
|---------|------|------|-------------|
| GET | `/list` | 用户列表(脱敏) | `getUserList()` |
| GET | `/count` | 用户总数 | `getUserCount()` |
| POST | `/updateRole` | 修改角色 | `updateRole(username, role)` |
| POST | `/updateStatus` | 封禁/解封 | `updateStatus(username, status)` |
| POST | `/remove` | 逻辑删除 | `removeUser(username)` |

#### 典型链路: 用户列表 (带脱敏)

```
GET /api/sys-user/list
  │
  ▼ [SysAuthService.getUserList()] (第151-157行)
  ├─ users = sysUserMapper.getAllUsers()
  │   → SELECT * FROM sys_user WHERE is_deleted=0 ORDER BY id ASC
  │
  └─ voList = users.stream().map(this::convertToVO).toList()
     │
     ▼ [convertToVO()] (第209-220行)
     └─ new SysUserListVO(
          id, username, role, status,
          lastLoginTime.format(DT_FORMAT),  // 格式化为 "yyyy-MM-dd HH:mm:ss"
          isDeleted,
          createdAt.format(DT_FORMAT),
          updatedAt.format(DT_FORMAT)
        )
     → 注意: password字段不包含在VO中! (敏感信息脱敏)

返回: Result<List<SysUserListVO>>
```

#### 典型链路: 更改角色

```
POST /api/sys-user/updateRole
Body: {"username":"testuser", "role":1}
  │
  ▼ [SysAuthService.updateRole()] (第169-176行)
  ├─ validateUsername(username)  // 校验用户存在性
  │   └─ getSysUserByUsername(username) == null? → throw "用户不存在"
  │
  ├─ role不在[0,1]? → throw "角色值无效"
  │
  └─ sysUserMapper.updateRoleByUsername(username, role)
     → UPDATE sys_user SET role=#{role} WHERE username=#{username}

返回: Result.successMsg("角色更新成功")
```

---

## 六、核心业务逻辑深度剖析

### 6.1 fakeId去重合并算法

```
参考实现: gf2gacha_Matcha 项目 MergeRecord.go

算法目标: 将新拉取的API数据 与 本地历史数据 合并去重

输入:
  newRecords: 本次从GF2官方API拉取的全量记录(已按时间正序)
  oldRecords: 上次保存的历史记录(同样按时间正序)

输出:
  merged: 无重复的完整记录集(按时间降序, 最新在前)
```

#### 算法步骤

```
步骤1: 生成fakeId
  ┌──────────────────────────────────────────────┐
  │ 遍历记录列表(假设已按time升序排列):            │
  │                                              │
  │  record[0]: time=1700000100 → order=0        │
  │           fakeId = 1700000100*100 + 0        │
  │                  = 170000010000               │
  │                                              │
  │  record[1]: time=1700000100 → order=1 (同秒) │
  │           fakeId = 1700000100*100 + 1        │
  │                  = 170000010001               │
  │                                              │
  │  record[2]: time=1700000200 → order=0 (换秒) │
  │           fakeId = 1700000200*100 + 0        │
  │                  = 170000020000               │
  │                                              │
  │  规则:                                        │
  │    - timestamp变化 → order重置为0             │
  │    - timestamp不变 → order递增(+1)            │
  │    - order>9 → warn(非标准十连以上数据)       │
  └──────────────────────────────────────────────┘

步骤2: Set-based去重(新优先)
  ┌──────────────────────────────────────────────┐
  │ HashSet<Long> seenIds                         │
  │                                              │
  │  for each newRecord:                          │
  │    fakeId not in seenIds? → 加入merged        │
  │                                              │
  │  for each oldRecord:                          │
  │    fakeId not in seenIds? → 补充加入merged    │
  │    (新数据已覆盖的fakeId会被跳过)              │
  └──────────────────────────────────────────────┘

步骤3: 排序
  ┌──────────────────────────────────────────────┐
  │ merged.sort(time DESC)  // 最新记录在前       │
  └──────────────────────────────────────────────┘
```

#### 数学正确性证明

```
fakeId = timestamp * 100 + order

约束条件:
  - timestamp: Unix时间戳(秒级), 如 1700000100
  - order: 0~9 (同一秒内的连抽序号)
  - GF2官方API保证: 同一秒内的连抽不超过10抽

唯一性:
  - 不同timestamp → 至少相差100 → fakeId不同
  - 相同timestamp + 不同order → fakeId不同
  - 因此 (timestamp, order) → fakeId 是单射

与Go项目等效性:
  Go:   Sprintf("%d%02d", timestamp, order) → ParseInt
        例如: "1700000100" + "00" → 170000010000
  
  Java: timestamp * 100 + order
        例如: 1700000100 * 100 + 0 → 170000010000
  
  结果数学上完全一致
```

### 6.2 SSR记录构建算法 (buildSsrRecords)

```
目的: 从合并后的JSON数据中提取SSR记录, 构建规范化的SSR明细

遍历方向: 从旧到新 (reverse chronological index: size-1 → 0)
原因: 需要知道"距离上次SSR过了多少抽", 所以必须从头开始累计

状态机:
  ┌─────────────────────────────────────────────────┐
  │ totalDraws = 0    // 距离上次SSR的抽数计数器     │
  │ ssrCount = 0      // 当前池子内的SSR编号          │
  │                                                 │
  │ for record in reversed(records):                │
  │   if isSSR(itemId in ssrItemMap):               │
  │     ssrRecord = {                               │
  │       itemId: ssrItem.dbPrimaryKey,             │
  │       drawOrder: ssrCount++,                    │
  │       costDraws: totalDraws + 1,  // 含自身!    │
  │     }                                          │
  │     totalDraws = 0  // 重置计数器               │
  │   else:                                        │
  │     totalDraws++  // 非SSR, 垫刀+1              │
  └─────────────────────────────────────────────────┘

后处理 (有SSR的情况):
  1. Collections.reverse(ssrRecords)  // 翻转为从新到旧
  2. 在index=0插入 question 占位符:
     {itemId:0, drawOrder:0, costDraws: 剩余垫抽数}
  3. 重新编号真实SSR: drawOrder = 1, 2, 3, ...

最终结构 (以某个池子为例):
  ┌──────┬────────┬───────────┬──────────┬──────────┐
  │ idx  │ itemId │ drawOrder │ costDraws│ 含义     │
  ├──────┼────────┼───────────┼──────────┼──────────┤
  │  0   │   0    │     0     │    23    │ question │
  │  1   │ 80001  │     1     │    52    │ 最新SSR  │
  │  2   │ 80002  │     2     │    35    │ 次新SSR  │
  │  3   │ 80003  │     3     │    18    │ 第三SSR  │
  └──────┴────────┴───────────┴──────────┴──────────┘
  
  解释:
  - question: 最新SSR之后又垫了23抽
  - SS#1(最新): 花了52抽出(含自身1抽+之前51抽垫刀)
  - SS#2: 距离上一个SSR花了35抽
  - 以此类推...
```

### 6.3 欧皇值计算模型 (calculateLuckValue)

```
luckValue = rateScore + waiScore + earlyScore
满分约: 400+ (极端运气)    及格线约: 350~450
```

#### 三维评分细则

```
┌─────────────────────────────────────────────────────────────┐
│ 维度1: 出率分 (rateScore)                                   │
│                                                             │
│   公式: rateScore = floor(8000 / avgCostDraws)              │
│                                                             │
│   avgCostDraws = sumCostDraws / totalSSR                    │
│   (平均每出一只SSR需要多少抽)                                │
│                                                             │
│   示例:                                                     │
│     60抽/SSR → 8000/60 = 133分                             │
│     40抽/SSR → 8000/40 = 200分                             │
│     20抽/SSR → 8000/20 = 400分 (小保底出货!)               │
│                                                             │
│   样本衰减: totalSSR < 5 时, rateScore *= (totalSSR/5)     │
│   (样本太少则分数打折, 防止偶然性虚高)                       │
├─────────────────────────────────────────────────────────────┤
│ 维度2: 不歪分 (waiScore)                                    │
│                                                             │
│   公式: waiScore = floor(noWaiRate × 300)                  │
│                                                             │
│   noWaiRate = 1 - (waiCnt / limitedSSR)                    │
│   (限定池不歪比例; 不含常驻池数据)                           │
│                                                             │
│   示例 (限定池共10抽SSR):                                   │
│     0歪  → noWaiRate=1.0  → 300分 (完全不歪!)             │
│     2歪  → noWaiRate=0.8  → 240分                         │
│     5歪  → noWaiRate=0.5  → 150分 (一半歪了)              │
│     10歪 → noWaiRate=0.0  → 0分 (全歪=大冤种)             │
│                                                             │
│   特殊: 无限定池SSR数据时 → 固定150分(及格分)              │
│   样本衰减: limitedSSR < 3 时, waiScore *= (limitedSSR/3)  │
├─────────────────────────────────────────────────────────────┤
│ 维度3: 早出分 (earlyScore)                                  │
│                                                             │
│   公式: earlyScore = floor((earlyCnt / totalSSR) × 150)    │
│                                                             │
│   earlyCnt = costDraws <= 30 的SSR数量                      │
│   (30抽以内出货算"早出"; 约1.5个版本周期内的小保底线)       │
│                                                             │
│   示例 (总SSR=10):                                         │
│     3个早出 → 3/10×150 = 45分                              │
│     5个早出 → 5/10×150 = 75分                              │
│     10早出 → 10/10×150 = 150分(全部小保底内!)              │
└─────────────────────────────────────────────────────────────┘
```

### 6.4 异步并发模型

```
┌──────────────────────────────────────────────────────────┐
│              WebClient 异步并发架构                        │
│                                                          │
│  主线程                                                  │
│    │                                                     │
│    ├──► Pool 1 (常驻池) ──┐                              │
│    ├──► Pool 3 (角色池) ──┤                              │
│    ├──► Pool 4 (武器池) ──┤  CountDownLatch(5)          │
│    ├──► Pool 6 (自选角色)─┤     await(120秒)             │
│    └──► Pool 7 (自选武器)─┘                              │
│          │         │         │                          │
│          ▼         ▼         ▼                          │
│     [Reactor线程池]     Netty EventLoop                  │
│                                                          │
│  每个池子的内部流:                                       │
│    Page1 ──► expand(Page2) ──► expand(Page3) ──► ...    │
│           (data.next非空?)     (data.next非空?)          │
│                  │                                       │
│                  ▼ empty (next为空, 终止)                 │
│           collectList() → flatten → allRecords          │
└──────────────────────────────────────────────────────────┘

关键技术点:
1. CountDownLatch: 确保5个池子全部完成(或超时)后才继续
2. Reactor expand: 声明式分页, 自动递归直到next为空
3. synchronizedMap: 保证并发写安全
4. WebClient连接池: maxIdleTime=10s, maxLifeTime=2min
5. 重试策略: backoff(3次, 500ms起始), 仅针对网络异常
6. 超时保护: latch.await(120秒), 部分失败不影响整体
```

---

## 七、安全认证机制

### 7.1 JWT认证流程

```
┌──────────┐     ① POST /login      ┌──────────────┐
│          │ ──────────────────────► │              │
│  Client  │     {user, pwd}        │   Server     │
│          │ ◄──────────────────────│              │
│          │ ② {token, user}        │  BCrypt校验   │
│          │                        │  JWT签署      │
├──────────┤                        ├──────────────┤
│          │     ③ API Request      │              │
│  后续请求 │ ─────────────────────►│              │
│          │  Header: Bearer <jwt>  │              │
│          │                        │  拦截器链:    │
│          │                        │  1.白名单检查 │
│          │                        │  2.Token提取  │
│          │                        │  3.签名验签   │
│          │                        │  4.过期检查   │
│          │                        │  5.角色鉴权   │
│          │                        │              │
│          │ ◄──────────────────────│  6.ThreadLocal│
│          │ ④ Response Data        │     设置用户  │
└──────────┘                        └──────────────┘
```

### 7.2 请求过滤规则

```
SecurityConfig 注册规则:

拦截范围: /api/**
排除路径 (无需Token):
  ├── /api/sys-auth/login        (登录)
  ├── /api/sys-auth/register     (注册)
  ├── /api/gacha-web/get         (UniApp抽卡入口 - 公开)
  ├── /api/gf-user/get           (公开查询)
  └── /api/gf-gacha-ranking/get  (排行榜公开)

需要管理员(@RequireRole(1)):
  ├── /api/sys-user/*            (整个路径)
  └── /api/gf-ssr-item/*         (整个路径)

需普通登录(无@RequireRole注解, 但需要有效Token):
  └── (当前无此类接口)
```

### 7.3 JWT Token结构

```
Header: {"alg":"HS256","typ":"JWT"}
Payload (Claims):
{
  "sub": "admin",           // subject = username
  "userId": 1,              // Long
  "role": 1,                // Integer: 0=普通, 1=管理员
  "iat": 1700000000000,     // issuedAt - 签发时间戳(ms)
  "exp": 1700086400000      // expiration - 过期时间 = iat + 24h
}
Signature: HMAC-SHA256(secretKey, base64Url(header).base64Url(payload))

密钥来源: application.properties → jwt.secret
过期时间: jwt.expiration = 86400000ms (24小时)
```

### 7.4 角色权限注解 @RequireRole

```java
// 可作用于方法级别
@RequireRole(1)  // 仅管理员
public Result<Void> adminOnlyMethod() { ... }

// 可作用于类级别 (所有方法继承)
@RestController
@RequireRole(1)  // 整个Controller需要管理员
public class SysUserController { ... }

// 拦截器检测优先级:
// 1. 方法级 @RequireRole
// 2. 类级 @RequireRole
// (两者都会检查，任一不满足即拒绝)
```

---

## 八、异常处理体系

### 8.1 异常层次与处理策略

```
┌─────────────────────────────────────────────────────────────┐
│                  GlobalExceptionHandler                       │
│               (@RestControllerAdvice)                         │
│                                                              │
│  异常类型                    │ HTTP Code │ 响应格式           │
│  ──────────────────────────┼──────────┼────────────────────│
│  BusinessException         │ 400/自定义│ {code,msg,data:null}│
│  │  ├─ "用户名不能为空"     │   400    │                     │
│  │  ├─ "获取用户UID失败"    │   400    │                     │
│  │  └─ "部分池子数据获取失败"│  400    │                     │
│  │                                                        │
│  JwtException               │   401    │ Token非法/失效      │
│  SignatureException         │   401    │ 签名不匹配          │
│  │  (拦截器层面也返回401)                              │
│  │                                                        │
│  NoResourceFoundException   │   404    │ 请求资源不存在      │
│  │                                                        │
│  DataAccessException        │   500风格│ "系统繁忙,稍后再试" │
│  │  (SQLException等数据库异常)                             │
│  │                                                        │
│  IllegalArgumentException  │   400    │ 原始错误消息         │
│  │                                                        │
│  Exception (兜底)            │   500    │ "系统内部错误"      │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 拦截器层面的异常响应

```
JwtAuthInterceptor 直接写入 HttpServletResponse (不经Exceptionhandler):

  401 UNAUTHORIZED:
    - 未提供Token: "未提供有效的认证Token，请先登录"
    - Token无效:   "Token已失效或非法，请重新登录"
    - Token过期:   "Token已过期，请重新登录"
    - 解析失败:    "Token解析失败：{具体原因}"

  403 FORBIDDEN:
    - 角色不足:   "权限不足，需要管理员权限"

统一格式: Result.fail(code, msg) → {code, msg, data:null}
```

### 8.3 GachaWebService 特殊异常处理

```java
// 第149-154行: GachaWebService 内部的双层异常捕获
try {
  // ... 完整的抽卡数据处理流程 ...
} catch (BusinessException e) {
  throw e;           // 业务异常直接抛出, 由GlobalExceptionHandler处理
} catch (Exception e) {
  log.error("获取抽卡记录失败", e);  // 记录完整堆栈
  throw new BusinessException("获取抽卡记录失败: " + e.getMessage());
  // 包装为BusinessException再抛出, 统一错误格式
}
```

---

## 附录A: 完整API清单速查

| # | 方法 | 路径 | 认证 | 权限 | 功能 |
|---|------|------|------|------|------|
| 1 | POST | `/api/sys-auth/login` | 无 | - | 用户登录, 返回JWT |
| 2 | POST | `/api/sys-auth/register` | 无 | - | 用户注册(需邀请码) |
| 3 | POST | `/api/gacha-web/get` | 无 | - | **[核心]** 拉取并处理抽卡数据 |
| 4 | GET | `/api/gf-user/get` | 无 | - | 按UID查询抽卡记录 |
| 5 | GET | `/api/gf-gacha-ranking/get` | 无 | - | 排行榜(欧皇值/抽数排序) |
| 6 | GET | `/api/gf-gacha-ranking/count` | 无 | - | 活跃抽卡用户数 |
| 7 | GET | `/api/sys-user/list` | JWT | Admin | 系统用户列表 |
| 8 | GET | `/api/sys-user/count` | JWT | Admin | 用户总数 |
| 9 | POST | `/api/sys-user/updateRole` | JWT | Admin | 修改用户角色 |
| 10 | POST | `/api/sys-user/updateStatus` | JWT | Admin | 封禁/解封 |
| 11 | POST | `/api/sys-user/remove` | JWT | Admin | 逻辑删除用户 |
| 12 | POST | `/api/gf-ssr-item/insertList` | JWT | Admin | 批量添加SSR物品 |
| 13 | GET | `/api/gf-ssr-item/getByItemId` | JWT | Admin | 按物品ID查询 |
| 14 | GET | `/api/gf-ssr-item/getAll` | JWT | Admin | 查询全部SSR物品 |
| 15 | GET | `/api/gf-ssr-item/count` | JWT | Admin | SSR物品总数 |
| 16 | POST | `/api/gf-ssr-item/removeByItemId` | JWT | Admin | 逻辑删除物品 |
| 17 | POST | `/api/gf-ssr-item/restoreAll` | JWT | Admin | 恢复全部已删 |
| 18 | GET | `/api/gf-ssr-item/getDeleted` | JWT | Admin | 回收站列表 |
| 19 | POST | `/api/gf-ssr-item/restoreByItemId` | JWT | Admin | 恢复单条 |
| 20 | POST | `/api/gf-ssr-item/deleteByIsDeleted` | JWT | Admin | 物理删除 |

## 附录B: 关键设计决策记录

| 决策点 | 选择 | 原因 |
|--------|------|------|
| HTTP客户端选择 | WebClient (WebFlux) | 异步非阻塞, 支持5池并发, Reactor操作符(expand)适合分页场景 |
| 去重算法 | fakeId (time*100+order) | 参考Go标准实现, 数学唯一, 不依赖序列化比对, 高效O(n) |
| 历史存储方式 | 快照追加 + SSR重建 | History存完整JSON(可追溯), SSR表存结构化数据(便于查询统计) |
| 分页格式保留 | _rebuildPages(6条/页) | 向后兼容, 保持与GF2官方API格式一致 |
| SSR识别 | 字典表(item_id)匹配 | 可动态维护SSR物品列表, 新增物品只需字典表操作不需改代码 |
| 密码存储 | BCrypt | 内置salt, 同一密码每次哈希不同, 抗彩虹表攻击 |
| 登录安全提示 | 统一模糊提示 | 防止用户名枚举攻击 |
| 回收站模式 | is_deleted软删除 | 防误删, 可恢复, 两阶段删除更安全 |
| 排行榜更新 | Update+Insert (Upsert) | 避免重复插入UNIQUE约束冲突, 语义清晰 |
| 邀请码硬编码 | Map.of()静态映射 | 简单场景够用, 避免数据库额外查询开销 |
| CORS策略 | allowedOriginPatterns(*) | 开发阶段便利, 生产环境应限制具体域名 |

---

> **文档版本**: v1.0 | **生成日期**: 2026-05-26 | **基于代码提交**: main分支 (working tree clean)
