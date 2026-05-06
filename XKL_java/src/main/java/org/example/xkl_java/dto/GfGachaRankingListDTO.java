package org.example.xkl_java.dto;

import lombok.Data;
import org.example.xkl_java.vo.GfGachaRankingListVO;

import java.util.List;

@Data
public class GfGachaRankingListDTO {
    private List<GfGachaRankingListVO> gfGachaRankingListOrderByLuckValueDesc;
    private List<GfGachaRankingListVO> gfGachaRankingListOrderByTotalDrawsDesc;
}
