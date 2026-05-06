package org.example.xkl_java;

import org.example.xkl_java.bean.SysUser;
import org.example.xkl_java.mapper.SysUserMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.time.LocalDateTime;
import java.time.ZoneId;

@SpringBootTest
public class SysUserMapperTests {

    @Autowired
    SysUserMapper sysUserMapper;

    @Test
    public void insertSysUser(){
        SysUser sysUser = new SysUser();
        sysUser.setUsername("Megumin");
        sysUser.setPassword("52894");
        sysUser.setLastLoginTime(LocalDateTime.now(ZoneId.of("Asia/Shanghai")));
        sysUserMapper.insertSysUser(sysUser);
    }

    @Test
    public void getSysUser(){
        System.out.println(sysUserMapper.getSysUserByUsername("Megumin"));
    }

    @Test
    public void removeSysUserByUsername(){
        sysUserMapper.removeSysUserByUsername("Megumin");
    }

    @Test
    public void deleteSysUserByIsDeleted(){
        sysUserMapper.deleteSysUserByIsDeleted();
    }
}
