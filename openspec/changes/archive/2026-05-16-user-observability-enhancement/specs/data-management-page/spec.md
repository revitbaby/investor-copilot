## ADDED Requirements

### Requirement: 数据管理页面展示缓存状态表格
Data Management 页面（`pages/4_Data_Management.py`）SHALL 渲染一个表格，涵盖 A 股细粒度缓存（13 个 CSV 文件）和美股粗粒度缓存（3 个 CSV 文件），每行包含：数据集名称（中文友好名）、最后同步时间、数据截至日期、同步耗时（秒）、状态图标。

A 股细粒度文件列表：`margin_ratio`、`csi300_pe`、`cgb10y_yield`、`equity_bond_spread`、`index_hs300_daily`、`index_gem_daily`、`limit_counts`、`m2_monthly`、`northbound_flow`、`southbound_flow`、`qvix`、`total_amount`、`total_mv_daily`。

美股粗粒度文件：`macro_data`、`sector_etf_data`、`china_data`（注：china_data 属于 DataLoader 的 China 路径，用于图表，区别于 A 股细粒度）。

#### Scenario: 页面加载时读取 sync_log.json 渲染表格
- **WHEN** 用户导航到数据管理页面
- **THEN** 页面从 `data_cache/sync_log.json` 读取遥测数据，结合各 CSV 文件的 OS mtime 和行数，渲染完整状态表格

#### Scenario: sync_log.json 不存在时显示降级信息
- **WHEN** `data_cache/sync_log.json` 文件不存在（应用首次运行，尚未发生任何 API 同步）
- **THEN** 表格仍然渲染，"最后同步时间"和"同步耗时"列显示"—"，状态列显示"⬜ 未知"

---

### Requirement: 状态分类逻辑
状态 SHALL 按以下规则确定（优先级从高到低）：

- `❌ 错误`：`sync_log` 中 `status = "error"`，无论同步时间
- `✅ 新鲜`：`sync_log` 中 `status = "success"` 且 `last_sync_utc` 为今日（UTC 日期）
- `⚠️ 月频`：数据本身是月频发布（M2、deposit_ratio）且 `last_data_date` 不超过 45 天前，视为正常
- `🔶 延迟`：非月频数据，`last_data_date` 早于昨天（存在数据滞后）
- `⬜ 未知`：`sync_log` 中无该文件记录

#### Scenario: 今天成功同步的文件显示 ✅ 新鲜
- **WHEN** `sync_log["china/margin_ratio.csv"].status = "success"` 且 `last_sync_utc` 为今日
- **THEN** 该行状态列显示"✅ 新鲜"

#### Scenario: QVIX 延迟 3 天时显示 🔶 延迟
- **WHEN** `sync_log["china/qvix.csv"].last_data_date` 为 3 天前（AkShare 延迟正常现象）
- **THEN** 该行状态列显示"🔶 延迟"

#### Scenario: M2 月度数据未超期时显示 ⚠️ 月频
- **WHEN** `sync_log["china/m2_monthly.csv"].last_data_date` 在 45 天以内
- **THEN** 该行状态列显示"⚠️ 月频"

---

### Requirement: 手动刷新操作
页面 SHALL 提供两个操作按钮：

1. **「🔄 刷新全部」**：调用 `st.cache_data.clear()`，并删除所有今日的 A 股细粒度 CSV 缓存文件（仅删除今天 mtime 的文件），然后 `st.rerun()`
2. **「🗑 清除今日缓存」**：仅删除今天 mtime 的 A 股细粒度 CSV 文件（保留历史数据），不清除 `@st.cache_data` 内存缓存，然后 `st.rerun()`

操作执行前 SHALL 显示确认对话框（`st.dialog` 或 `st.warning` + 确认 checkbox）。

#### Scenario: 刷新全部后下次访问中国页面重新拉取数据
- **WHEN** 用户点击"🔄 刷新全部"并确认
- **THEN** `@st.cache_data` 内存缓存清空，今日 A 股细粒度 CSV 被删除；用户导航到中国/港股页面后触发完整数据重新拉取（session cache miss 条件成立）

#### Scenario: 清除今日缓存保留历史数据
- **WHEN** 用户点击"🗑 清除今日缓存"并确认
- **THEN** 仅今日 mtime 的文件被删除，历史行数据（2015-present）保留在 CSV 文件中

---

### Requirement: 表格展示耗时超过 30 秒时加注释
若 `sync_log` 中某条记录的 `duration_s > 30`（通常是首次 backfill 触发），该行耗时列 SHALL 在数字后附加"（含历史补全）"标注，提示用户这是正常的一次性操作。

#### Scenario: backfill 耗时在表格中有说明
- **WHEN** `sync_log["china/margin_ratio.csv"].duration_s = 93.4`（首次包含 total_mv backfill）
- **THEN** 该行耗时列显示"93.4s（含历史补全）"
