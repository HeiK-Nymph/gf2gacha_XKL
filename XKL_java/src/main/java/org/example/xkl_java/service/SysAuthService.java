package org.example.xkl_java.service;

import org.example.xkl_java.bean.SysUser;
import org.example.xkl_java.common.Result;
import org.example.xkl_java.dto.SysAuthDTO;
import org.example.xkl_java.dto.SysUserListVO;
import org.example.xkl_java.exception.BusinessException;
import org.example.xkl_java.mapper.SysUserMapper;
import org.example.xkl_java.security.JwtUtil;
import org.example.xkl_java.security.LoginUser;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 系统认证与授权 Service
 * - 登录 / 注册
 * - Token 生成
 * - 用户管理 CRUD
 * - 角色与状态变更
 */
@Service
public class SysAuthService {

    /**
     * 邀请码 → 角色映射表（硬编码，不可配置于数据库或前端）
     * key: 邀请码, value: 角色编号（0=普通用户, 1=管理员）
     */
    private static final Map<String, Integer> INVITE_CODE_ROLE_MAP = Map.of(
            "52894", 1,   // 管理员邀请码
            "52614", 0    // 普通用户邀请码
    );

    @Autowired
    private SysUserMapper sysUserMapper;

    @Autowired
    private JwtUtil jwtUtil;

    /** BCrypt 密码编码器（线程安全，可复用） */
    private static final BCryptPasswordEncoder PASSWORD_ENCODER = new BCryptPasswordEncoder();

    private static final DateTimeFormatter DT_FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    /** 统一的登录失败安全提示（不暴露用户是否存在） */
    private static final String LOGIN_FAIL_MSG = "登录失败，请检查用户名和密码";

    /**
     * 用户登录（安全：用户不存在与密码错误返回相同提示）
     */
    public Result<Map<String, Object>> login(SysAuthDTO dto) {
        // 前置校验
        if (dto.getUsername() == null || dto.getUsername().isBlank()) {
            throw new BusinessException("用户名不能为空");
        }
        if (dto.getPassword() == null || dto.getPassword().isBlank()) {
            throw new BusinessException("密码不能为空");
        }

        // 查询用户
        SysUser user = sysUserMapper.getSysUserByUsername(dto.getUsername());
        if (user == null) {
            // 安全：不暴露用户是否存在，统一返回模糊提示
            throw new BusinessException(LOGIN_FAIL_MSG);
        }

        // 校验密码（BCrypt 哈希比对）
        if (!PASSWORD_ENCODER.matches(dto.getPassword(), user.getPassword())) {
            throw new BusinessException(LOGIN_FAIL_MSG);
        }

        // 检查账号状态（此条可单独提示，因为用户已确认存在）
        if ("0".equals(user.getStatus())) {
            throw new BusinessException("该账号已被封禁，请联系管理员");
        }

        // 生成 JWT
        String token = jwtUtil.generateToken(user.getUsername(), user.getId(), user.getRole());

        // 更新最后登录时间
        sysUserMapper.updateLastLoginTimeByUsername(user.getUsername(), LocalDateTime.now());

        // 构造返回数据
        LoginUser loginUser = new LoginUser(
                user.getId(),
                user.getUsername(),
                user.getRole(),
                LocalDateTime.now()
        );

        Map<String, Object> data = new HashMap<>();
        data.put("token", token);
        data.put("user", loginUser);

        return Result.success(data);
    }

    /**
     * 用户注册（需通过邀请码校验）
     */
    public Result<Void> register(SysAuthDTO dto) {
        // 前置校验
        if (dto.getUsername() == null || dto.getUsername().isBlank()) {
            throw new BusinessException("用户名不能为空");
        }
        if (dto.getPassword() == null || dto.getPassword().isBlank()) {
            throw new BusinessException("密码不能为空");
        }
        if (dto.getPassword().length() < 4) {
            throw new BusinessException("密码至少4位");
        }
        if (dto.getInviteCode() == null || dto.getInviteCode().isBlank()) {
            throw new BusinessException("邀请码不能为空");
        }

        // 校验邀请码（硬编码映射表，不可从数据库/配置文件读取）
        Integer assignedRole = INVITE_CODE_ROLE_MAP.get(dto.getInviteCode());
        if (assignedRole == null) {
            throw new BusinessException("邀请码无效，无法注册");
        }

        // 检查用户名是否已存在
        SysUser existing = sysUserMapper.getSysUserByUsername(dto.getUsername());
        if (existing != null) {
            throw new BusinessException("该用户名已被注册");
        }

        // 创建新用户（角色由邀请码决定）
        SysUser newUser = new SysUser();
        newUser.setUsername(dto.getUsername());
        newUser.setPassword(PASSWORD_ENCODER.encode(dto.getPassword())); // BCrypt 加密后存储
        newUser.setRole(assignedRole);          // 根据邀请码分配角色
        newUser.setStatus("1");                 // 默认正常
        newUser.setIsDeleted(0);
        newUser.setCreatedAt(LocalDateTime.now());
        newUser.setUpdatedAt(LocalDateTime.now());

        sysUserMapper.insertSysUser(newUser);
        return Result.successMsg("注册成功");
    }

    /**
     * 获取所有系统用户列表（隐藏敏感信息）
     */
    public Result<List<SysUserListVO>> getUserList() {
        List<SysUser> users = sysUserMapper.getAllUsers();
        List<SysUserListVO> voList = users.stream()
                .map(this::convertToVO)
                .toList();
        return Result.success(voList);
    }

    /**
     * 获取注册用户总数
     */
    public Result<Integer> getUserCount() {
        return Result.success(sysUserMapper.countUsers());
    }

    /**
     * 更改用户角色
     */
    public Result<Void> updateRole(String username, Integer role) {
        validateUsername(username);
        if (role != 0 && role != 1) {
            throw new BusinessException("角色值无效，只能为 0(普通用户) 或 1(管理员)");
        }
        sysUserMapper.updateRoleByUsername(username, role);
        return Result.successMsg("角色更新成功");
    }

    /**
     * 封禁/解封用户
     */
    public Result<Void> updateStatus(String username, String status) {
        validateUsername(username);
        if (!"0".equals(status) && !"1".equals(status)) {
            throw new BusinessException("状态值无效，只能为 0(封禁) 或 1(正常)");
        }
        sysUserMapper.updateStatusByUsername(username, status);
        return Result.successMsg("状态更新成功");
    }

    /**
     * 逻辑删除用户
     */
    public Result<Void> removeUser(String username) {
        validateUsername(username);
        sysUserMapper.removeSysUserByUsername(username);
        return Result.successMsg("用户已删除");
    }

    private void validateUsername(String username) {
        if (username == null || username.isBlank()) {
            throw new BusinessException("用户名不能为空");
        }
        SysUser user = sysUserMapper.getSysUserByUsername(username);
        if (user == null) {
            throw new BusinessException("用户不存在");
        }
    }

    private SysUserListVO convertToVO(SysUser user) {
        return new SysUserListVO(
                user.getId(),
                user.getUsername(),
                user.getRole(),
                user.getStatus(),
                user.getLastLoginTime() != null ? user.getLastLoginTime().format(DT_FORMAT) : null,
                user.getIsDeleted(),
                user.getCreatedAt() != null ? user.getCreatedAt().format(DT_FORMAT) : null,
                user.getUpdatedAt() != null ? user.getUpdatedAt().format(DT_FORMAT) : null
        );
    }
}
