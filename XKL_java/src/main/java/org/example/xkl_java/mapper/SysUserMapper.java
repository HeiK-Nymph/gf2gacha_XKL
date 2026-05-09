package org.example.xkl_java.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.example.xkl_java.bean.SysUser;

import java.time.LocalDateTime;

@Mapper
public interface SysUserMapper {
    SysUser getSysUserByUsername(@Param("username") String username);
    void insertSysUser(SysUser sysUser);
    void updatePasswordByUsername(@Param("username") String username, @Param("password") String password);
    void updateLastLoginTimeByUsername(@Param("username") String username, @Param("lastLoginTime") LocalDateTime lastLoginTime);
    void updateStatusByUsername(@Param("username") String username, @Param("status") String status);
    void updateRoleByUsername(@Param("username") String username, @Param("role") Integer role);
    //逻辑删除
    void removeSysUserByUsername(@Param("username") String username);
    //获取所有未删除用户
    java.util.List<SysUser> getAllUsers();
    //统计未删除用户数量
    int countUsers();
    //物理删除
    void deleteSysUserByIsDeleted();
}
