# china-margin-data Specification

## Purpose
TBD - created by syncing change enhance-china-regime-scoring.

## Requirements

### Requirement: Fetch Daily Margin Balance and Market Cap

系统 SHALL 每日从 Tushare Pro 获取沪深两市融资融券余额合计（`pro.margin`）以及 A 股总市值（`pro.daily_basic` 或宏观接口），并计算两融余额市值比（Margin Balance / Market Cap Ratio），单位为百分比。

#### Scenario: Successful daily fetch

- **WHEN** 数据管道在交易日运行
- **THEN** 系统从 Tushare 获取当日融资余额 + 融券余额合计（全市场），并除以当日 A 股总市值
- **AND** 结果以百分比表示，写入 `data_cache/china/margin_ratio.csv`

#### Scenario: Cache hit skips API call

- **WHEN** `data_cache/china/margin_ratio.csv` 中已存在今日条目
- **THEN** 系统直接读取缓存，不调用 Tushare API

#### Scenario: API failure graceful degradation

- **WHEN** Tushare API 调用失败（超时或限额）
- **THEN** 返回最近一个有效值（last-known-good），并向 UI 层传递 `data_stale=True` 标志

### Requirement: Historical Margin Ratio with Bull Market Reference Levels

系统 SHALL 在图表中标注三个历史参考水位：
- 2015 牛市高点（约 3.3%）
- 2021 牛市高点（约 2.8%，需从历史数据实际计算）
- 当前最新值（高亮点）

#### Scenario: Reference levels rendered

- **WHEN** 系统渲染两融余额市值比折线图
- **THEN** 图表上叠加三条虚线参考水位，并附文字标注（"2015高点"、"2021高点"、"当前"）

#### Scenario: Latest value card shows distance description

- **WHEN** 渲染最新值卡片
- **THEN** 卡片显示"最新值 X.XX% — 距2015高点 Y.YY个百分点（很远 / 较远 / 较近 / 接近）"的文字描述

### Requirement: Margin Ratio Sentinel Threshold Classification

系统 SHALL 将最新两融余额市值比分类为三档：`OVERHEATED`（> 2.5%）、`NORMAL`（1.5%–2.5%）、`COLD`（< 1.5%），供 Layer 2 体制评分使用。

#### Scenario: Overheated classification

- **WHEN** 最新两融余额市值比 > 2.5%
- **THEN** 分类输出为 `OVERHEATED`，Layer 2 该维度得分为 -1（过热）

#### Scenario: Cold classification

- **WHEN** 最新两融余额市值比 < 1.5%
- **THEN** 分类输出为 `COLD`，Layer 2 该维度得分为 -1（冷淡/低迷）

#### Scenario: Normal classification

- **WHEN** 最新两融余额市值比在 1.5%–2.5% 范围内
- **THEN** 分类输出为 `NORMAL`，Layer 2 该维度得分为 +1（正常杠杆）
