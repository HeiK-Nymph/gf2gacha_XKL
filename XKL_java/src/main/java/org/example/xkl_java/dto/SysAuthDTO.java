package org.example.xkl_java.dto;

import lombok.Data;

/**
 * 认证相关 DTO（登录/注册共用）
 */
@Data
public class SysAuthDTO {

    /** 用户名 */
    private String username;

    /** 密码 */
    private String password;

    /** 邀请码（仅注册时必填） */
    private String inviteCode;
}
