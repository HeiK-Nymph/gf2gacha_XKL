package org.example.xkl_java.config;


import com.github.pagehelper.PageInterceptor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;


@Configuration
public class MyBatisConfig {

    @Bean
    PageInterceptor pageInterceptor() {
        // 创建分页插件对象
        PageInterceptor interceptor = new PageInterceptor();
        // 设置参数
        return interceptor;
    }

}
