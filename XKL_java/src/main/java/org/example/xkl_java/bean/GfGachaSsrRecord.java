package org.example.xkl_java.bean;

import lombok.Data;

@Data
public class GfGachaSsrRecord {
    private Long id;
    private Long userId;
    private Long historyId;
    private Integer poolType; //1常驻，3角色，4武器，6自选角色，7自选武器
    private Long itemId; //id为0的时候则表示为最新未知五星，本质是一个占位道具，用于计算垫抽数，即真正的最后一个五星后还抽了多少抽
    private Integer drawOrder; //池内顺序号
    private Integer costDraws; //距上次抽到五星后，又花费了多少抽才抽出当前五星，注意如果itemId为0的时候此时该数为垫抽数，注意如果当前为drawOrder最后的一个五星时，此时计算的应该是抽到当前的五星花费的抽数，尽管更早前并没有五星
}
