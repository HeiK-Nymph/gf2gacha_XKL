package org.example.xkl_java.controller;

import lombok.RequiredArgsConstructor;
import org.example.xkl_java.common.Result;
import org.example.xkl_java.dto.GfGachaRankingListDTO;
import org.example.xkl_java.service.GfGachaRankingListService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/gf-gacha-ranking")
@RequiredArgsConstructor
public class GfGachaRankingListController {

    private final GfGachaRankingListService gfGachaRankingListService;

    @GetMapping("/get")
    public Result<GfGachaRankingListDTO> getGfGachaRankingList() {
        return Result.success(gfGachaRankingListService.getGfGachaRankingList());
    }

}
