package org.example.xkl_java.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.example.xkl_java.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;

import java.io.IOException;
import java.util.Arrays;
import java.util.List;

/**
 * JWT 认证拦截器
 * - 校验请求头中的 Bearer Token
 * - 解析用户信息并存入 ThreadLocal
 * - 支持通过 @RequireRole 注解进行角色校验
 */
@Component
public class JwtAuthInterceptor implements HandlerInterceptor {

    @Autowired
    private JwtUtil jwtUtil;

    /** 不需要认证的路径白名单 */
    public static final List<String> WHITE_LIST = Arrays.asList(
            "/api/sys-auth/login",
            "/api/sys-auth/register"
    );

    private static final ThreadLocal<LoginUser> USER_HOLDER = new ThreadLocal<>();

    /**
     * 获取当前登录用户（Controller/Service 层调用）
     */
    public static LoginUser getCurrentUser() {
        return USER_HOLDER.get();
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        // 非控制器方法直接放行
        if (!(handler instanceof HandlerMethod)) {
            return true;
        }

        String uri = request.getRequestURI();

        // 白名单路径精确匹配（仅放行 login 和 register）
        if (WHITE_LIST.contains(uri)) {
            return true;
        }

        // 获取 Authorization 头
        String authHeader = request.getHeader("Authorization");
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            writeUnauthorized(response, "未提供有效的认证 Token，请先登录");
            return false;
        }

        String token = authHeader.substring(7);

        // 校验 Token 有效性
        if (!jwtUtil.validateToken(token)) {
            writeUnauthorized(response, "Token 已失效或非法，请重新登录");
            return false;
        }

        // 检查 Token 过期
        if (jwtUtil.isTokenExpired(token)) {
            writeUnauthorized(response, "Token 已过期，请重新登录");
            return false;
        }

        // 解析用户信息并设置到上下文
        try {
            LoginUser loginUser = new LoginUser(
                    jwtUtil.getUserIdFromToken(token),
                    jwtUtil.getUsernameFromToken(token),
                    jwtUtil.getRoleFromToken(token),
                    java.time.LocalDateTime.now()
            );
            USER_HOLDER.set(loginUser);

            // 检查角色权限注解
            HandlerMethod method = (HandlerMethod) handler;
            RequireRole roleAnnotation = method.getMethodAnnotation(RequireRole.class);
            if (roleAnnotation != null && !checkRole(roleAnnotation.value(), loginUser.getRole())) {
                writeForbidden(response, "权限不足，需要管理员权限");
                return false;
            }

            // 类级别角色检查
            RequireRole classRoleAnnotation = method.getBeanType().getDeclaredAnnotation(RequireRole.class);
            if (classRoleAnnotation != null && !checkRole(classRoleAnnotation.value(), loginUser.getRole())) {
                writeForbidden(response, "权限不足，需要管理员权限");
                return false;
            }

            return true;
        } catch (Exception e) {
            writeUnauthorized(response, "Token 解析失败：" + e.getMessage());
            return false;
        }
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) {
        USER_HOLDER.remove();
    }

    private boolean checkRole(int[] requiredRoles, int userRole) {
        if (requiredRoles.length == 0) return true;
        for (int r : requiredRoles) {
            if (r == userRole) return true;
        }
        return false;
    }

    private void writeUnauthorized(HttpServletResponse response, String msg) throws IOException {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType("application/json;charset=UTF-8");
        ObjectMapper mapper = new ObjectMapper();
        response.getWriter().write(mapper.writeValueAsString(Result.fail(401, msg)));
    }

    private void writeForbidden(HttpServletResponse response, String msg) throws IOException {
        response.setStatus(HttpServletResponse.SC_FORBIDDEN);
        response.setContentType("application/json;charset=UTF-8");
        ObjectMapper mapper = new ObjectMapper();
        response.getWriter().write(mapper.writeValueAsString(Result.fail(403, msg)));
    }
}
