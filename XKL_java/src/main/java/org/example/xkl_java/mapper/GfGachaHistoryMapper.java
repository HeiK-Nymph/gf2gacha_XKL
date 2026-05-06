package org.example.xkl_java.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.example.xkl_java.bean.GfGachaHistory;

@Mapper
public interface GfGachaHistoryMapper {
    GfGachaHistory getGfGachaHistoryByUserId(@Param("userId") Long userId);
    GfGachaHistory getLatestGfGachaHistoryByUserId(@Param("userId") Long userId);
    void insertGfGachaHistory(GfGachaHistory gfGachaHistory);
    void removeGfGachaHistoryByUserId(@Param("userId") Long userId);
    void deleteGfGachaHistoryByIsDeleted();
}
