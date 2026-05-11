# china-margin-data Specification

## Purpose
描述两融余额市值比（Margin Balance / Market Cap Ratio）的数据获取、历史 backfill、图表锚点与体制评分分类逻辑。

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

### Requirement: Historical Backfill from 2015

系统 SHALL 在首次加载时自动 backfill 2015-01-01 至今的两融余额市值比历史数据，无需手动操作。

Backfill 实现约束（见 data-ingestion spec 中"API Row-Count and Date-Range Constraints"）：
- `pro.margin` 必须按年分批查询（每年约 488 行），禁止单次覆盖多年
- A 股总市值来自共享缓存 `total_mv_daily.csv`（月末单日查询，无行数截断问题）

#### Scenario: Backfill on empty cache

- **WHEN** 缓存为空或最早日期晚于 2015-01-01
- **THEN** 系统自动执行 backfill，写入 2015-01-30（首个月末交易日）至今的月频数据，约 136+ 行

#### Scenario: 2015 bull peak verifiable

- **WHEN** backfill 完成后检查 2015-06-30 附近数据
- **THEN** 该月两融余额市值比应在 3.3%–3.6% 范围内（历史实测值）

### Requirement: Bull Market Reference Anchors

系统 SHALL 在图表中以**空心圆圈标记**（`circle-open`）标注以下历史牛市峰值锚点，替代原水平虚线：

| 锚点名称 | 日期 | 参考值 |
|---------|------|--------|
| 2015年牛市 | 2015-06-30 | 3.33% |
| 2021年牛市 | 2021-03-09 | 1.98% |

#### Scenario: Anchor markers rendered

- **WHEN** 系统渲染两融余额市值比折线图
- **THEN** 图表在对应日期位置显示空心圆圈 + 标注文字（"2015年牛市 3.33%"、"2021年牛市 1.98%"）
- **AND** 若锚点日期不在当前时间范围（如选择 1Y 视图时 2015 锚点不可见），则自动跳过，不报错

#### Scenario: Distance cards show latest vs anchors

- **WHEN** 渲染最新值区域
- **THEN** 渲染 N+1 列卡片（N = 锚点数量，最后一列为最新值），每个锚点卡片显示锚点名称、参考值、当前与锚点的距离描述（很远/较远/较近/接近）或"超 X.XX%"（若已超过锚点值）

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
