package org.example.xkl_java.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 用户列表 VO（返回给前端，不包含密码）
 */
@Data
@AllArgsConstructor
@NoArgsConstructor
public class SysUserListVO {

    private Long id;
    private String username;
    private Integer role;           // 0=普通用户, 1=管理员
    private String status;          // 0=封禁, 1=正常
    private String lastLoginTime;   // 最后登录时间
    private Integer isDeleted;      // 0未删除, 1已删除
    private String createdAt;       // 创建时间
    private String updatedAt;       // 更新时间
}
