package org.example.xkl_java.service;

import lombok.RequiredArgsConstructor;
import org.example.xkl_java.bean.GfSsrItem;
import org.example.xkl_java.dto.GfSsrItemBatchDTO;
import org.example.xkl_java.dto.GfSsrItemDTO;
import org.example.xkl_java.mapper.GfSsrItemMapper;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;


@Service
@RequiredArgsConstructor
@Transactional
public class GfSsrItemService {

    private final GfSsrItemMapper gfSsrItemMapper;

    public void batchInsert(GfSsrItemBatchDTO gfSsrItemBatchDTO) {
        List<GfSsrItem> gfSsrItemList = gfSsrItemBatchDTO.getGfSsrItemList();
        gfSsrItemMapper.insertGfSsrItemList(gfSsrItemList);
    }

    public GfSsrItemDTO getGfSsrItemByItemId(Integer itemId) {
        GfSsrItem gfSsrItem = gfSsrItemMapper.getGfSsrItemByItemId(itemId);
        GfSsrItemDTO gfSsrItemDTO = new GfSsrItemDTO();
        BeanUtils.copyProperties(gfSsrItem, gfSsrItemDTO);
        return gfSsrItemDTO;
    }

    public List<GfSsrItemDTO> getGfSsrItemAll() {
        List<GfSsrItem> gfSsrItemList = gfSsrItemMapper.getGfSsrItemList();
        List<GfSsrItemDTO> gfSsrItemDTOList = new ArrayList<>();
        for (GfSsrItem gfSsrItem : gfSsrItemList) {
            GfSsrItemDTO gfSsrItemDTO = new GfSsrItemDTO();
            BeanUtils.copyProperties(gfSsrItem, gfSsrItemDTO);
            gfSsrItemDTOList.add(gfSsrItemDTO);
        }
        return gfSsrItemDTOList;
    }

    /**
     * 获取 SSR 物品总数
     */
    public int getSsrItemCount() {
        return gfSsrItemMapper.countSsrItems();
    }

    public void removeGfSsrItemByItemId(Integer itemId) {
        gfSsrItemMapper.removeGfSsrItemByItemId(itemId);
    }

    public void restoreGfSsrItemAll() {
        gfSsrItemMapper.restoreGfSsrItemAll();
    }

    /** 回收站：查询所有已删除的SSR物品 */
    public List<GfSsrItemDTO> getDeletedGfSsrItemList() {
        List<GfSsrItem> gfSsrItemList = gfSsrItemMapper.getDeletedGfSsrItemList();
        List<GfSsrItemDTO> gfSsrItemDTOList = new ArrayList<>();
        for (GfSsrItem gfSsrItem : gfSsrItemList) {
            GfSsrItemDTO dto = new GfSsrItemDTO();
            BeanUtils.copyProperties(gfSsrItem, dto);
            gfSsrItemDTOList.add(dto);
        }
        return gfSsrItemDTOList;
    }

    /** 回收站：恢复单条已删除的SSR物品 */
    public void restoreGfSsrItemByItemId(Integer itemId) {
        int rows = gfSsrItemMapper.restoreGfSsrItemByItemId(itemId);
        if (rows == 0) {
            throw new RuntimeException("未找到可恢复的物品或该物品未被删除");
        }
    }

    public void deleteGfSsrItemByIsDeleted() {
        gfSsrItemMapper.deleteGfSsrItemByIsDeleted();
    }

}
