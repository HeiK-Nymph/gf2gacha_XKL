package org.example.xkl_java.service;


import lombok.RequiredArgsConstructor;
import org.example.xkl_java.dto.GfGachaRankingListDTO;
import org.example.xkl_java.mapper.GfGachaRankingListMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional
public class GfGachaRankingListService {

    private final GfGachaRankingListMapper gfGachaRankingListMapper;

    public GfGachaRankingListDTO getGfGachaRankingList() {
        GfGachaRankingListDTO dto = new GfGachaRankingListDTO();
        dto.setGfGachaRankingListOrderByLuckValueDesc(
                gfGachaRankingListMapper.getGfGachaRankingListOrderByLuckValueDesc()
        );
        dto.setGfGachaRankingListOrderByTotalDrawsDesc(
                gfGachaRankingListMapper.getGfGachaRankingListOrderByTotalDrawsDesc()
        );
        return dto;
    }

    /**
     * 获取活跃抽卡用户数（去重）
     */
    public int getActiveUserCount() {
        return gfGachaRankingListMapper.countActiveUsers();
    }

}
