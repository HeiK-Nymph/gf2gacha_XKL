package org.example.xkl_java.controller;

import org.example.xkl_java.common.Result;
import org.example.xkl_java.security.RequireRole;
import org.example.xkl_java.service.SysAuthService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

/**
 * 系统用户管理 Controller - 需要管理员权限
 *
 * <p>所有接口均需要 role=1 (管理员) 才能调用</p>
 */
@RestController
@RequestMapping("/api/sys-user")
@RequireRole(1)
public class SysUserController {

    @Autowired
    private SysAuthService sysAuthService;

    /**
     * 获取所有用户列表
     * GET /api/sys-user/list
     */
    @GetMapping("/list")
    public Result<?> getUserList() {
        return sysAuthService.getUserList();
    }

    /**
     * 获取注册用户总数
     * GET /api/sys-user/count
     */
    @GetMapping("/count")
    public Result<Integer> getUserCount() {
        return sysAuthService.getUserCount();
    }

    /**
     * 更改用户角色
     * POST /api/sys-user/updateRole
     * Body: {"username":"xxx","role":1}
     */
    @PostMapping("/updateRole")
    public Result<Void> updateRole(@RequestBody java.util.Map<String, Object> body) {
        String username = (String) body.get("username");
        Integer role = ((Number) body.get("role")).intValue();
        return sysAuthService.updateRole(username, role);
    }

    /**
     * 封禁/解封用户
     * POST /api/sys-user/updateStatus
     * Body: {"username":"xxx","status":"0"}
     */
    @PostMapping("/updateStatus")
    public Result<Void> updateStatus(@RequestBody java.util.Map<String, Object> body) {
        String username = (String) body.get("username");
        String status = (String) body.get("status");
        return sysAuthService.updateStatus(username, status);
    }

    /**
     * 逻辑删除用户
     * POST /api/sys-user/remove
     * Body: {"username":"xxx"}
     */
    @PostMapping("/remove")
    public Result<Void> removeUser(@RequestBody java.util.Map<String, Object> body) {
        String username = (String) body.get("username");
        return sysAuthService.removeUser(username);
    }
}
