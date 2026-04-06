package org.example.xkl_java;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("org.example.xkl_java.mapper")
public class XklJavaApplication {

    public static void main(String[] args) {
        SpringApplication.run(XklJavaApplication.class, args);
    }

}
