package org.example.xkl_java.bean;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class GfGachaRankingList {
    private Long id;
    private Long userId;
    private Integer luckValue; //欧皇值
    private Integer totalDraws;
    private Integer isDeleted; //0未删除，1已删除
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
