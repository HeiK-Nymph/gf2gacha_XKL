package org.example.xkl_java.controller;

import lombok.RequiredArgsConstructor;
import org.example.xkl_java.common.Result;
import org.example.xkl_java.dto.GfSsrItemBatchDTO;
import org.example.xkl_java.dto.GfSsrItemDTO;
import org.example.xkl_java.service.GfSsrItemService;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/gf-ssr-item")
@RequiredArgsConstructor
public class GfSsrItemController {

    private final GfSsrItemService gfSsrItemService;

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
    public Result<List<GfSsrItemDTO>> getGfSsrItemAll() {
        List<GfSsrItemDTO> gfSsrItemDTOList = gfSsrItemService.getGfSsrItemAll();
        return Result.success(gfSsrItemDTOList);
    }

    @PostMapping("/removeByItemId")
    public Result<Void> removeGfSsrItemByItemId(@RequestBody Map<String, Integer> map) {
        gfSsrItemService.removeGfSsrItemByItemId(map.get("itemId"));
        return Result.successMsg("删除成功");
    }

    @PostMapping("/restoreAll")
    public Result<Void> restoreGfSsrItemAll() {
        gfSsrItemService.restoreGfSsrItemAll();
        return Result.successMsg("恢复成功");
    }

    @PostMapping("/deleteByIsDeleted")
    public Result<Void> deleteGfSsrItemByIsDeleted() {
        gfSsrItemService.deleteGfSsrItemByIsDeleted();
        return Result.successMsg("删除成功");
    }

}
