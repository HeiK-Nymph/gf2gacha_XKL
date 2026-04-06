package org.example.xkl_java.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.example.xkl_java.bean.User;

import java.util.List;

@Mapper
public interface UserMapper {
    int insertUser(User user);
    User selectByUid(String uid);
    List<User> selectAllUsers();
    int updateCnt(String uid, Integer cnt);
    int deleteByUid(String uid);
}
