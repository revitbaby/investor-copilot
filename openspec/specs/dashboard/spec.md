# dashboard 规范 (Specification)

## 目的 (Purpose)
待定 (TBD) - 由归档变更 create-macro-liquidity-analyst 创建。归档后更新目的。

## 需求 (Requirements)
### 需求：交互式可视化 (Interactive Visualization)
仪表板 (dashboard) 必须 (MUST) 将净流动性 (Net Liquidity) 与标普500 (S&P 500) 进行可视化对比。

#### 场景 (Scenario)：流动性相关性图表 (Liquidity Correlation Chart)
- **当 (WHEN)** 用户查看主仪表板时
- **那么 (THEN)** 双轴折线图 (dual-axis line chart) 在选定的时间范围内显示净流动性（左轴）和 SPY 价格（右轴）

### 需求：AI 报告显示 (AI Report Display)
仪表板必须 (MUST) 以用户选择的语言显示生成的 AI 分析。

#### 场景 (Scenario)：查看分析师报告 (View Analyst Report)
- **当 (WHEN)** 分析完成时
- **那么 (THEN)** Markdown 报告会在专用部分渲染
- **并且 (AND)** 内容以当前选择的语言编写
- **并且 (AND)** 关键指标（当前水平，1周变化）在带有本地化标签的摘要视图中显示

### 需求：语言选择 (Language Selection)
仪表板必须 (MUST) 提供一种机制，让用户选择其首选的界面语言。

#### 场景 (Scenario)：切换语言 (Switch Language)
- **当 (WHEN)** 用户从语言选择器中选择“中文”时
- **那么 (THEN)** 所有静态 UI 文本立即更新为中文
- **并且 (AND)** 该选择在会话 (session) 期间保持不变

### 需求：报告历史 (Report History)
仪表板必须 (MUST) 允许用户查看以前生成的分析报告。

#### 场景 (Scenario)：查看过去的报告 (View Past Report)
- **当 (WHEN)** 用户从报告历史选择器中选择过去的日期时
- **那么 (THEN)** 系统加载并显示该日期和当前语言的缓存报告
- **并且 (AND)** 隐藏“生成 (Generate)”按钮

### 需求：报告持久化 (Report Persistence)
仪表板必须 (MUST) 缓存生成的报告以防止多余的 API 调用。

#### 场景 (Scenario)：加载缓存的报告 (Load Cached Report)
- **当 (WHEN)** 仪表板加载时
- **如果 (IF)** 存在当前日期和语言的报告
- **那么 (THEN)** 它会自动显示
- **并且 (AND)** 提供“重新生成 (Regenerate)”按钮

### 需求：央行可视化 (Central Bank Visualization)
仪表板必须 (MUST) 显示美联储资产负债表 (Federal Reserve's balance sheet) 和政策利率 (policy rates) 的详细指标。

#### 场景 (Scenario)：查看美联储资产负债表组成部分
- **当 (WHEN)** 用户滚动到详细指标部分时
- **那么 (THEN)** 图表显示总资产 (WALCL)、逆回购 (RRP) 和财政部一般账户 (TGA) 的趋势
- **并且 (AND)** 单独的图表显示隔夜融资利率 (SOFR)

### 需求：市场健康度可视化 (Market Health Visualization)
仪表板必须 (MUST) 可视化市场风险和活动指标。

#### 场景 (Scenario)：查看市场内部数据 (View Market Internals)
- **当 (WHEN)** 用户查看市场侧图表时
- **那么 (THEN)** 它显示 SPY 交易量、波动率指数 (VIX, MOVE) 和高收益债券 ETF (HYG, JNK)

### 需求：跨资产可视化 (Cross-Asset Visualization)
仪表板必须 (MUST) 显示关键的跨资产相关性 (cross-asset correlations)。

#### 场景 (Scenario)：查看资产类别 (View Asset Classes)
- **当 (WHEN)** 用户查看跨资产图表时
- **那么 (THEN)** 它显示美元指数 (DXY)、黄金、WTI 原油、比特币 (BTC) 和美国 10 年期国债收益率 (US 10Y Treasury Yields) 的表现

### 需求：仪表板布局 (Dashboard Layout)
详细图表必须 (MUST) 以 2x2 网格布局排列。

#### 场景 (Scenario)：2x2 网格布局
- **当 (WHEN)** 仪表板渲染详细图表时
- **那么 (THEN)** 它们排列成两行两列
- **并且 (AND)** 图表的尺寸小于主净流动性图表

### 需求：中国/香港仪表板选项卡 (China/HK Dashboard Tab)
仪表板必须 (MUST) 为中国和香港流动性分析提供专用的选项卡。

#### 场景 (Scenario)：导航到中国仪表板
- **当 (WHEN)** 用户选择“🇨🇳 中国/香港流动性 (China/HK Liquidity)”选项卡时
- **那么 (THEN)** 视图切换以显示特定于中国/香港的图表和指标

### 需求：中国流动性可视化 (China Liquidity Visualization)
仪表板必须 (MUST) 可视化三层流动性框架（宏观、中观、微观 / Macro, Meso, Micro）。

#### 场景 (Scenario)：查看中国宏观图表 (View China Macro Charts)
- **当 (WHEN)** 用户查看中国仪表板时
- **那么 (THEN)** 图表显示 DR007 与 OMO 利率、M1-M2 剪刀差和社会融资

#### 场景 (Scenario)：查看中国市场图表 (View China Market Charts)
- **当 (WHEN)** 用户查看中国仪表板时
- **那么 (THEN)** 图表显示 A 股换手率、北向资金流向和融资融券余额

### 需求：香港流动性可视化 (HK Liquidity Visualization)
仪表板必须 (MUST) 可视化香港特定的流动性驱动因素。

#### 场景 (Scenario)：查看香港图表 (View HK Charts)
- **当 (WHEN)** 用户查看香港部分时
- **那么 (THEN)** 图表显示 AH 股溢价指数、南向资金流向和 USD/CNH 与 HSI 的对比
