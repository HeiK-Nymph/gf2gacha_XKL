package org.example.xkl_java.controller;

import lombok.RequiredArgsConstructor;
import org.example.xkl_java.common.Result;
import org.example.xkl_java.dto.GfUserDTO;
import org.example.xkl_java.service.GfUserService;
import org.springframework.web.bind.annotation.*;



@RestController
@RequestMapping("/api/gf-user")
@RequiredArgsConstructor
public class GfUserController {

    private final GfUserService gfUserService;

    @GetMapping("/get")
    public Result<GfUserDTO> getGfUserInfoByUid(@RequestParam Integer uid) {
        GfUserDTO gfUserDTO = gfUserService.getGachaInfoByUid(uid);
        return Result.success(gfUserDTO);
    }
}
