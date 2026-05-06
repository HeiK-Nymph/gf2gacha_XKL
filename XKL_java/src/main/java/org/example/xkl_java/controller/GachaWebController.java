package org.example.xkl_java.controller;

import lombok.RequiredArgsConstructor;
import org.example.xkl_java.common.Result;
import org.example.xkl_java.dto.GfUserDTO;
import org.example.xkl_java.dto.firstRequestDTO;
import org.example.xkl_java.service.GachaWebService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/gacha-web")
@RequiredArgsConstructor
public class GachaWebController {

    private final GachaWebService gachaWebService;

    @PostMapping("/get")
    public Result<GfUserDTO> getGachaWeb(@RequestBody firstRequestDTO request) {
        GfUserDTO result = gachaWebService.getGachaFromWeb(request);
        return Result.success(result);
    }
}
