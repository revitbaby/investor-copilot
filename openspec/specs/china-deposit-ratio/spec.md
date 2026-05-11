# china-deposit-ratio Specification

## Purpose
描述存款市值比（M2 ÷ A 股总市值）的月频数据获取、历史 backfill、图表锚点，以及其作为长周期辅助信号（不参与评分公式）的定位。

## Requirements

### Requirement: Compute Monthly Deposit / Market Cap Ratio

系统 SHALL 每月（月度数据到达后）计算存款市值比 = M2 广义货币存量 ÷ A 股总市值，单位为"倍"，存入 `data_cache/china/deposit_ratio.csv`。

数据来源：

- M2：Tushare 宏观接口 `pro.cn_m`（月度，约月末后 15 日发布）
- A 股总市值：月末最后交易日的 `pro.daily_basic` 汇总或 `pro.index_dailybasic`

#### Scenario: Monthly fetch on new data availability

- **WHEN** 最新月度 M2 数据发布且缓存中尚无该月条目
- **THEN** 系统计算该月存款市值比并追加到 `deposit_ratio.csv`

#### Scenario: No new data — reuse last value

- **WHEN** 本月 M2 数据尚未发布（月中运行）
- **THEN** 返回上月值，并在 UI 标注数据截止月份（如"至 2026-04"）

#### Scenario: Cache hit skips fetch

- **WHEN** 最新月份条目已存在于缓存
- **THEN** 直接读取，不调用 Tushare

### Requirement: Historical Backfill from 2015

系统 SHALL 在首次加载时自动 backfill 2015-01-01 至今的存款市值比历史数据。

Backfill 无需额外 API 调用：M2 来自已有缓存 `m2_monthly.csv`（覆盖 1990 年至今），总市值来自共享缓存 `total_mv_daily.csv`（月末值）。两者取月末值 inner join 后计算比率。

#### Scenario: Backfill on empty cache

- **WHEN** 缓存为空或最早日期晚于 2015-01-01
- **THEN** 系统自动执行 backfill，写入 2015-01-31（首个月末）至今的月频数据，约 136+ 行

### Requirement: Monthly-Frequency Chart with Bull Market Reference Anchors

系统 SHALL 以**月频散点**（非日频连线）渲染存款市值比时间序列图，并以**空心圆圈标记**（`circle-open`）标注以下历史牛市锚点，替代原水平虚线：

| 锚点名称 | 日期 | 参考值 |
|---------|------|--------|
| 2008年牛市 | 2008-01-10 | 0.44x |
| 2015年牛市 | 2015-06-15 | 0.68x |
| 2021年牛市 | 2021-01-21 | 1.07x |

注：上述锚点值来自设计参考文档，M2/总市值的实际量级取决于定义口径。若实测值与锚点量级不符，应以实测数据为准并更新锚点。

#### Scenario: Monthly dot chart rendered

- **WHEN** 渲染存款市值比图表
- **THEN** 图表使用月度散点（不连日度线），x 轴为月份，y 轴为倍数

#### Scenario: Anchor markers rendered

- **WHEN** 系统渲染存款市值比图表
- **THEN** 图表在对应日期位置显示空心圆圈 + 标注文字
- **AND** 若锚点日期不在当前时间范围（如选择 1Y 视图），则自动跳过

#### Scenario: Distance cards show latest vs anchors

- **WHEN** 渲染最新值区域
- **THEN** 渲染 N+1 列卡片（N = 时间范围内可见的锚点数量，最后一列为最新值）

#### Scenario: Latest value card shows potential inflow interpretation

- **WHEN** 渲染最新值卡片
- **THEN** 卡片显示当前值，并附配置潜力的文字解读

### Requirement: Deposit Ratio as Long-Cycle Supplementary Signal

存款市值比 SHALL 仅作为辅助性长周期判断信号（P2 优先级），不直接参与 Layer 1/2/3 的评分计算；仅在 Dashboard 展示以辅助用户做长周期判断。

#### Scenario: Deposit ratio not in scoring formula

- **WHEN** 系统计算 Layer 1、Layer 2 评分
- **THEN** 存款市值比不进入评分公式，仅作为展示指标

#### Scenario: Dashboard displays ratio with context

- **WHEN** 用户查看 China 模块
- **THEN** 存款市值比卡片显示当前值、历史参考水位、以及配置潜力的文字解读
