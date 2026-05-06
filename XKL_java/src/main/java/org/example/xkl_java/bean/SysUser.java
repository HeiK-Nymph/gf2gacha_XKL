package org.example.xkl_java.bean;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class SysUser {
    private Long id;
    private String username;
    private String password;
    private Integer role; //0普通用户，1管理员
    private String status; //0封禁，1正常
    private LocalDateTime lastLoginTime; //LocalDateTime now = LocalDateTime.now();
    private Integer isDeleted; //0未删除，1已删除
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
