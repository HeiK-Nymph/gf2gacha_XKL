package org.example.xkl_java.service;

import lombok.RequiredArgsConstructor;
import org.example.xkl_java.dto.GfUserDTO;
import org.example.xkl_java.exception.BusinessException;
import org.example.xkl_java.mapper.GfGachaSsrRecordMapper;
import org.example.xkl_java.vo.GachaItemVO;
import org.example.xkl_java.vo.GachaRecordsVO;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class GfUserService {

    private final GfGachaSsrRecordMapper gfGachaSsrRecordMapper;


    // 根据uid获得抽卡记录
    public GfUserDTO getGachaInfoByUid(Integer uid) {
        List<GachaItemVO> allItems = getAllPoolGachaItems(uid);
        if (allItems.isEmpty()) {
            throw new BusinessException("该用户没有抽卡记录");
        }
        List<GachaRecordsVO> gachaRecordsList = buildGachaRecordsList(allItems);
        return buildGfUserDTO(String.valueOf(uid), gachaRecordsList);
    }


    //获取所有池子的抽卡记录
    public List<GachaItemVO> getAllPoolGachaItems(Integer uid) {
        return gfGachaSsrRecordMapper.getGachaItemVOListByUid(uid);
    }

    //判断是否歪了，除了poolType为1外，其他池子中的ssrType为3的都算歪，isWai设置为1
    public List<GachaItemVO> isWai(List<GachaItemVO> gachaItems) {
        for (GachaItemVO gachaItemVO : gachaItems) {
            if (gachaItemVO.getPoolType() != 1 && gachaItemVO.getSsrType() == 3) {
                gachaItemVO.setIsWai(1);
            }
        }
        return gachaItems;
    }

    //拆分五个池子，组装GachaRecordsVO
    public List<GachaRecordsVO> buildGachaRecordsList(List<GachaItemVO> gachaItemVOList) {
        Map<Integer, List<GachaItemVO>> groupedByPool = gachaItemVOList.stream().collect(Collectors.groupingBy(GachaItemVO::getPoolType));
        List<GachaRecordsVO> res = new ArrayList<>();
        for (Map.Entry<Integer, List<GachaItemVO>> entry : groupedByPool.entrySet()) {
            Integer poolType = entry.getKey();
            List<GachaItemVO> items = entry.getValue();
            GachaRecordsVO vo = new GachaRecordsVO();
            vo.setPoolType(poolType);
            int totalSSR = 0;
            int waiCnt = 0;
            int totalDraws = 0;
            for (GachaItemVO item : items) {
                if (item.getItemId() != null && item.getItemId() == 0) {
                    // question占位符
                    item.setItemName("question");
                    item.setItemType(0);
                    item.setSsrType(0);
                    item.setIsWai(0);
                    // 修复：question的costDraws也要计入池子总抽数
                    if (item.getCostDraws() != null) {
                        totalDraws += item.getCostDraws();
                    }
                } else {
                    // 真实 SSR 物品
                    totalSSR++;

                    // 计算 isWai：限定池中 ssrType==3(常驻) 就是歪了
                    boolean isWai = (poolType != 1) && (item.getSsrType() != null && item.getSsrType() == 3);
                    item.setIsWai(isWai ? 1 : 0);
                    if (isWai) waiCnt++;

                    // 累加该池子总抽数
                    if (item.getCostDraws() != null) {
                        totalDraws += item.getCostDraws();
                    }
                }
            }
            vo.setTotalSSR(totalSSR);
            vo.setWaiCnt(waiCnt);
            vo.setTotalDraws(totalDraws);
            vo.setGachaItems(items);
            res.add(vo);
        }
        return res;
    }

    //组装GfUserDTO
    public GfUserDTO buildGfUserDTO(List<GachaRecordsVO> gachaRecordsList) {
        return buildGfUserDTO(null, gachaRecordsList);
    }

    //组装GfUserDTO（带uid）
    public GfUserDTO buildGfUserDTO(String uid, List<GachaRecordsVO> gachaRecordsList) {
        GfUserDTO dto = new GfUserDTO();
        dto.setUid(uid);

        int totalDraws = 0;
        int totalSSR = 0;
        int waiCnt = 0;
        int permanentCnt = 0;
        int characterCnt = 0;
        int weaponCnt = 0;
        int characterSSRCnt = 0;
        int weaponSSRCnt = 0;
        int permanentSSRCnt = 0;
        for (GachaRecordsVO gachaRecordsVO : gachaRecordsList) {
            totalDraws += gachaRecordsVO.getTotalDraws();
            totalSSR += gachaRecordsVO.getTotalSSR();
            waiCnt += gachaRecordsVO.getWaiCnt();
            if (gachaRecordsVO.getPoolType() == 1) {
                permanentCnt += gachaRecordsVO.getTotalDraws();
                permanentSSRCnt += gachaRecordsVO.getTotalSSR();
            } else if (gachaRecordsVO.getPoolType() == 3 || gachaRecordsVO.getPoolType() == 6) {
                characterCnt += gachaRecordsVO.getTotalDraws();
                characterSSRCnt += gachaRecordsVO.getTotalSSR();
            } else if (gachaRecordsVO.getPoolType() == 4 || gachaRecordsVO.getPoolType() == 7) {
                weaponCnt += gachaRecordsVO.getTotalDraws();
                weaponSSRCnt += gachaRecordsVO.getTotalSSR();
            }
        }

        int safeRate = totalDraws == 0 ? 0 : (totalSSR - waiCnt) * 100 / totalSSR;
        int avgCharacter = characterSSRCnt == 0 ? 0 : characterCnt / characterSSRCnt;
        int avgWeapon = weaponSSRCnt == 0 ? 0 : weaponCnt / weaponSSRCnt;
        int avgPermanent = permanentSSRCnt == 0 ? 0 : permanentCnt / permanentSSRCnt;

        dto.setTotalDraws(totalDraws);
        dto.setTotalSSR(totalSSR);
        dto.setWaiCnt(waiCnt);
        dto.setSafeRate(safeRate);
        dto.setAvgCharacter(avgCharacter);
        dto.setAvgWeapon(avgWeapon);
        dto.setAvgPermanent(avgPermanent);
        dto.setGachaRecordsList(gachaRecordsList);
        return dto;
    }

    /**
     * 计算欧皇值（luckValue）
     * 公式：luckValue = floor(8000/avgCostDraws) + floor(noWaiRate×300) + floor(earlyPct×150)
     */
    public int calculateLuckValue(List<GachaItemVO> allItems) {
        final int EARLY_THRESHOLD = 30;

        int totalSSR = 0;
        int sumCostDraws = 0;
        int waiCnt = 0;
        int limitedSSR = 0;
        int earlyCnt = 0;

        for (GachaItemVO item : allItems) {
            // question占位符不计入SSR统计
            if (item.getItemId() != null && item.getItemId() == 0) {
                continue;
            }
            totalSSR++;
            int cost = item.getCostDraws() != null ? item.getCostDraws() : 0;
            sumCostDraws += cost;

            if (cost <= EARLY_THRESHOLD) earlyCnt++;

            // 仅限定池（非常驻池 poolType != 1）计算歪率
            if (item.getPoolType() != null && item.getPoolType() != 1) {
                limitedSSR++;
                if (item.getIsWai() != null && item.getIsWai() == 1) {
                    waiCnt++;
                }
            }
        }

        if (totalSSR == 0) return 0;

        // 维度1：出率分 = 8000 / avgCostDraws
        double avgCostDraws = (double) sumCostDraws / totalSSR;
        int rateScore = (int) (8000.0 / avgCostDraws);
        // 样本量衰减：SSR数不足5个时，出率分打折
        if (totalSSR < 5) {
            rateScore = (int) (rateScore * totalSSR / 5.0);
        }

        // 维度2：不歪分
        int waiScore;
        if (limitedSSR == 0) {
            // 没有限定池SSR数据，给中间分150（及格分）
            waiScore = 150;
        } else {
            double noWaiRate = 1.0 - (double) waiCnt / limitedSSR;
            waiScore = (int) (noWaiRate * 300);
            // 样本量衰减：限定池SSR不足3个时，不歪分打折
            if (limitedSSR < 3) {
                waiScore = (int) (waiScore * limitedSSR / 3.0);
            }
        }

        // 维度3：早出分
        double earlyPct = (double) earlyCnt / totalSSR;
        int earlyScore = (int) (earlyPct * 150);

        return rateScore + waiScore + earlyScore;
    }
}
