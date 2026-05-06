package org.example.xkl_java.bean;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class GfGachaHistory {
    private Long id;
    private Long userId;
    private String permanentPoolJson; //常驻池JSON，1
    private String characterPoolJson; //角色池JSON，3
    private String weaponPoolJson; //武器池JSON，4
    private String customCharacterPoolJson; //自选角色池JSON，6
    private String customWeaponPoolJson; //自选武器池JSON，7
    private Integer isDeleted; //0未删除，1已删除
    private LocalDateTime createdAt;
}
