package org.example.xkl_java.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.xkl_java.bean.GfGachaHistory;
import org.example.xkl_java.bean.GfGachaRankingList;
import org.example.xkl_java.bean.GfGachaSsrRecord;
import org.example.xkl_java.bean.GfSsrItem;
import org.example.xkl_java.bean.GfUser;
import org.example.xkl_java.dto.GfUserDTO;
import org.example.xkl_java.dto.firstRequestDTO;
import org.example.xkl_java.exception.BusinessException;
import org.example.xkl_java.mapper.GfGachaHistoryMapper;
import org.example.xkl_java.mapper.GfGachaRankingListMapper;
import org.example.xkl_java.mapper.GfGachaSsrRecordMapper;
import org.example.xkl_java.mapper.GfSsrItemMapper;
import org.example.xkl_java.mapper.GfUserMapper;
import org.example.xkl_java.vo.GachaItemVO;
import org.example.xkl_java.vo.GachaRecordsVO;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.*;
import reactor.util.retry.Retry;

import java.time.Duration;
import java.util.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * 异步非阻塞 HTTP 服务 - 使用 WebClient 实现真正异步
 */
@Slf4j
@Service
@RequiredArgsConstructor
@Transactional
public class GachaWebService {
    private static final String GACHA_RECORD_URL = "https://gf2-gacha-record.sunborngame.com/list";
    private static final String ACCOUNT_INFO_URL = "https://gf2-zoneinfo.sunborngame.com/account/info";

    private final GfGachaHistoryMapper gfGachaHistoryMapper;
    private final GfGachaRankingListMapper gfGachaRankingListMapper;
    private final GfGachaSsrRecordMapper gfGachaSsrRecordMapper;
    private final GfSsrItemMapper gfSsrItemMapper;
    private final GfUserMapper gfUserMapper;
    private final GfUserService gfUserService;
    private final WebClient webClient;
    private final ObjectMapper objectMapper = new ObjectMapper();

    private static final ParameterizedTypeReference<Map<String, Object>> MAP_TYPE_REF =
            new ParameterizedTypeReference<Map<String, Object>>() {};

    // 五个池子的类型
    private static final List<Integer> POOL_TYPES = Arrays.asList(1, 3, 4, 6, 7);
    // 池子名称映射
    private static final Map<Integer, String> POOL_NAMES = Map.of(
            1, "常驻池", 3, "角色池", 4, "武器池",
            6, "自选角色池", 7, "自选武器池"
    );

    public GfUserDTO getGachaFromWeb(firstRequestDTO request) {
        try {
            // 1. firstJson 已经是 Map 对象，无需解析
            Map<String, Object> firstJsonMap = request.getFirstJson();

            @SuppressWarnings("unchecked")
            Map<String, String> headers = (Map<String, String>) firstJsonMap.get("headers");
            @SuppressWarnings("unchecked")
            Map<String, String> body = (Map<String, String>) firstJsonMap.get("body");
            @SuppressWarnings("unchecked")
            Map<String, String> params = (Map<String, String>) firstJsonMap.get("params");

            String authorization = headers.get("Authorization");

            // 2. 获取用户uid - 异步获取
            Integer uid = getUidFromServerAsync(authorization, headers);
            if (uid == null) {
                throw new BusinessException("获取用户UID失败");
            }
            log.info("获取到用户UID: {}", uid);

            // 3. 获取或创建GfUser（Long类型的userId是数据库主键）
            Long userId = getOrCreateGfUser(uid);

            // 4. 获取SSR物品列表用于匹配
            List<GfSsrItem> ssrItemList = gfSsrItemMapper.getGfSsrItemList();
            // ssrItemMap 以游戏道具ID为key，用于匹配抽卡记录
            Map<Integer, GfSsrItem> ssrItemMap = ssrItemList.stream()
                    .collect(Collectors.toMap(GfSsrItem::getItemId, item -> item, (a, b) -> a));
            // ssrItemMapById 以数据库主键为key，用于查询物品详情
            Map<Long, GfSsrItem> ssrItemMapById = ssrItemList.stream()
                    .collect(Collectors.toMap(GfSsrItem::getId, item -> item, (a, b) -> a));

            // 5. 异步并发获取五个池子的数据（真正非阻塞）
            Map<Integer, List<Map<String, Object>>> allPoolRecords = fetchAllPoolsAsync(
                    headers, params, body, authorization);

            // 6. 获取最新的History并合并数据
            GfGachaHistory latestHistory = gfGachaHistoryMapper.getLatestGfGachaHistoryByUserId(userId);
            Map<Integer, String> mergedPoolJsons = mergePoolData(latestHistory, allPoolRecords);

            // 7. 插入新的History记录
            GfGachaHistory newHistory = new GfGachaHistory();
            newHistory.setUserId(userId);
            newHistory.setPermanentPoolJson(mergedPoolJsons.get(1));
            newHistory.setCharacterPoolJson(mergedPoolJsons.get(3));
            newHistory.setWeaponPoolJson(mergedPoolJsons.get(4));
            newHistory.setCustomCharacterPoolJson(mergedPoolJsons.get(6));
            newHistory.setCustomWeaponPoolJson(mergedPoolJsons.get(7));
            gfGachaHistoryMapper.insertGfGachaHistory(newHistory);
            Long historyId = newHistory.getId();

            // 8. 删除旧的SSR记录并插入新的
            gfGachaSsrRecordMapper.deleteGfGachaSsrRecordByUserId(userId);
            List<GfGachaSsrRecord> ssrRecords = buildSsrRecords(userId, historyId, mergedPoolJsons, ssrItemMap, ssrItemMapById);
            if (!ssrRecords.isEmpty()) {
                gfGachaSsrRecordMapper.insertGfGachaSsrRecordList(ssrRecords);
            }

            // 9. 组装GfUserDTO返回（使用ssrRecords数据，它们已经包含了costDraws和drawOrder）
            List<GachaItemVO> allItems = buildGachaItemsFromRecords(ssrRecords, ssrItemMapById);
            List<GachaRecordsVO> recordsList = gfUserService.buildGachaRecordsList(allItems);
            GfUserDTO result = gfUserService.buildGfUserDTO(String.valueOf(uid), recordsList);

            // 10. 计算欧皇值并更新排行榜
            int luckValue = gfUserService.calculateLuckValue(allItems);
            GfGachaRankingList ranking = new GfGachaRankingList();
            ranking.setUserId(userId);
            ranking.setLuckValue(luckValue);
            ranking.setTotalDraws(result.getTotalDraws());
            // 尝试更新，若影响行数为0则插入
            if (gfGachaRankingListMapper.updateGfGachaRankingListByUserId(ranking) == 0) {
                gfGachaRankingListMapper.insertGfGachaRankingList(ranking);
            }

            return result;

        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("获取抽卡记录失败", e);
            throw new BusinessException("获取抽卡记录失败: " + e.getMessage());
        }
    }

    /**
     * 异步获取用户UID - WebClient 非阻塞
     */
    private Integer getUidFromServerAsync(String authorization, Map<String, String> headers) {
        try {
            Map<String, Object> response = webClient.post()
                    .uri(ACCOUNT_INFO_URL)
                    .contentType(MediaType.APPLICATION_JSON)
                    .header("Authorization", authorization)
                    .header("User-Agent", headers.get("User-Agent"))
                    .header("Accept", "*/*")
                    .header("X-Unity-Version", headers.get("X-Unity-Version"))
                    .bodyValue("{}")
                    .retrieve()
                    .bodyToMono(MAP_TYPE_REF)
                    .retryWhen(Retry.backoff(3, Duration.ofMillis(500))
                            .filter(e -> e instanceof java.net.SocketException
                                    || e instanceof org.springframework.web.reactive.function.client.WebClientRequestException))
                    .block();

            if (response != null && "0".equals(String.valueOf(response.get("code")))) {
                @SuppressWarnings("unchecked")
                Map<String, Object> data = (Map<String, Object>) response.get("data");
                return (Integer) data.get("uid");
            }
        } catch (Exception e) {
            log.error("获取UID失败", e);
        }
        return null;
    }

    /**
     * 获取或创建GfUser
     */
    private Long getOrCreateGfUser(Integer uid) {
        GfUser existingUser = gfUserMapper.getGfUserByUid(uid);
        if (existingUser != null) {
            return existingUser.getId();
        }
        GfUser newUser = new GfUser();
        newUser.setUid(uid);
        newUser.setIsDeleted(0);
        gfUserMapper.insertGfUser(newUser);
        return gfUserMapper.getGfUserByUid(uid).getId();
    }

    /**
     * 异步并发获取所有池子的数据 - 真正非阻塞
     */
    private Map<Integer, List<Map<String, Object>>> fetchAllPoolsAsync(
            Map<String, String> headers, Map<String, String> params,
            Map<String, String> body, String authorization) {

        Map<Integer, List<Map<String, Object>>> result = Collections.synchronizedMap(new HashMap<>());
        CountDownLatch latch = new CountDownLatch(POOL_TYPES.size());

        for (Integer poolType : POOL_TYPES) {
            final Integer type = poolType;

            fetchSinglePoolAsync(headers, params, body, authorization, type)
                    .subscribe(
                            records -> {
                                result.put(type, records);
                                latch.countDown();
                            },
                            error -> {
                                log.error("获取{}数据失败", POOL_NAMES.get(type), error);
                                result.put(type, Collections.emptyList());
                                latch.countDown();
                            }
                    );
        }

        try {
            boolean completed = latch.await(120, TimeUnit.SECONDS);
            if (!completed) {
                log.warn("等待池子数据超时，部分数据可能不完整");
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            log.error("等待池子数据被中断", e);
        }

        if (result.size() != POOL_TYPES.size()) {
            throw new BusinessException("部分池子数据获取失败");
        }
        return result;
    }

    /**
     * 异步获取单个池子的所有数据（分页）
     */
    private Mono<List<Map<String, Object>>> fetchSinglePoolAsync(
            Map<String, String> headers, Map<String, String> params,
            Map<String, String> body, String authorization, Integer poolType) {

        Map<String, String> requestBody = new HashMap<>(body);
        requestBody.put("type_id", String.valueOf(poolType));
        requestBody.remove("next");

        return fetchPageAsync(headers, params, requestBody, authorization, poolType)
                .expand(response -> {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> data = (Map<String, Object>) response.get("data");
                    String next = (String) data.get("next");
                    if (next == null || next.isEmpty()) {
                        return Mono.empty();
                    }
                    Map<String, String> nextBody = new HashMap<>(requestBody);
                    nextBody.put("next", next);
                    return fetchPageAsync(headers, params, nextBody, authorization, poolType);
                })
                .collectList()
                .map(pages -> {
                    List<Map<String, Object>> allRecords = new ArrayList<>();
                    for (Map<String, Object> pageData : pages) {
                        @SuppressWarnings("unchecked")
                        List<Map<String, Object>> list = (List<Map<String, Object>>)
                                ((Map<String, Object>) pageData.get("data")).get("list");
                        if (list != null) {
                            allRecords.addAll(list);
                        }
                    }
                    log.info("{}获取完成，共{}页{}条记录",
                            POOL_NAMES.get(poolType), pages.size(), allRecords.size());
                    return allRecords;
                });
    }

    /**
     * 异步获取单页数据 - WebClient 非阻塞请求
     */
    private Mono<Map<String, Object>> fetchPageAsync(
            Map<String, String> headers, Map<String, String> params,
            Map<String, String> body, String authorization, Integer poolType) {

        MultiValueMap<String, String> formData = new LinkedMultiValueMap<>();
        formData.setAll(body);
        if (params != null) {
            params.forEach(formData::add);
        }

        return webClient.post()
                .uri(GACHA_RECORD_URL)
                .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .header("Authorization", authorization)
                .header("User-Agent", headers.get("User-Agent"))
                .header("Accept", "*/*")
                .header("X-Unity-Version", headers.get("X-Unity-Version"))
                .body(BodyInserters.fromFormData(formData))
                .retrieve()
                .bodyToMono(MAP_TYPE_REF)
                .retryWhen(Retry.backoff(3, Duration.ofMillis(500))
                        .filter(e -> e instanceof java.net.SocketException
                                || e instanceof org.springframework.web.reactive.function.client.WebClientRequestException))
                .doOnSuccess(response -> {
                    if (response != null) {
                        @SuppressWarnings("unchecked")
                        Map<String, Object> data = (Map<String, Object>) response.get("data");
                        if (data != null) {
                            @SuppressWarnings("unchecked")
                            List<Map<String, Object>> list = (List<Map<String, Object>>) data.get("list");
                            log.debug("获取{}成功，当前累计{}条记录",
                                    POOL_NAMES.get(poolType), list != null ? list.size() : 0);
                        }
                    }
                })
                .doOnError(error -> log.error("获取{}失败", POOL_NAMES.get(poolType), error));
    }

    /**
     * 合并池子数据（新数据在上，旧数据在下，去除连续重复记录）
     */
    private Map<Integer, String> mergePoolData(GfGachaHistory latestHistory,
                                                Map<Integer, List<Map<String, Object>>> newPoolRecords) {
        Map<Integer, String> result = new HashMap<>();

        for (Integer poolType : POOL_TYPES) {
            List<Map<String, Object>> newRecords = newPoolRecords.get(poolType);
            List<Map<String, Object>> oldRecords = new ArrayList<>();

            if (latestHistory != null) {
                String oldJson = getPoolJson(latestHistory, poolType);
                if (oldJson != null && !oldJson.isEmpty()) {
                    try {
                        List<Map<String, Object>> oldPageData = objectMapper.readValue(
                                oldJson, new TypeReference<List<Map<String, Object>>>() {});
                        for (Map<String, Object> page : oldPageData) {
                            // data 是对象 { "next": "", "list": [...] }
                            @SuppressWarnings("unchecked")
                            Map<String, Object> data = (Map<String, Object>) page.get("data");
                            if (data != null) {
                                @SuppressWarnings("unchecked")
                                List<Map<String, Object>> list = (List<Map<String, Object>>) data.get("list");
                                if (list != null) {
                                    oldRecords.addAll(list);
                                }
                            }
                        }
                    } catch (Exception e) {
                        log.error("解析旧{}数据失败", POOL_NAMES.get(poolType), e);
                    }
                }
            }

            List<Map<String, Object>> merged = mergeRecords(newRecords, oldRecords);
            List<Map<String, Object>> pages = rebuildPages(merged);

            try {
                result.put(poolType, objectMapper.writeValueAsString(pages));
            } catch (Exception e) {
                log.error("序列化{}数据失败", POOL_NAMES.get(poolType), e);
                result.put(poolType, "[]");
            }
        }
        return result;
    }

    private String getPoolJson(GfGachaHistory history, Integer poolType) {
        return switch (poolType) {
            case 1 -> history.getPermanentPoolJson();
            case 3 -> history.getCharacterPoolJson();
            case 4 -> history.getWeaponPoolJson();
            case 6 -> history.getCustomCharacterPoolJson();
            case 7 -> history.getCustomWeaponPoolJson();
            default -> null;
        };
    }

    /**
     * 基于fakeId去重合并记录（参考 gf2gacha_Matcha 项目 MergeRecord.go）
     *
     * 算法原理:
     * 1. 从API原始记录的 time 字段生成 fakeId = time * 100 + order
     *    (order为同一秒内连抽序号0~9)
     * 2. 将新旧记录按 fakeId 做 set 去重
     * 3. 按 fakeId 降序排列（最新在前）
     *
     * 优势: 不依赖JSON序列化比对, 不要求连续重叠, 数学上保证唯一性
     */
    private List<Map<String, Object>> mergeRecords(List<Map<String, Object>> newRecords,
                                                     List<Map<String, Object>> oldRecords) {
        if (newRecords == null) newRecords = new ArrayList<>();
        if (oldRecords == null) oldRecords = new ArrayList<>();

        // 步骤1: 为每条记录生成 fakeId
        generateFakeId(newRecords);
        generateFakeId(oldRecords);

        // 步骤2: 基于 fakeId 去重合并（新数据优先）
        Set<Long> seenIds = new HashSet<>();
        List<Map<String, Object>> merged = new ArrayList<>();

        // 先遍历新记录
        for (Map<String, Object> record : newRecords) {
            Long fakeId = (Long) record.get("_fake_id");
            if (fakeId != null && !seenIds.contains(fakeId)) {
                seenIds.add(fakeId);
                record.remove("_fake_id");
                merged.add(record);
            }
        }

        // 再遍历旧记录（补充新记录中没有的）
        for (Map<String, Object> record : oldRecords) {
            Long fakeId = (Long) record.get("_fake_id");
            if (fakeId != null && !seenIds.contains(fakeId)) {
                seenIds.add(fakeId);
                record.remove("_fake_id");
                merged.add(record);
            }
        }

        // 步骤3: 按 time 降序排序（最新在前）
        merged.sort((a, b) -> {
            long timeA = a.containsKey("time") ? ((Number) a.get("time")).longValue() : 0L;
            long timeB = b.containsKey("time") ? ((Number) b.get("time")).longValue() : 0L;
            return Long.compare(timeB, timeA); // 降序
        });

        return merged;
    }

    /**
     * 为每条抽卡记录生成唯一fakeId。
     * 算法: fakeId = time * 100 + order
     * 其中order是同一秒(time)内连抽的序号(0~9)。
     *
     * @param records 记录列表（每条记录会被原地添加 _fake_id 字段）
     */
    private void generateFakeId(List<Map<String, Object>> records) {
        if (records == null || records.isEmpty()) return;

        Long preTimestamp = null;
        int order = -1;

        for (Map<String, Object> record : records) {
            Long timestamp = record.containsKey("time")
                    ? ((Number) record.get("time")).longValue() : 0L;

            if (!timestamp.equals(preTimestamp)) {
                // 时间戳变了 → 新的一抽，order重置为0
                order = 0;
            } else {
                // 同一秒内的连抽 → order递增
                order++;
                if (order > 9) {
                    log.warn("存在时间戳相同但超过十连的数据: time={}", timestamp);
                }
            }

            // fakeId = 时间戳 * 100 + 序号（两位数补零）
            long fakeId = timestamp * 100 + order;
            record.put("_fake_id", fakeId);

            preTimestamp = timestamp;
        }
    }

    private List<Map<String, Object>> rebuildPages(List<Map<String, Object>> records) {
        List<Map<String, Object>> pages = new ArrayList<>();

        for (int i = 0; i < records.size(); i += 6) {
            int end = Math.min(i + 6, records.size());
            List<Map<String, Object>> pageList = records.subList(i, end);

            Map<String, Object> page = new HashMap<>();
            page.put("code", 0);
            page.put("message", "OK");
            Map<String, Object> data = new HashMap<>();
            data.put("list", pageList);
            data.put("next", "");
            page.put("data", data);
            pages.add(page);
        }

        return pages;
    }

    private List<GfGachaSsrRecord> buildSsrRecords(Long userId, Long historyId,
                                                   Map<Integer, String> poolJsons,
                                                   Map<Integer, GfSsrItem> ssrItemMap,
                                                   Map<Long, GfSsrItem> ssrItemMapById) {
        List<GfGachaSsrRecord> allRecords = new ArrayList<>();

        for (Integer poolType : POOL_TYPES) {
            String json = poolJsons.get(poolType);
            if (json == null || json.isEmpty()) continue;

            List<Map<String, Object>> records = new ArrayList<>();
            try {
                List<Map<String, Object>> pages = objectMapper.readValue(
                        json, new TypeReference<List<Map<String, Object>>>() {});
                for (Map<String, Object> page : pages) {
                    // data 是对象 { "next": "", "list": [...] }
                    @SuppressWarnings("unchecked")
                    Map<String, Object> data = (Map<String, Object>) page.get("data");
                    if (data != null) {
                        @SuppressWarnings("unchecked")
                        List<Map<String, Object>> list = (List<Map<String, Object>>) data.get("list");
                        if (list != null) {
                            records.addAll(list);
                        }
                    }
                }
            } catch (Exception e) {
                log.error("解析{}数据失败", POOL_NAMES.get(poolType), e);
                continue;
            }

            List<GfGachaSsrRecord> poolSsrRecords = new ArrayList<>();
            int ssrCount = 0;
            int totalDraws = 0;

            for (int i = records.size() - 1; i >= 0; i--) {
                Map<String, Object> record = records.get(i);
                // 原始数据使用 "item" 而不是 "item_id"
                Integer itemId = record.get("item") != null ? ((Number) record.get("item")).intValue() : null;
                // rank(稀有度) 通过 itemId 从 ssrItemMap 获取，如果找不到则不是SSR
                Integer rank = (itemId != null && ssrItemMap.containsKey(itemId)) ? 3 : 1;

                if (rank == 3) {
                    ssrCount++;
                    GfGachaSsrRecord ssrRecord = new GfGachaSsrRecord();
                    ssrRecord.setUserId(userId);
                    ssrRecord.setHistoryId(historyId);
                    ssrRecord.setPoolType(poolType);
                    // 获取 gf_ssr_item 的数据库主键 id
                    GfSsrItem ssrItem = ssrItemMap.get(itemId);
                    ssrRecord.setItemId(ssrItem != null ? ssrItem.getId() : 0L);
                    ssrRecord.setDrawOrder(ssrCount);
                    // 修复：costDraws需要+1来包含五星自身1抽
                    ssrRecord.setCostDraws(totalDraws + 1);
                    poolSsrRecords.add(ssrRecord);
                    totalDraws = 0;
                } else {
                    totalDraws++;
                }
            }

            // question占位符使用最新的drawOrder=0（避免与真实SSR冲突）
            // question的costDraws表示最新SSR之后又抽了多少抽
            if (poolSsrRecords.isEmpty()) {
                // 池子没抽卡或没有SSR
                GfGachaSsrRecord placeholder = new GfGachaSsrRecord();
                placeholder.setUserId(userId);
                placeholder.setHistoryId(historyId);
                placeholder.setPoolType(poolType);
                placeholder.setItemId(0L);
                placeholder.setDrawOrder(0);
                placeholder.setCostDraws(totalDraws); // 0抽或累计抽数
                poolSsrRecords.add(placeholder);
            } else {
                // 保存最新SSR后的垫抽数
                final int drawsAfterLatestSsr = totalDraws;

                // 先反转列表（从旧到新 → 从新到旧），然后插入占位符
                Collections.reverse(poolSsrRecords);

                // 创建占位符：drawOrder=0表示最新SSR之后的状态
                GfGachaSsrRecord placeholder = new GfGachaSsrRecord();
                placeholder.setUserId(userId);
                placeholder.setHistoryId(historyId);
                placeholder.setPoolType(poolType);
                placeholder.setItemId(0L);
                placeholder.setDrawOrder(0);
                // 修复：question的costDraws是最新SSR后的垫抽数
                placeholder.setCostDraws(drawsAfterLatestSsr);
                poolSsrRecords.add(0, placeholder);

                // 真实SSR的drawOrder从1开始编号（占位符已经是0，不需要重新编号）
                int ssrOrder = 1;
                for (GfGachaSsrRecord record : poolSsrRecords) {
                    if (record.getItemId() == null || record.getItemId() != 0L) {
                        record.setDrawOrder(ssrOrder++);
                    }
                }
            }

            allRecords.addAll(poolSsrRecords);
        }

        return allRecords;
    }

    /**
     * 从SSR记录构建GachaItemVO列表（用于返回给前端）
     * ssrRecords 中的 itemId 是 gf_ssr_item.id（数据库主键）
     * ssrItemMapById 以数据库主键为key
     */
    private List<GachaItemVO> buildGachaItemsFromRecords(List<GfGachaSsrRecord> ssrRecords,
                                                           Map<Long, GfSsrItem> ssrItemMapById) {
        List<GachaItemVO> allItems = new ArrayList<>();

        for (GfGachaSsrRecord record : ssrRecords) {
            GachaItemVO vo = new GachaItemVO();
            vo.setPoolType(record.getPoolType());
            vo.setCostDraws(record.getCostDraws());
            vo.setDrawOrder(record.getDrawOrder());

            Long itemId = record.getItemId();
            if (itemId != null && itemId == 0) {
                // itemId=0 表示"question"占位符
                vo.setItemId(0);
                vo.setItemName("question");
                vo.setItemType(0);
                vo.setSsrType(0);
            } else {
                // itemId 是 gf_ssr_item.id（数据库主键），用 ssrItemMapById 查找
                GfSsrItem ssrItem = ssrItemMapById.get(itemId);
                if (ssrItem != null) {
                    vo.setItemId(ssrItem.getItemId()); // 设置为游戏物品ID
                    vo.setItemName(ssrItem.getItemName());
                    vo.setItemType(ssrItem.getItemType());
                    vo.setSsrType(ssrItem.getSsrType());
                } else {
                    vo.setItemId(itemId != null ? itemId.intValue() : 0);
                    vo.setItemName("unknown");
                    vo.setItemType(0);
                    vo.setSsrType(0);
                }
            }

            allItems.add(vo);
        }

        return allItems;
    }
}
