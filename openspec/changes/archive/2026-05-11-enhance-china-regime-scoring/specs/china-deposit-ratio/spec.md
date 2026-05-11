## ADDED Requirements

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

### Requirement: Monthly-Frequency Chart with Historical Reference Levels

系统 SHALL 以**月频点**（非日频连线）渲染存款市值比时间序列图，并标注历史参考水位：

- 2015 牛市高峰时的低点（存款市值比最低，反映资金大量入市）
- 2018 年底（存款市值比高位，配置价值高位）
- 当前最新月度值（高亮点）

#### Scenario: Monthly dot chart rendered

- **WHEN** 渲染存款市值比图表
- **THEN** 图表使用月度散点（不连日度线），x 轴为月份，y 轴为倍数

#### Scenario: Latest value card shows potential inflow interpretation

- **WHEN** 渲染最新值卡片
- **THEN** 卡片显示"当前 X.X 倍 — 居民资金入市比例：{'高' if ratio > threshold else '低'}"的解释性描述

### Requirement: Deposit Ratio as Long-Cycle Supplementary Signal

存款市值比 SHALL 仅作为辅助性长周期判断信号（P2 优先级），不直接参与 Layer 1/2/3 的评分计算；仅在 Dashboard 展示以辅助用户做长周期判断。

#### Scenario: Deposit ratio not in scoring formula

- **WHEN** 系统计算 Layer 1、Layer 2 评分
- **THEN** 存款市值比不进入评分公式，仅作为展示指标

#### Scenario: Dashboard displays ratio with context

- **WHEN** 用户查看 China 模块
- **THEN** 存款市值比卡片显示当前值、历史参考水位、以及配置潜力的文字解读

