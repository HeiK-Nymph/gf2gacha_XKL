package org.example.xkl_java.dto;

import lombok.Data;

@Data
public class GfSsrItemDTO {
    private Integer itemId;
    private String itemName;
    private Integer itemType; //10人形，20武器
    private Integer ssrType; //1限定角色，2限定武器，3常驻
}
