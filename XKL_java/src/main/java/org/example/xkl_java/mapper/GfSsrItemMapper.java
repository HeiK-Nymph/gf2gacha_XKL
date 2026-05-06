package org.example.xkl_java.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.example.xkl_java.bean.GfSsrItem;

import java.util.List;

@Mapper
public interface GfSsrItemMapper {
    List<GfSsrItem> getGfSsrItemList();
    GfSsrItem getGfSsrItemByItemId(@Param("itemId") Integer itemId);
    void insertGfSsrItem(GfSsrItem gfSsrItem);
    void insertGfSsrItemList(List<GfSsrItem> gfSsrItemList);
    void removeGfSsrItemByItemId(@Param("itemId") Integer itemId);
    void restoreGfSsrItemAll();
    void deleteGfSsrItemByIsDeleted();
}
