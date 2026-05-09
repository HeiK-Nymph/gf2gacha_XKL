package org.example.xkl_java.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 用户列表返回 DTO（隐藏密码等敏感信息）
 */
@Data
@AllArgsConstructor
@NoArgsConstructor
public class SysUserListDTO {

    private Long id;
    private String username;
    private Integer role;       // 0=普通用户, 1=管理员
    private String status;      // 0=封禁, 1=正常
    private String lastLoginTime;
    private String createdAt;
}
