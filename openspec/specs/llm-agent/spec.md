# llm-agent 规范 (Specification)

## 目的 (Purpose)
待定 (TBD) - 由归档变更 create-macro-liquidity-analyst 创建。归档后更新目的。

## 需求 (Requirements)
### 需求：宏观策略师角色 (Macro Strategist Persona)
LLM Agent 必须 (MUST) 采用高级宏观对冲基金经理 (macro hedge fund manager) 的角色，并使用用户首选的语言进行交流。

#### 场景 (Scenario)：在上下文中生成分析
- **当 (WHEN)** 提供市场数据 (market data) 和目标语言（例如中文）时
- **那么 (THEN)** 响应使用适合该语言的专业金融术语 (financial terminology)
- **并且 (AND)** 输出文本严格使用请求的语言
- **并且 (AND)** 避免泛泛的建议，专注于“追逐风险 (risk-on)”与“规避风险 (risk-off)”的头寸配置 (positioning)

### 需求：市场状态评级 (Market Status Grading)
系统必须 (MUST) 输出清晰的红绿灯状态 (traffic-light status)。

#### 场景 (Scenario)：分配红绿灯
- **当 (WHEN)** 分析数据时
- **那么 (THEN)** 输出必须 (MUST) 根据信号 (signals) 的综合明确说明“绿色（看涨 / Bullish）”、“黄色（中性 / Neutral）”或“红色（看跌 / Bearish）”

### 需求：报告缓存 (Report Caching)
LLM Agent 必须 (MUST) 支持从本地存储保存和检索报告。

#### 场景 (Scenario)：保存生成的报告
- **当 (WHEN)** 成功生成报告时
- **那么 (THEN)** 它将与元数据（日期、语言、输入上下文）一起保存到磁盘

#### 场景 (Scenario)：检索缓存的报告
- **当 (WHEN)** 请求特定日期和语言时
- **那么 (THEN)** 如果存在，则返回确切的 markdown 内容
