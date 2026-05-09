package org.example.xkl_java.exception;

import lombok.extern.slf4j.Slf4j;
import org.example.xkl_java.common.Result;
import org.springframework.dao.DataAccessException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    //处理业务异常
    @ExceptionHandler(BusinessException.class)
    public Result<?> handleBusinessException(BusinessException e){
        log.warn("业务异常: {}", e.getMessage());
        return Result.fail(e.getCode(), e.getMessage());
    }

    //处理认证/授权相关异常
    @ExceptionHandler({io.jsonwebtoken.JwtException.class, io.jsonwebtoken.security.SignatureException.class})
    public Result<?> handleJwtException(Exception e){
        log.warn("JWT 异常: {}", e.getMessage());
        return Result.fail(401, "Token 非法或已失效，请重新登录");
    }

    @ExceptionHandler(org.springframework.web.servlet.resource.NoResourceFoundException.class)
    public Result<?> handleNoResourceFound(Exception e){
        log.warn("资源不存在: {}", e.getMessage());
        return Result.fail(404, "请求的资源不存在");
    }

    @ExceptionHandler(DataAccessException.class)
    public Result<?> handleDataAccessException(DataAccessException e){
        log.error("数据库操作失败", e);
        return Result.fail("系统繁忙，请稍后再试");
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public Result<?> handleIllegalArgument(IllegalArgumentException e){
        log.warn("参数错误: {}", e.getMessage());
        return Result.fail(400, e.getMessage());
    }

    @ExceptionHandler(Exception.class)
    public Result<?> handleException(Exception e){
        log.error("系统异常", e);
        return Result.fail("系统内部错误");
    }

}
