package org.example.xkl_java.controller;

import org.example.xkl_java.common.Result;
import org.example.xkl_java.dto.SysAuthDTO;
import org.example.xkl_java.service.SysAuthService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 认证 Controller - 登录/注册接口（无需认证）
 */
@RestController
@RequestMapping("/api/sys-auth")
public class SysAuthController {

    @Autowired
    private SysAuthService sysAuthService;

    /**
     * 用户登录
     * POST /api/sys-auth/login
     *
     * @param dto {"username":"admin", "password":"admin123"}
     * @return {"code":200,"msg":"success","data":{"token":"jwt...","user":{...}}}
     */
    @PostMapping("/login")
    public Result<Map<String, Object>> login(@RequestBody SysAuthDTO dto) {
        return sysAuthService.login(dto);
    }

    /**
     * 用户注册
     * POST /api/sys-auth/register
     *
     * @param dto {"username":"newuser", "password":"123456"}
     */
    @PostMapping("/register")
    public Result<Void> register(@RequestBody SysAuthDTO dto) {
        return sysAuthService.register(dto);
    }
}
