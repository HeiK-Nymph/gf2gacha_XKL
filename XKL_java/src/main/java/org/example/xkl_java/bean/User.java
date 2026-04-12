package org.example.xkl_java.bean;

import lombok.Data;

import java.io.Serializable;

@Data
public class User implements Serializable {
    private Integer id;
    private String uid;
    private String userName;
    private Integer cnt;
}
