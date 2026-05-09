package org.example.xkl_java.security;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 当前登录用户的上下文信息（存储在 Request 作用域）
 */
@Data
@AllArgsConstructor
@NoArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class LoginUser {

    /** 用户 ID */
    private Long id;

    /** 用户名 */
    private String username;

    /** 角色：0=普通用户, 1=管理员 */
    private Integer role;

    /** 登录时间 */
    private LocalDateTime loginTime;
}
