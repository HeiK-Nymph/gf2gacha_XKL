package org.example.xkl_java.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.example.xkl_java.bean.GfGachaRankingList;
import org.example.xkl_java.vo.GfGachaRankingListVO;

import java.util.List;

@Mapper
public interface GfGachaRankingListMapper {
    List<GfGachaRankingListVO> getGfGachaRankingListOrderByLuckValueDesc();
    List<GfGachaRankingListVO> getGfGachaRankingListOrderByTotalDrawsDesc();
    //统计活跃抽卡用户数（去重）
    int countActiveUsers();
    void insertGfGachaRankingList(GfGachaRankingList gfGachaRankingList);
    void insertGfGachaRankingListList(List<GfGachaRankingList> gfGachaRankingListList);
    void removeGfGachaRankingListByUserId(@Param("userId") Long userId);
    void deleteGfGachaRankingListByIsDeleted();
    int updateGfGachaRankingListByUserId(GfGachaRankingList rankingList);
}
