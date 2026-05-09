package org.example.xkl_java.security;

import java.lang.annotation.*;

/**
 * 角色权限注解 - 标记在 Controller 方法或类上
 *
 * <p>使用示例：
 * <pre>
 *   &#64;RequireRole(1)   // 仅管理员可访问
 *   &#64;RequireRole({0, 1})  // 所有已登录用户均可访问
 * </pre>
 */
@Target({ElementType.METHOD, ElementType.TYPE})
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface RequireRole {

    /**
     * 允许的角色编码数组
     * 0 = 普通用户
     * 1 = 管理员
     */
    int[] value() default {};
}
