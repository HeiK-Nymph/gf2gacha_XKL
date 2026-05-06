package org.example.xkl_java;

import org.example.xkl_java.mapper.GfGachaSsrRecordMapper;
import org.example.xkl_java.vo.GachaItemVO;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.List;

@SpringBootTest
class GfGachaSsrRecordMapperTest {

    @Autowired
    private GfGachaSsrRecordMapper gfGachaSsrRecordMapper;

    @Test
    void testGetGachaItemVOListByUid() {
        Integer testUid = 3898920;
        List<GachaItemVO> items = gfGachaSsrRecordMapper.getGachaItemVOListByUid(testUid);

        System.out.println("查询结果:");
        System.out.println("  总记录数: " + items.size());

        int printCount = Math.min(20, items.size());
        System.out.println("  前" + printCount + "条记录:");
        for (int i = 0; i < printCount; i++) {
            GachaItemVO vo = items.get(i);
            System.out.println("    [" + i + "] itemId=" + vo.getItemId()
                    + ", itemName=" + vo.getItemName()
                    + ", poolType=" + vo.getPoolType()
                    + ", costDraws=" + vo.getCostDraws()
                    + ", drawOrder=" + vo.getDrawOrder());
        }

        if (items.size() > 20) {
            System.out.println("  ... 还有 " + (items.size() - 20) + " 条记录");
        }
    }
}
