# dashboard 规范 (Specification)

## Purpose
待定 (TBD) - 由归档变更 create-macro-liquidity-analyst 创建。归档后更新目的。
## Requirements
### Requirement: Interactive Visualization
仪表板 (dashboard) 必须 (MUST) 将净流动性 (Net Liquidity) 与标普500 (S&P 500) 进行可视化对比。

#### Scenario: Liquidity Correlation Chart
- **当 (WHEN)** 用户查看主仪表板时
- **那么 (THEN)** 双轴折线图 (dual-axis line chart) 在选定的时间范围内显示净流动性（左轴）和 SPY 价格（右轴）

### Requirement: AI Report Display
dashboard MUST 以用户所选语言展示生成的 AI 分析；当可用时，Executive Summary 与 Investment Playbook 内容来自 regime-aware LLM narrative；当 regime narrative 生成失败时，回退到 legacy LLM 输出。

#### Scenario: View Analyst Report
- **WHEN** 分析完成且 regime narrative 生成成功
- **THEN** Executive Summary 内容来自 regime-aware narrative
- **AND** Investment Playbook 内容来自 regime-aware narrative
- **AND** Liquidity Analysis 与 Risk Signals 区块仍来自现有 LLM 输出

#### Scenario: Regime narrative fallback
- **WHEN** regime narrative 生成失败
- **THEN** Executive Summary 与 Investment Playbook 回退到现有 LLM 输出
- **AND** scoring tables、gauge 与 sentinel row 仍正常渲染（它们是 rule-based）

### Requirement: Language Selection
仪表板必须 (MUST) 提供一种机制，让用户选择其首选的界面语言。

#### Scenario: Switch Language
- **当 (WHEN)** 用户从语言选择器中选择“中文”时
- **那么 (THEN)** 所有静态 UI 文本立即更新为中文
- **并且 (AND)** 该选择在会话 (session) 期间保持不变

### Requirement: Report History
仪表板必须 (MUST) 允许用户查看以前生成的分析报告。

#### Scenario: View Past Report
- **当 (WHEN)** 用户从报告历史选择器中选择过去的日期时
- **那么 (THEN)** 系统加载并显示该日期和当前语言的缓存报告
- **并且 (AND)** 隐藏“生成 (Generate)”按钮

### Requirement: Report Persistence
仪表板必须 (MUST) 缓存生成的报告以防止多余的 API 调用。

#### Scenario: Load Cached Report
- **当 (WHEN)** 仪表板加载时
- **如果 (IF)** 存在当前日期和语言的报告
- **那么 (THEN)** 它会自动显示
- **并且 (AND)** 提供“重新生成 (Regenerate)”按钮

### Requirement: Central Bank Visualization
仪表板必须 (MUST) 显示美联储资产负债表 (Federal Reserve's balance sheet) 和政策利率 (policy rates) 的详细指标。

#### Scenario: 查看美联储资产负债表组成部分
- **当 (WHEN)** 用户滚动到详细指标部分时
- **那么 (THEN)** 图表显示总资产 (WALCL)、逆回购 (RRP) 和财政部一般账户 (TGA) 的趋势
- **并且 (AND)** 单独的图表显示隔夜融资利率 (SOFR)

### Requirement: Market Health Visualization
仪表板必须 (MUST) 可视化市场风险和活动指标。

#### Scenario: View Market Internals
- **当 (WHEN)** 用户查看市场侧图表时
- **那么 (THEN)** 它显示 SPY 交易量、波动率指数 (VIX, MOVE) 和高收益债券 ETF (HYG, JNK)

### Requirement: Cross-Asset Visualization
仪表板必须 (MUST) 显示关键的跨资产相关性 (cross-asset correlations)。

#### Scenario: View Asset Classes
- **当 (WHEN)** 用户查看跨资产图表时
- **那么 (THEN)** 它显示美元指数 (DXY)、黄金、WTI 原油、比特币 (BTC) 和美国 10 年期国债收益率 (US 10Y Treasury Yields) 的表现

### Requirement: Dashboard Layout
详细图表必须 (MUST) 以 2x2 网格布局排列。

#### Scenario: 2x2 网格布局
- **当 (WHEN)** 仪表板渲染详细图表时
- **那么 (THEN)** 它们排列成两行两列
- **并且 (AND)** 图表的尺寸小于主净流动性图表

### Requirement: China/HK Dashboard Tab
仪表板必须 (MUST) 为中国和香港流动性分析提供专用的选项卡。

#### Scenario: 导航到中国仪表板
- **当 (WHEN)** 用户选择“🇨🇳 中国/香港流动性 (China/HK Liquidity)”选项卡时
- **那么 (THEN)** 视图切换以显示特定于中国/香港的图表和指标

### Requirement: China Liquidity Visualization
仪表板必须 (MUST) 可视化三层流动性框架（宏观、中观、微观 / Macro, Meso, Micro）。

#### Scenario: View China Macro Charts
- **当 (WHEN)** 用户查看中国仪表板时
- **那么 (THEN)** 图表显示 DR007 与 OMO 利率、M1-M2 剪刀差和社会融资

#### Scenario: View China Market Charts
- **当 (WHEN)** 用户查看中国仪表板时
- **那么 (THEN)** 图表显示 A 股换手率、北向资金流向和融资融券余额

### Requirement: HK Liquidity Visualization
仪表板必须 (MUST) 可视化香港特定的流动性驱动因素。

#### Scenario: View HK Charts
- **当 (WHEN)** 用户查看香港部分时
- **那么 (THEN)** 图表显示 AH 股溢价指数、南向资金流向和 USD/CNH 与 HSI 的对比

### Requirement: L3 Alert Banner
当任意 L3 sentinel 处于 TRIGGERED 或 COOLING 状态时，dashboard SHALL 在页面顶部显示全宽 sticky 红色告警横幅。横幅 SHALL 展示 sentinel 名称、forced ceiling、触发时间与重置进度。若有多个 sentinel 触发，应按严重程度排序展示（forced_ceiling 越低越靠前）。当全部 sentinel 为 CLEAR 时，横幅 SHALL NOT 渲染。

#### Scenario: Single sentinel triggered
- **WHEN** L3 的 VIX Spike sentinel 处于 TRIGGERED
- **THEN** 页面顶部出现红色 sticky 横幅，显示 "⚡ LAYER 3 ALERT: VIX Spike TRIGGERED"、20% forced ceiling、触发时间戳和重置进度

#### Scenario: All sentinels clear
- **WHEN** 所有 L3 sentinels 均为 CLEAR
- **THEN** 告警横幅不渲染

### Requirement: Regime Gauge Hero Component
dashboard SHALL 以横向 gauge（0%-100%）作为主 hero 组件，并以高亮色带显示 Target Position Envelope。色带颜色随 target_max 变化：>70% 为绿色、50-70% 为黄色、30-50% 为橙色、<30% 为红色。emergency mode 下色带为红色。

#### Scenario: Normal mode gauge
- **WHEN** L1=CONTRACTING（60%）、L2=RISK_ON（70%-85%）、L3=all CLEAR
- **THEN** gauge 显示 42% 到 51% 的高亮区间，并在下方展示推导公式

#### Scenario: Current position marker shown after upload
- **WHEN** 用户已上传 portfolio 且当前 exposure 为 70%
- **THEN** gauge 在 70% 位置显示三角标记 ▼，并附带红色标签 "⚠️ Overweight X pp"

#### Scenario: No portfolio marker without upload
- **WHEN** 未上传 portfolio
- **THEN** gauge 仅显示 target envelope 色带，不显示当前仓位标记

#### Scenario: Emergency mode gauge
- **WHEN** 某个 L3 sentinel 触发且 forced_ceiling 为 20%
- **THEN** gauge 显示 0% 到 20% 的红色色带，推导文本显示 "🚨 L3 Emergency Override"

### Requirement: L1 Scoring Table
dashboard SHALL 显示 Layer 1 卡片，标题为 "LAYER 1: Liquidity Foundation"，包含 regime badge（按 regime 名称与 ceiling 进行颜色编码）、指标表（指标名称、当前值、阈值命中、得分 +1/0/-1 且带色块）、带 regime 背景色的 composite 汇总行，以及下方灰色斜体的 LLM 1-2 句摘要。

#### Scenario: Render L1 scoring table
- **WHEN** L1 scoring 完成
- **THEN** 渲染一个恰好包含 4 行指标的表格
- **AND** composite 分数行使用对应 regime 颜色作为背景
- **AND** badge 显示 regime 名称与 ceiling 百分比

### Requirement: L2 Scoring Table
dashboard SHALL 显示 Layer 2 卡片，标题为 "LAYER 2: Market Regime"，包含 regime badge，以及带以下列的表格：indicator name、current value、threshold hit、score、weight、weighted score。在 composite 行下方，Score Bar 微可视化 SHALL 在 -8.0 到 +8.0 刻度上显示当前分值位置，并标注 regime 分界线。

#### Scenario: Render L2 scoring table with score bar
- **WHEN** L2 scoring 完成且 weighted composite 为 3.5
- **THEN** 渲染一个恰好包含 8 行指标的表格
- **AND** Score Bar 在 3.5 位置显示 ▲，并在 ±2.0 和 ±5.0 边界处显示竖线

### Requirement: L1 and L2 Two-Column Layout
L1 与 L2 scoring table SHALL 以双列布局排列（L1 在左、L2 在右），位于 Regime Gauge 下方。

#### Scenario: Two-column scoring layout
- **WHEN** dashboard 渲染 scoring 区域
- **THEN** L1 Scoring Table 占左半区，L2 Scoring Table 占右半区

### Requirement: L3 Sentinel Row
dashboard SHALL 以紧凑单行形式并排展示 4 个 sentinel。每个 sentinel 渲染为小区块：CLEAR = 绿色 + ✅ + 数值，TRIGGERED = 红色 + 🚨 + 数值，COOLING = 黄色 + ⏳ + "resetting (N days)" + 数值。仅当 sentinel 被触发时，才在下方显示 LLM 的 L3 摘要。

#### Scenario: All sentinels clear
- **WHEN** 4 个 sentinel 全部为 CLEAR
- **THEN** 单行显示 4 个带 ✅ 的绿色区块
- **AND** 不显示 L3 摘要文本

#### Scenario: One sentinel triggered
- **WHEN** VIX Spike 为 TRIGGERED，其他均为 CLEAR
- **THEN** VIX Spike 显示红色 🚨 区块，其余显示绿色 ✅ 区块
- **AND** 标题显示 "LAYER 3: Sentinels — 1 Triggered 🚨"

### Requirement: Position Advisory Card
dashboard SHALL 显示 Position Advisory 卡片：未加载 portfolio 时显示 CSV 上传提示，上传后显示完整建议内容。建议内容包括：exposure 摘要（当前 %、目标区间、overweight/underweight 状态、调整金额）、优先级持仓表（priority、ticker、conviction、current %、target %、action、adjustment $、reason）并按 action 上色（CLOSE=红、TRIM=橙、HOLD=灰、ADD=绿）、当前生效的 regime 规则列表，以及 LLM position narrative。

#### Scenario: No portfolio uploaded
- **WHEN** 用户尚未上传 portfolio CSV
- **THEN** 卡片显示占位文案 "Upload portfolio CSV for personalized advice" 与上传按钮

#### Scenario: Portfolio uploaded and overweight
- **WHEN** 用户上传有效 portfolio 且当前 exposure 超过 Target Max
- **THEN** 建议结果显示 is_overweight = true、excess dollars，以及按优先级排序的 trim/close 表格

### Requirement: Regime Timeline
dashboard SHALL 显示一个 12 个月堆叠 timeline 图，共 4 行共享同一时间轴：L1 Regime（色带）、L2 Regime（色带）、L3 Events（⚡ 标记）和 Target Envelope（0-100% 阴影区域）。同时叠加一条半透明 SPX 价格线，使用右侧 y 轴。

#### Scenario: First deployment with no history
- **WHEN** 不存在 regime history 数据
- **THEN** timeline 显示占位提示 "Regime scoring history will begin accumulating from today"

#### Scenario: Timeline with accumulated data
- **WHEN** 已存在 30+ 天的 regime history
- **THEN** timeline 渲染色带、事件标记，以及带 SPX 叠加的 envelope 面积图

### Requirement: New Components Layout Order
所有新增 regime scoring 组件 SHALL 按以下顺序插入 dashboard 页面顶部、位于现有内容之上：L3 Alert Banner（条件渲染）、Regime Gauge、L1+L2 Scoring Tables（双列）、L3 Sentinel Row、Position Advisory、Regime Timeline。

#### Scenario: Component rendering order
- **WHEN** dashboard 渲染
- **THEN** regime 组件显示在现有 charts 与 LLM analysis 区块上方
- **AND** 下方原有图表与区块保持不变

