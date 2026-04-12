package org.example.xkl_java.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.example.xkl_java.bean.User;

import java.util.List;

@Mapper
public interface UserMapper {
    void insertUser(@Param("user") User user);
    User selectByUid(@Param("uid") String uid);
    List<User> selectAllUsers();
    void updateCnt(@Param("uid") String uid, @Param("cnt") Integer cnt);
    void deleteByUid(@Param("uid") String uid);
    User selectByUidAndCnt(@Param("uid") String uid, @Param("cnt") Integer cnt);
    void updateUserNameAndCnt(@Param("uid") String uid, @Param("cnt") Integer cnt, @Param("userName") String userName);
    List<User> selectByUidIn(@Param("uidList") List<String> uidList);
}
