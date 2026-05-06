package org.example.xkl_java;

import org.example.xkl_java.bean.GfUser;
import org.example.xkl_java.mapper.GfUserMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest
class GfUserMapperTest {

    @Autowired
    private GfUserMapper gfUserMapper;

    @Test
    void testGetGfUserByUid() {
        // 测试获取存在的用户
        Integer testUid = 3898920;
        GfUser user = gfUserMapper.getGfUserByUid(testUid);
        if (user != null) {
            System.out.println("找到用户:");
            System.out.println("  id: " + user.getId());
            System.out.println("  uid: " + user.getUid());
            System.out.println("  isDeleted: " + user.getIsDeleted());
        } else {
            System.out.println("用户不存在: uid=" + testUid);
        }
    }

    @Test
    void testGetGfUserByUid_NotExist() {
        // 测试获取不存在的用户
        Integer testUid = 9999999;
        GfUser user = gfUserMapper.getGfUserByUid(testUid);
        if (user != null) {
            System.out.println("找到用户:");
            System.out.println("  id: " + user.getId());
            System.out.println("  uid: " + user.getUid());
        } else {
            System.out.println("用户不存在: uid=" + testUid);
        }
    }
}
