package org.example.xkl_java.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;
import org.example.xkl_java.bean.GfSsrItem;

import java.util.List;

@Data
public class GfSsrItemBatchDTO {
    @JsonProperty("GfSsrItemList")
    private List<GfSsrItem> GfSsrItemList;
}
