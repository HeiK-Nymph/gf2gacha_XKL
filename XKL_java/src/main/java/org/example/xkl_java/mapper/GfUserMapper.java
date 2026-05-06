package org.example.xkl_java.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.example.xkl_java.bean.GfUser;

@Mapper
public interface GfUserMapper {
    GfUser getGfUserByUid(@Param("uid") Integer uid);
    void insertGfUser(GfUser gfUser);
    void removeGfUserByUid(@Param("uid") Integer uid);
    void deleteGfUserByIsDeleted();
}
