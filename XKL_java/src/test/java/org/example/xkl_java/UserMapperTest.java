package org.example.xkl_java;

import org.example.xkl_java.bean.User;
import org.example.xkl_java.mapper.UserMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import java.util.List;

@SpringBootTest
public class UserMapperTest {
    @Autowired
    private UserMapper userMapper;

    @Test
    public void testInsertUser() {
        User user = new User();
        user.setUid("uid007");
        user.setUserName("测试玩家");
        user.setCnt(null);

        User selected = userMapper.selectByUid(user.getUid());
        if (selected != null) {
            System.out.println("已存在");
            return;
        }

        userMapper.insertUser(user);
        System.out.println("插入成功！");

        Integer id = user.getId();
        System.out.println("数据库自增id: " + id);

        List<User> all = userMapper.selectAllUsers();
        System.out.println(all.size());
    }

    @Test
    public void testSelectByUid() {
        User user = userMapper.selectByUid("uid003");
        System.out.println(user);
    }

    @Test
    public void testDeleteByUid() {
        userMapper.deleteByUid("uid003");
        System.out.println("删除成功！");

    }

    @Test
    public void testSelectByUidAndCnt() {
        User user = userMapper.selectByUidAndCnt("uid007", null);
        System.out.println(user);
    }

}
