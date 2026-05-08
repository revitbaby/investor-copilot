## ADDED Requirements

### Requirement: Regime-Aware Narrative Generation
LLM Agent SHALL 在单次 LLM 调用中接收完整结构化评分结果（三层分数、分指标明细、Target Envelope 以及可选的 position advisory 摘要）和原始市场数据，并生成 6 个带标签的叙事分段。

#### Scenario: Generate six narrative segments
- **WHEN** LLM 接收到包含三层结果与 position advice 的结构化评分输入
- **THEN** 生成以下内容：L1 Summary（1-2 句）、L2 Summary（1-2 句）、L3 Summary（1 句）、Executive Summary（3-5 句）、Position Narrative（4-6 句）和 Investment Playbook（按资产类别）

#### Scenario: Generate without position data
- **WHEN** LLM 接收到评分结果但用户未上传 portfolio
- **THEN** 仍生成 L1/L2/L3 summaries、Executive Summary 与 Investment Playbook
- **AND** Position Narrative 省略或明确说明未提供 portfolio

### Requirement: Regime Narrative Prompt Design
LLM system prompt SHALL 指示模型：所有结论都引用具体数值，显式指出相互矛盾的信号，在建议中给出明确动作与时间框架，并避免使用诸如 "consider watching" 或 "monitor closely" 的模糊措辞。

#### Scenario: Prompt enforces specificity
- **WHEN** LLM 生成 narrative
- **THEN** system prompt 要求每条分析陈述都引用精确指标值、阈值对比和 regime 标签

### Requirement: Narrative Section Parsing
系统 SHALL 使用 delimiter markers 将单次 LLM 响应解析为 6 个独立分段。若解析失败，整段响应 SHALL 作为 fallback Executive Summary。

#### Scenario: Successful parsing
- **WHEN** LLM 响应包含全部 6 个分隔分段
- **THEN** 每个分段都被提取并路由到对应 UI 位置

#### Scenario: Parsing failure fallback
- **WHEN** LLM 响应无法被解析为分段
- **THEN** 使用完整响应作为 Executive Summary，其余分段槽位留空

### Requirement: Narrative Generation Degradation
系统 SHALL 确保 LLM narrative 失败不会影响 rule-based 组件渲染（scoring tables、gauge、sentinel row、position advisory table）。失败时，Executive Summary 与 Investment Playbook SHALL 回退到现有 legacy LLM 输出。

#### Scenario: LLM call timeout
- **WHEN** LLM 调用超过 30 秒并超时
- **THEN** scoring tables 与 gauge 正常渲染
- **AND** Executive Summary 回退到 legacy LLM 内容
- **AND** 各层 summary 不显示

## MODIFIED Requirements

### Requirement: Macro Strategist Persona
LLM Agent MUST 采用资深宏观对冲基金经理（senior macro hedge fund manager）的人设，并以用户偏好语言输出。Agent 的分析 SHALL 以结构化三层 regime 评分结果为基础：rule-based 分数是仓位 sizing 的权威依据，同时以自然语言解释评分逻辑及其含义。

#### Scenario: Generate analysis in context
- **WHEN** 提供 market data、目标语言与结构化 regime 评分结果
- **THEN** 响应使用与该语言相匹配的专业金融术语
- **AND** 输出文本严格使用请求语言
- **AND** 所有仓位 sizing 引用均与 regime engine 计算出的 Target Envelope 对齐
- **AND** Agent 解释为何这些分数导出了该 envelope，而非自行提出独立数值
