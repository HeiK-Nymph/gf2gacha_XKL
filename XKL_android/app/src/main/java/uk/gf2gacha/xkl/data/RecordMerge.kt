package uk.gf2gacha.xkl.data

/**
 * 抽卡记录合并 —— 与 PC 版（`main.py::_merge_pool_data`）同一套算法，
 * 最早来自 gf2gacha_Matcha 的 MergeRecord.go。
 *
 * 为什么必须合并、不能每次覆盖：
 * 官方记录接口只保留一段时间的记录，窗口一往前滑，旧记录就再也拉不回来了。
 * PC 版的做法是每次刷新都「新拉到的 + 本地已有的」按 fakeId 去重合并，历史只增不减。
 *
 * fakeId = time * 100 + 同一秒内的序号(0~9)：
 * 同一条记录无论取多少次、从哪个池子取，算出来的 fakeId 都不变，
 * 所以不依赖 JSON 字段比对，也不要求新旧两份数据有重叠区。
 */
object RecordMerge {

    /**
     * 按**原始顺序**给每条记录算 fakeId。
     *
     * 注意：必须传接口返回的顺序（或本地文件里存着的顺序），同一秒内的序号才对得上。
     * 本地文件里的顺序也是这套算法合并后写进去的，两边自然一致。
     */
    fun fakeIds(records: List<GachaRecord>): LongArray {
        val ids = LongArray(records.size)
        var prevTime = Long.MIN_VALUE
        var order = -1
        for (i in records.indices) {
            val time = records[i].time
            if (time != prevTime) {
                order = 0            // 换了时间戳 → 新的一抽
            } else {
                order++              // 同一秒内的连抽（官方理论上不会超过 10 抽）
            }
            ids[i] = time * 100 + order
            prevTime = time
        }
        return ids
    }

    /**
     * 合并（与 PC 版逐步对齐）：先遍历新记录，再遍历旧记录补新里没有的，
     * 最后按 time 降序 —— 稳定排序，同一秒内保持「新记录在前」。
     */
    fun merge(newRecords: List<GachaRecord>, oldRecords: List<GachaRecord>): List<GachaRecord> {
        if (oldRecords.isEmpty()) return newRecords.sortedByDescending { it.time }
        if (newRecords.isEmpty()) return oldRecords

        val seen = HashSet<Long>((newRecords.size + oldRecords.size) * 2)
        val merged = ArrayList<GachaRecord>(newRecords.size + oldRecords.size)

        val newIds = fakeIds(newRecords)
        for (i in newRecords.indices) {
            if (seen.add(newIds[i])) merged.add(newRecords[i])
        }
        val oldIds = fakeIds(oldRecords)
        for (i in oldRecords.indices) {
            if (seen.add(oldIds[i])) merged.add(oldRecords[i])
        }
        return merged.sortedByDescending { it.time }
    }
}
