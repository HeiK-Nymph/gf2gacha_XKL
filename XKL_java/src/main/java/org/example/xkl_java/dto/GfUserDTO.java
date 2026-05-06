package org.example.xkl_java.dto;

import lombok.Data;
import org.example.xkl_java.vo.GachaRecordsVO;

import java.util.List;

@Data
public class GfUserDTO {
    private String uid;
    private List<GachaRecordsVO> gachaRecordsList; //7个池子
    private Integer totalDraws; //总抽数
    private Integer totalSSR; //总SSR数
    private Integer safeRate; //保底不歪率，总SSR数/总抽数的百分比，不需要小数，注意所有的率都是向下取整的整数
    private Integer waiCnt; //歪数，意思是除常驻池外，其他池子的所有SSR中的常驻SSR的数量
    private Integer avgCharacter; //平均角色抽数，出一个角色SSR平均需要的抽数
    private Integer avgWeapon; //平均武器抽数，出一个武器SSR平均需要的抽数
    private Integer avgPermanent; //平均常驻抽数，出一个常驻SSR平均需要的抽数

}
