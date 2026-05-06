package org.example.xkl_java.bean;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class GfSsrItem {
    private Long id;
    private Integer itemId;
    private String itemName;
    private Integer itemType; //10人形，20武器
    private Integer ssrType; //1限定角色，2限定武器，3常驻
    private Integer isDeleted; //0未删除，1已删除
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
