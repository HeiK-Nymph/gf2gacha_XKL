package org.example.xkl_java.common;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 通用返回对象
 */


@Data
@AllArgsConstructor
@NoArgsConstructor
public class Result<T> {
    private Integer code;
    private String msg;
    private T data;

    //成功，不带数据
    public static <T> Result<T> success(){
        return new Result<>(200, "success", null);
    }

    //成功，带数据
    public static <T> Result<T> success(T data){
        return new Result<>(200, "success", data);
    }

    //成功，带数据和消息
    public static <T> Result<T> success(String msg, T data){
        return new Result<>(200, msg, data);
    }

    //成功，带信息不带数据
    public static <T> Result<T> successMsg(String msg){
        return new Result<>(200, msg, null);
    }

    //失败，不自定义错误码
    public static <T> Result<T> fail(String msg){
        return new Result<>(400, msg, null);
    }

    //失败，自定义错误码
    public static <T> Result<T> fail(Integer code, String msg){
        return new Result<>(code, msg, null);
    }
}
