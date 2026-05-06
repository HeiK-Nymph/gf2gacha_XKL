package org.example.xkl_java.vo;

import lombok.Data;

@Data
public class GachaItemVO {
    private Integer itemId; //0为question，占位用
    private String itemName; //question为最新的未知道具，占位用于计算垫抽数，垫抽数是指最新的五星后还抽了多少次
    private Integer itemType; //类型:10人形,20武器
    private Integer ssrType; //SSR类型:1限定角色,2限定武器,3常驻
    private Integer costDraws; //距离上一次五星抽数，相当于抽出这个五星的抽数
    private Integer drawOrder; //池内顺序号
    private Integer poolType; //卡池类型:1常驻,3角色,4武器,6自选角色,7自选武器
    private Integer isWai = 0; //是否歪，0否，1是； 注意question不计入歪数和SSR数，并且它的isWai为0
}
