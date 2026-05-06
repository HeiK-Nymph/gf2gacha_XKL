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
        return Result.fail(e.getCode(), e.getMessage());
    }

    @ExceptionHandler(DataAccessException.class)
    public Result<?> handleDataAccessException(DataAccessException e){
        log.error("数据库操作失败", e);
        return Result.fail("系统繁忙，请稍后再试");
    }

    @ExceptionHandler(Exception.class)
    public Result<?> handleException(Exception e){
        log.error("系统异常", e);
        return Result.fail("系统内部错误");
    }

}
