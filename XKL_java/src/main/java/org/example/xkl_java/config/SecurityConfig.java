package org.example.xkl_java.config;

import org.example.xkl_java.security.JwtAuthInterceptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Web MVC 配置 - 注册 JWT 拦截器 & CORS 配置
 */
@Configuration
public class SecurityConfig implements WebMvcConfigurer {

    @Autowired
    private JwtAuthInterceptor jwtAuthInterceptor;

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(jwtAuthInterceptor)
                .addPathPatterns("/api/**")          // 拦截所有 /api 路径
                .excludePathPatterns(                 // 排除白名单
                        // === 认证接口 ===
                        "/api/sys-auth/login",
                        "/api/sys-auth/register",
                        // === UniApp 公开接口（无需登录）===
                        "/api/gacha-web/get",          // 抽卡数据拉取 - UniApp 核心入口
                        "/api/gf-user/get",            // 抽卡查询公开
                        "/api/gf-gacha-ranking/get"    // 排行榜公开
                        // 注意：已移除 /api/gf-ssr-item/getAll 白名单
                        // SSR物品所有接口统一走 JWT + @RequireRole(1) 校验
                );
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**")
                .allowedOriginPatterns("*")
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .allowCredentials(true)
                .maxAge(3600);
    }
}
