# dashboard 规范 (Specification)

## Purpose
描述 Streamlit Dashboard 的布局、交互控件和各 UI 组件的渲染要求，涵盖 Global/US Tab 和 China/HK Tab。
## Requirements
### Requirement: Interactive Visualization
仪表板 (dashboard) 必须 (MUST) 将净流动性 (Net Liquidity) 与标普500 (S&P 500) 进行可视化对比。

#### Scenario: Liquidity Correlation Chart
- **当 (WHEN)** 用户查看主仪表板时
- **那么 (THEN)** 双轴折线图 (dual-axis line chart) 在选定的时间范围内显示净流动性（左轴）和 SPY 价格（右轴）

### Requirement: AI Report Display
当 A 股体制评分可用时，系统 SHALL 将 `ChinaRegimeResult` 注入到 LLM Agent 的中国宏观分析 prompt 中（此部分为准备工作，LLM 叙事生成本身在本 change 范围外）。Dashboard SHALL 保留现有 AI Report 区块不变。

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

#### Scenario: Regime data available for future LLM injection
- **WHEN** China 体制评分计算完成
- **THEN** `ChinaRegimeResult` 对象在 session_state 中可访问，供后续 LLM 集成使用

#### Scenario: Existing AI Report fallback unchanged
- **WHEN** 本次变更部署后
- **THEN** 现有 AI 报告生成逻辑保持不变，不因本次 change 而退化

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

### Requirement: China Three-Indicator Chart Cards
系统 SHALL 在 China 模块顶部渲染三个指标卡片，每个包含折线图（或月频散点图）+ 历史牛市锚点圆圈标记 + 距离卡片：
1. 两融余额市值比（日频折线图）
2. 股债利差（日频折线图）
3. 存款市值比（月频散点图）

三个图表共享同一组控件（位于图表区上方）：时间范围选择器和叠加指数选择器。

#### Scenario: Three cards render with bull market anchor markers
- **WHEN** 用户打开 China 模块
- **THEN** 三个指标卡片均可见，每个图表在对应历史牛市日期位置显示空心圆圈标记（替代原水平虚线），并附标注文字

#### Scenario: Distance cards replace metric caption
- **WHEN** 渲染最新值区域
- **THEN** 渲染 N+1 列样式化卡片（N = 时间范围内可见锚点数），每列显示锚点名称、参考值、距离描述（"很远/较远/较近/接近"或"超X%"），最后一列为最新值卡片（带指标主题色边框）

#### Scenario: Data freshness note displayed
- **WHEN** 渲染 China 指标卡片区域
- **THEN** 区域底部显示小字数据来源和最新更新日期（例如"融资融券余额：日更，至 2026-05-10 | PE：日更，约1日滞后 | M2：月更，至 2026-04"）

#### Scenario: Deposit ratio uses monthly dot chart
- **WHEN** 渲染存款市值比图表
- **THEN** 图表使用月频散点而非日频连线，x 轴以月份为单位

### Requirement: China Indicator Chart Time Period Selector

三个指标图表上方 SHALL 提供共用的时间范围选择器，允许用户切换查看不同历史长度的数据。

可选项：`1Y`、`3Y`、`5Y`、`10Y`、`15Y`，默认 `3Y`。

切换时间范围后，图表数据截断到对应起始日期，锚点圆圈若早于起始日期则自动隐藏。

#### Scenario: Default to 3Y view
- **WHEN** 用户首次打开 China 模块
- **THEN** 三个图表均显示过去 3 年数据，时间范围选择器默认选中 "3Y"

#### Scenario: Switch to 15Y view
- **WHEN** 用户选择 "15Y"
- **THEN** 三个图表数据延伸至 2015 年（历史数据起点），所有可见年份的锚点圆圈均显示

#### Scenario: Anchor hidden when out of range
- **WHEN** 用户选择 "1Y" 视图
- **THEN** 2015 年和 2021 年的早期锚点不在范围内，图表自动跳过，不报错也不留空白

### Requirement: China Indicator Chart Index Overlay

三个指标图表上方 SHALL 提供共用的叠加指数选择器，将市场走势叠加到指标折线图上。

可选项：`沪深300`、`创业板指`，默认 `沪深300`。叠加指数在右轴显示，以所选时间范围起点为基准归一化为百分比变化（`(close / close[0] - 1) * 100`），使用半透明浅色线条，不干扰主指标阅读。

#### Scenario: Default CSI 300 overlay
- **WHEN** 用户首次打开 China 模块
- **THEN** 三个图表均叠加沪深300走势（右轴，归一化 % 变化，浅蓝色半透明）

#### Scenario: Switch to ChiNext overlay
- **WHEN** 用户切换叠加指数为 "创业板指"
- **THEN** 三个图表的右轴叠加线更新为创业板指走势

#### Scenario: Overlay normalized to time period start
- **WHEN** 用户切换时间范围
- **THEN** 叠加指数重新以新的时间范围起点为基准（= 0%）归一化，保持相对涨跌幅可比

### Requirement: China Regime Scoring Table
系统 SHALL 在 China 模块中部渲染 A 股体制评分表，展示三层评分的当前状态：
- Layer 1：4 个信号的各自得分 (+1/0/-1)、Composite Score、Ceiling
- Layer 2：体制分类名称、各维度信号状态、Utilization Rate 区间
- Layer 3：5 个哨兵各自状态（CLEAR / TRIGGERED / COOLING）

#### Scenario: Scoring table renders all three layers
- **WHEN** China 体制评分计算完成
- **THEN** Dashboard 显示三层评分表，每层标题清晰，信号状态以颜色区分（绿/黄/红）

#### Scenario: L2 regime name localized
- **WHEN** 用户界面语言为中文
- **THEN** L2 体制名称显示为中文（"价值牛市" / "情绪牛市" / "恐慌底部" / "高估风险" / "中性"）

#### Scenario: Reasoning text shown per layer
- **WHEN** 渲染体制评分表
- **THEN** 每层附一行简短推理说明（如"M1 同比转正，DR007 低于 OMO，流动性趋于宽松"）

### Requirement: China Target Position Envelope Gauge
系统 SHALL 在 China 模块中部渲染一个 Gauge 仪表盘，显示 A 股 Target Position Envelope（min%–max%），样式与 US 模块 Envelope Gauge 一致。

#### Scenario: Gauge renders envelope range
- **WHEN** 三层合成完成
- **THEN** Gauge 显示当前 A 股建议仓位区间（如 "48%–60%"），并标注当前体制名称

#### Scenario: Emergency mode gauge changes color
- **WHEN** Layer 3 触发 emergency override
- **THEN** Gauge 以橙色或红色渲染，并附"哨兵触发中"提示文字

### Requirement: China Sentinel Warning Banner
系统 SHALL 在 China 模块顶部（条件显示）渲染警告横幅：当任意 Layer 3 哨兵处于 TRIGGERED 或 COOLING 状态时显示；无哨兵触发时隐藏。

#### Scenario: Banner appears on sentinel trigger
- **WHEN** `LIMIT_DOWN_PANIC` 哨兵 TRIGGERED
- **THEN** China 模块顶部显示橙色/红色警告横幅，描述触发原因（如"⚠️ 跌停恐慌哨兵触发：当日跌停股 62 只，超出阈值 50"）

#### Scenario: Multiple sentinels in banner
- **WHEN** 2 个及以上哨兵 TRIGGERED
- **THEN** 横幅列出所有触发的哨兵名称和触发值

#### Scenario: Banner hidden when all clear
- **WHEN** 所有 Layer 3 哨兵均为 CLEAR
- **THEN** 警告横幅不显示，不占用 UI 空间

### Requirement: China 12-Month Regime Timeline
系统 SHALL 在 China 模块底部渲染过去 12 个月的 A 股体制色带时间轴，每日使用对应 L2 体制颜色填充（`VALUE_BULL`=深绿，`SENTIMENT_BULL`=浅绿，`NEUTRAL`=黄，`PANIC_BOTTOM`=橙，`OVERVALUATION_RISK`=红），样式与 US 模块 Regime Timeline 一致。

#### Scenario: Timeline renders 12 months of history
- **WHEN** `china_regime_history.csv` 包含过去 12 个月记录
- **THEN** 色带时间轴完整渲染，当日用较深边框高亮

#### Scenario: Insufficient history shows available data
- **WHEN** 历史记录不足 12 个月（如初次部署）
- **THEN** 时间轴仅显示已有的历史范围，并标注"历史不足 12 个月"提示

