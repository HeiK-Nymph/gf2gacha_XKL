package org.example.xkl_java.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.example.xkl_java.bean.GfGachaSsrRecord;
import org.example.xkl_java.vo.GachaItemVO;

import java.util.List;

@Mapper
public interface GfGachaSsrRecordMapper {
    List<GfGachaSsrRecord> getGfGachaSsrRecordListByUserId(@Param("userId") Long userId);
    void insertGfGachaSsrRecordList(List<GfGachaSsrRecord> gfGachaSsrRecordList);
    void deleteGfGachaSsrRecordByUserId(@Param("userId") Long userId);

    // 以下为业务方法
    List<GachaItemVO> getGachaItemVOListByUid(@Param("uid") Integer uid);

}
