package org.example.xkl_java.vo;

import lombok.Data;

import java.util.List;

@Data
public class GachaRecordsVO {
    private Integer poolType; //卡池类型:1常驻,3角色,4武器,6自选角色,7自选武器，0所有
    private Integer totalDraws; //总抽数
    private Integer totalSSR; //总SSR数
    private Integer waiCnt; //歪数，意思是除常驻池外，其他池子的所有SSR中的常驻SSR的数量
    private List<GachaItemVO> gachaItems; //注意gachaItems[0]为最新未知道具，用于计算垫抽数，不计入SSR数
}
