-- ============================================
-- GF2 Gacha Admin - RBAC 数据库初始化脚本
-- 执行前请确保已创建 gf2gacha_xkl 数据库
-- ============================================

-- 1. 系统用户表 (sys_user)
CREATE TABLE IF NOT EXISTS `sys_user` (
    `id`               BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `username`         VARCHAR(64)  NOT NULL            COMMENT '用户名',
    `password`         VARCHAR(128) NOT NULL            COMMENT '密码',
    `role`             INT          NOT NULL DEFAULT 0   COMMENT '角色: 0=普通用户, 1=管理员',
    `status`           CHAR(1)      NOT NULL DEFAULT '1' COMMENT '状态: 0=封禁, 1=正常',
    `last_login_time`  DATETIME     NULL                COMMENT '最后登录时间',
    `is_deleted`       INT          NOT NULL DEFAULT 0   COMMENT '逻辑删除: 0=未删除, 1=已删除',
    `created_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统用户表';

-- 2. 插入默认管理员账号 (admin / admin123)
INSERT INTO `sys_user` (`username`, `password`, `role`, `status`) VALUES
('admin', 'admin123', 1, '1')
ON DUPLICATE KEY UPDATE `password` = VALUES(`password`);

-- 3. 确认其他业务表存在
CREATE TABLE IF NOT EXISTS `gf_user` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT,
    `uid`           INT          NOT NULL UNIQUE,
    `sys_user_id`   BIGINT       NULL,
    `is_deleted`    INT          NOT NULL DEFAULT 0,
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='游戏玩家表';

CREATE TABLE IF NOT EXISTS `gf_ssr_item` (
    `id`          BIGINT      NOT NULL AUTO_INCREMENT,
    `item_id`     INT         NOT NULL UNIQUE,
    `item_name`   VARCHAR(255) NOT NULL,
    `item_type`   INT         NOT NULL COMMENT '10=人形, 20=武器',
    `ssr_type`    INT         NOT NULL COMMENT '1=限定角色, 2=限定武器, 3=常驻',
    `is_deleted`  INT         NOT NULL DEFAULT 0,
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='SSR物品字典表';

CREATE TABLE IF NOT EXISTS `gf_gacha_history` (
    `id`                        BIGINT NOT NULL AUTO_INCREMENT,
    `user_id`                   BIGINT NOT NULL,
    `permanent_pool_json`       TEXT,
    `character_pool_json`       TEXT,
    `weapon_pool_json`          TEXT,
    `custom_character_pool_json` TEXT,
    `custom_weapon_pool_json`   TEXT,
    `is_deleted`                INT NOT NULL DEFAULT 0,
    `created_at`                DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    INDEX `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='抽卡历史记录表';

CREATE TABLE IF NOT EXISTS `gf_gacha_ssr_record` (
    `id`          BIGINT NOT NULL AUTO_INCREMENT,
    `user_id`     BIGINT NOT NULL,
    `history_id`  BIGINT NOT NULL,
    `pool_type`   INT NOT NULL,
    `item_id`     BIGINT NOT NULL,
    `draw_order`  INT NOT NULL,
    `cost_draws`  INT NOT NULL,
    PRIMARY KEY (`id`),
    INDEX `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='SSR抽卡明细记录表';

CREATE TABLE IF NOT EXISTS `gf_gacha_ranking_list` (
    `id`          BIGINT NOT NULL AUTO_INCREMENT,
    `user_id`     BIGINT NOT NULL UNIQUE,
    `luck_value`  INT NOT NULL,
    `total_draws` INT NOT NULL,
    `is_deleted`  INT NOT NULL DEFAULT 0,
    `created_at`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='排行榜表';
