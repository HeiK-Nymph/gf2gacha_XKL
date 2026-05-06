package org.example.xkl_java.config;

import io.netty.channel.ChannelOption;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;
import reactor.netty.resources.ConnectionProvider;

import java.time.Duration;

@Configuration
public class WebClientConfig {

    @Bean
    public WebClient webClient() {
        // 配置连接池：空闲超过10秒的连接自动清除，避免复用被服务端关闭的连接
        ConnectionProvider connectionProvider = ConnectionProvider.builder("gacha-pool")
                .maxIdleTime(Duration.ofSeconds(10))
                .maxLifeTime(Duration.ofMinutes(2))
                .evictInBackground(Duration.ofSeconds(15))
                .build();

        HttpClient httpClient = HttpClient.create(connectionProvider)
                .responseTimeout(Duration.ofSeconds(30))
                .followRedirect(true)
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 10000);

        return WebClient.builder()
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .codecs(configurer -> configurer.defaultCodecs().maxInMemorySize(16 * 1024 * 1024))
                .build();
    }
}
