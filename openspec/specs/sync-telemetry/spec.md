# Sync Telemetry Specification

## Purpose
描述 `_record_sync` 同步遥测写入 sync_log.json 的范围、字段与最新一次覆盖语义。
## Requirements

### Requirement: `_record_sync` context manager
`china_market_fetcher.py` SHALL 提供 `_record_sync(filename: str)` context manager。当包裹代码块成功执行完毕时，SHALL 将同步记录写入 `data_cache/sync_log.json`，包含字段：`last_sync_utc`（ISO 8601 UTC 时间）、`duration_s`（浮点，保留两位小数）、`status`（`"success"` 或 `"error"`）、`last_data_date`（从对应 CSV 最后一行 index 读取，格式 `YYYY-MM-DD`）。异常退出时 `status` 为 `"error"` 且 `last_data_date` 为 `null`。

#### Scenario: 成功 fetch 后写入 success 记录
- **WHEN** `with _record_sync("china/margin_ratio.csv"):` 包裹的代码块成功执行
- **THEN** `data_cache/sync_log.json` 中 `"china/margin_ratio.csv"` 键下存在 `status: "success"`，`duration_s` 为实际耗时，`last_sync_utc` 为当前 UTC 时间

#### Scenario: fetch 失败时写入 error 记录并重新抛出异常
- **WHEN** `with _record_sync("china/qvix.csv"):` 包裹的代码块抛出异常
- **THEN** `data_cache/sync_log.json` 中 `"china/qvix.csv"` 键下存在 `status: "error"`，且异常继续向上传播（不被吞掉）

---

### Requirement: 仅 API 调用分支包裹 `_record_sync`
`_record_sync` SHALL 仅包裹 CSV cache miss 后的 API 调用路径（即 `try` 块中的 Tushare/AkShare 调用和 `_save_cache` 调用），不包裹 CSV cache hit 返回路径。

#### Scenario: CSV cache hit 时不写入 sync_log
- **WHEN** `fetch_margin_ratio()` 发现目标日期已在 CSV cache 中，直接返回缓存数据
- **THEN** `data_cache/sync_log.json` 中 `"china/margin_ratio.csv"` 的 `last_sync_utc` 不更新（保持上次 API 调用时的值）

---

### Requirement: DataLoader 方法也纳入同步遥测
`src/data/loader.py` 的 `fetch_all_data()`、`fetch_sector_etf_data()`、`fetch_china_data()` SHALL 在 cache miss（文件不存在或非今日）的 API 调用分支使用 `_record_sync`（从 `china_market_fetcher` 导入或复制工具函数），key 分别为 `"macro_data.csv"`、`"sector_etf_data.csv"`、`"china_data.csv"`。

#### Scenario: 美股数据首次加载写入遥测
- **WHEN** `macro_data.csv` 不存在或非今日，`fetch_all_data()` 调用 FRED+Yahoo API
- **THEN** `sync_log.json` 中 `"macro_data.csv"` 键下存在 `status: "success"` 和有效的 `duration_s`

---

### Requirement: `sync_log.json` 为追加-覆盖（最新一次）模式
每次写入 SHALL 读取现有 JSON、更新对应 key、写回全量 JSON（不是追加行）。每个 key 只保留最近一次同步记录。

#### Scenario: 多次同步后只保留最新记录
- **WHEN** `fetch_margin_ratio()` 今天已被调用两次（两次都发生了 API 调用）
- **THEN** `sync_log.json["china/margin_ratio.csv"]` 中只有最近一次的 `last_sync_utc` 和 `duration_s`
