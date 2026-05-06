package org.example.xkl_java.bean;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class GfUser {
    private Long id;
    private Integer uid;
    private Long sysUserId;
    private Integer isDeleted; //0未删除，1已删除
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
