package org.example.xkl_java.controller;

import lombok.RequiredArgsConstructor;
import org.example.xkl_java.common.Result;
import org.example.xkl_java.dto.GfSsrItemBatchDTO;
import org.example.xkl_java.dto.GfSsrItemDTO;
import org.example.xkl_java.service.GfSsrItemService;
import org.example.xkl_java.security.RequireRole;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * SSR 物品管理 Controller
 * - 所有接口均需要管理员权限 (role=1)
 */
@RestController
@RequestMapping("/api/gf-ssr-item")
@RequiredArgsConstructor
@RequireRole(1)
public class GfSsrItemController {

    private final GfSsrItemService gfSsrItemService;

    /** 批量添加 SSR 物品 */
    @PostMapping("/insertList")
    public Result<Void> insertGfSsrItemList(@RequestBody GfSsrItemBatchDTO gfSsrItemBatchDTO) {
        gfSsrItemService.batchInsert(gfSsrItemBatchDTO);
        return Result.successMsg("插入成功");
    }

    @GetMapping("/getByItemId")
    public Result<GfSsrItemDTO> getGfSsrItemByItemId(@RequestParam Integer itemId) {
        GfSsrItemDTO gfSsrItemDTO = gfSsrItemService.getGfSsrItemByItemId(itemId);
        return Result.success(gfSsrItemDTO);
    }

    @GetMapping("/getAll")
    @RequireRole(1)
    public Result<List<GfSsrItemDTO>> getGfSsrItemAll() {
        List<GfSsrItemDTO> gfSsrItemDTOList = gfSsrItemService.getGfSsrItemAll();
        return Result.success(gfSsrItemDTOList);
    }

    /** 获取 SSR 物品总数 */
    @GetMapping("/count")
    public Result<Integer> getSsrItemCount() {
        return Result.success(gfSsrItemService.getSsrItemCount());
    }

    /** 删除 SSR 物品（逻辑删除） */
    @PostMapping("/removeByItemId")
    public Result<Void> removeGfSsrItemByItemId(@RequestBody Map<String, Integer> map) {
        gfSsrItemService.removeGfSsrItemByItemId(map.get("itemId"));
        return Result.successMsg("删除成功");
    }

    /** 恢复所有已删除的 SSR 物品 */
    @PostMapping("/restoreAll")
    public Result<Void> restoreGfSsrItemAll() {
        gfSsrItemService.restoreGfSsrItemAll();
        return Result.successMsg("恢复成功");
    }

    /** 回收站：查询所有已删除的SSR物品 */
    @GetMapping("/getDeleted")
    public Result<List<GfSsrItemDTO>> getDeletedGfSsrItemList() {
        List<GfSsrItemDTO> list = gfSsrItemService.getDeletedGfSsrItemList();
        return Result.success(list);
    }

    /** 回收站：恢复单条已删除的SSR物品 */
    @PostMapping("/restoreByItemId")
    public Result<Void> restoreGfSsrItemByItemId(@RequestBody Map<String, Integer> map) {
        gfSsrItemService.restoreGfSsrItemByItemId(map.get("itemId"));
        return Result.successMsg("恢复成功");
    }

    /** 物理删除所有已标记删除的 SSR 物品 */
    @PostMapping("/deleteByIsDeleted")
    public Result<Void> deleteGfSsrItemByIsDeleted() {
        gfSsrItemService.deleteGfSsrItemByIsDeleted();
        return Result.successMsg("删除成功");
    }

}
