package org.example.xkl_java.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.example.xkl_java.bean.GfSsrItem;

import java.util.List;

@Mapper
public interface GfSsrItemMapper {
    List<GfSsrItem> getGfSsrItemList();
    //统计未删除物品数量
    int countSsrItems();
    GfSsrItem getGfSsrItemByItemId(@Param("itemId") Integer itemId);
    void insertGfSsrItem(GfSsrItem gfSsrItem);
    void insertGfSsrItemList(List<GfSsrItem> gfSsrItemList);
    void removeGfSsrItemByItemId(@Param("itemId") Integer itemId);
    void restoreGfSsrItemAll();
    /** 回收站：查询所有已删除的记录 */
    List<GfSsrItem> getDeletedGfSsrItemList();
    /** 回收站：恢复单条已删除记录，返回影响行数 */
    int restoreGfSsrItemByItemId(@Param("itemId") Integer itemId);
    void deleteGfSsrItemByIsDeleted();
}
