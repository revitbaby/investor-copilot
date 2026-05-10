# analysis-engine 规范 (Specification)

## Purpose
待定 (TBD) - 由归档变更 create-macro-liquidity-analyst 创建。归档后更新目的。

## Requirements
### Requirement: Net Liquidity Calculation
系统必须 (MUST) 使用标准公式计算净流动性 (Net Liquidity)。

#### Scenario: 计算净流动性
- **当 (WHEN)** 原始央行数据可用时
- **那么 (THEN)** 净流动性计算为 `WALCL - RRPONTSYD - WTREGEN`（以十亿/万亿为单位）

### Requirement: Trend Analysis
系统必须 (MUST) 基于移动平均线 (moving averages) 和变化率 (rate of change) 识别趋势。

#### Scenario: 流动性趋势检测
- **当 (WHEN)** 净流动性低于其 20 日移动平均线时
- **那么 (THEN)** 系统将趋势标记为“收缩 (Contracting)”

### Requirement: Volatility Divergence
系统必须 (MUST) 检测股票波动率 (equity volatility) 和债券波动率 (bond volatility) 之间的背离 (divergence)。

#### Scenario: VIX/MOVE 背离
- **当 (WHEN)** VIX 较低 (<20) 但 MOVE 指数较高 (>120) 时
- **那么 (THEN)** 生成“债券市场压力 (Bond Market Stress)”警告信号

### Requirement: China Macro Analysis
系统必须 (MUST) 计算关键的中国宏观经济信号。

#### Scenario: M1-M2 Gap
- **当 (WHEN)** M1 和 M2 同比 (YoY) 数据可用时
- **那么 (THEN)** 系统计算 `Gap = M1_Growth - M2_Growth`
- **并且 (AND)** 将正差值解释为“活跃流动性 (Active Liquidity)”，负差值解释为“流动性陷阱 (Liquidity Trap)”

### Requirement: China Market Signals
系统必须 (MUST) 基于A股市场活动生成信号。

#### Scenario: Turnover Signal
- **当 (WHEN)** 评估A股每日换手率时
- **那么 (THEN)** 与阈值进行比较（<6000亿：低，>1万亿：活跃，>2万亿：过热）

#### Scenario: Northbound Flow Signal
- **当 (WHEN)** 北向资金流向 (Northbound fund flow) 为正时
- **那么 (THEN)** 发出“外资流入 (Foreign Inflow)”信号

### Requirement: Hong Kong Valuation Analysis
系统必须 (MUST) 分析 AH 股的相对估值 (relative valuation)。

#### Scenario: AH Premium Analysis
- **当 (WHEN)** AH 股溢价指数 (AH Premium Index) > 150 时
- **那么 (THEN)** 发出“H股被低估 (H-Shares Undervalued)”（高溢价）信号
