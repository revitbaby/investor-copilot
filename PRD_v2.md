# PRD v2.0: 三层市场体制评分引擎（Three-Layer Regime Scoring Engine）

> **目标系统**: Macro Liquidity Copilot Dashboard
> **版本**: v2.0
> **日期**: 2026-04-25
> **读者**: AI Coding Agent — 本文档定义业务逻辑与功能需求，技术设计与实现由你完成

---

## 0. 给 Coding Agent 的前置说明

本文档是一份**产品需求文档**，描述的是"系统应该做什么"和"用户应该看到什么"。你需要在此基础上自行完成技术设计（数据模型、模块划分、函数签名等）和编码实现。

关键约束：

- 所有阈值和权重**必须可配置**（推荐使用YAML或类似配置文件），文档中给出的数值均为默认值
- 三层打分逻辑为**确定性规则**（rule-based），不依赖LLM。LLM仅用于第8节定义的叙事生成
- 新增模块必须与现有dashboard代码兼容——优先通过新增文件实现，尽量不修改现有文件
- 本文档中所有"默认值"均可在后续调优中修改，因此硬编码是不可接受的

### 术语表

| 术语 | 含义 |
|---|---|
| Position Ceiling | Layer 1 输出的总仓位上限百分比 |
| Utilization Rate | Layer 2 输出的Ceiling使用率范围 |
| Target Position Envelope | `Ceiling × Utilization` 得出的最终目标仓位区间 |
| Sentinel | Layer 3 的二元熔断触发器 |
| Conviction | 用户对单个持仓的信念等级（S/A/B/C） |
| Net Liquidity | `WALCL - TGA - RRP`（美联储净流动性） |

---

## 1. 功能概述

### 1.1 目标

在现有dashboard上新增**三层体制评分引擎**，实现四个核心能力：

1. **三层独立打分**：按不同时间层级评估宏观环境，每层以表格形式展示打分推理过程
2. **目标仓位区间合成**：三层分数合成为一个 Target Position Envelope，以可视化gauge展示
3. **持仓操作建议**：基于目标仓位区间 + 用户持仓数据，生成逐个持仓的操作建议
4. **LLM叙事集成**：现有LLM分析师的输出嵌入三层架构，对每层打分做自然语言总结并生成综合投资建议

### 1.2 系统数据流

```
现有数据管道（FRED API, Market Data API 等）
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│                     REGIME SCORING ENGINE                        │
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │  Layer 1   │  │  Layer 2   │  │  Layer 3   │                │
│  │ 流动性基底  │  │ 市场体制   │  │ 即时哨兵   │                │
│  │ → Ceiling  │  │ → Util%    │  │ → Override │                │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘                │
│        │               │               │                        │
│        └───────┬───────┘               │                        │
│                ▼                       │                        │
│     Target Envelope ◄─────────────────┘                        │
│     (Ceiling × Util, 或被L3紧急覆盖)                            │
│                │                                                │
│                ▼                                                │
│     Position Advisor（逐持仓建议）                               │
└────────┬────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────┐
│                     LLM 叙事生成（1次调用）                       │
│                                                                  │
│  输入：三层结构化打分结果 + 原始指标 + 持仓建议                   │
│  输出：                                                          │
│    - 每层1-2句总结（嵌入各层scoring table下方）                   │
│    - 综合叙事（嵌入Position Advisory卡片底部）                    │
│    - 替换现有 Executive Summary 和 Investment Playbook           │
└──────────────────────────────────────────────────────────────────┘
         │
         ▼
       UI 渲染
```

---

## 2. Layer 1: 流动性基底

### 2.1 职责

评估宏观流动性环境的**结构性状态**，输出 **Position Ceiling**（总仓位上限）。这是最慢变化的一层，决定了无论市场情绪多乐观，你的仓位绝对不应超过多少。

### 2.2 更新频率

每周一次（Friday close后），数据到达时自动重算。

### 2.3 输入指标与打分规则

共4个指标，每个独立打分为 +1 / 0 / -1。

**L1-1: Net Liquidity Trend**

- 数据来源：**已有** — `WALCL - TGA - RRP`
- 计算20日移动均线（20DMA），观察其逐周变化方向
- +1（利好）：20DMA连续上升 ≥ N周（默认3周），每周涨幅 > 阈值（默认0.5%/周）
- 0（中性）：20DMA变化幅度在阈值范围内
- -1（利空）：20DMA连续下降 ≥ N周，每周跌幅超过阈值
- 展示值示例：`5,234,561M (偏离20DMA +1.2%)`

**L1-2: TGA Trend**

- 数据来源：**已有** — `FRED:WTREGEN`
- 观察过去约1个月（默认21个交易日）的TGA余额变化百分比
- **注意方向反转**：TGA下降 = 财政部向市场释放流动性 = 利好；TGA上升 = 吸收流动性 = 利空
- +1：月变化 < -5%（TGA下降，释放流动性）
- 0：月变化在 ±5% 以内
- -1：月变化 > +5%（TGA上升，吸收流动性）

**L1-3: RRP Buffer**

- 数据来源：**已有** — `FRED:RRPONTSYD`
- 评估隔夜逆回购余额水平（不看趋势，看绝对水平）
- +1：余额 > 高阈值（默认$200B）— 缓冲充裕
- 0：介于两个阈值之间
- -1：余额 < 低阈值（默认$50B）— 缓冲接近耗尽

**L1-4: Policy Rate Direction**

- 数据来源：**已有** — `SOFR` 或 `EFFR`
- 比较当前利率与约90日历天前（默认63个交易日）的利率差异
- +1：期间降息 ≥ 10bp
- 0：变化在 ±10bp 以内
- -1：期间加息 ≥ 10bp

### 2.4 Composite Score 计算

将4个指标得分直接相加，得到 Composite Score，范围为 -4 到 +4。

### 2.5 Regime 判定与 Ceiling 映射

| Composite Score | Regime | Ceiling（默认值） | 颜色 |
|---|---|---|---|
| ≥ 3 | EXPANSIONARY | 100% | 🟢 绿 `#22c55e` |
| 1 到 2 | NEUTRAL | 80% | 🟡 黄 `#eab308` |
| -1 到 0 | CONTRACTING | 60% | 🟠 橙 `#f97316` |
| ≤ -2 | SEVERE CONTRACTION | 40% | 🔴 红 `#ef4444` |

**业务含义**：当流动性环境处于 CONTRACTING 状态时，即使市场短期看起来很好（Layer 2 risk-on），你的总仓位也不应超过60%。流动性是地基，地基不稳的时候不应该往上加层。

---

## 3. Layer 2: 市场体制

### 3.1 职责

评估当前市场参与者行为和价格动量状态，输出 **Utilization Rate 范围**（在 Layer 1 Ceiling 内应使用多少比例）。

### 3.2 更新频率

每个交易日收盘后计算。

### 3.3 输入指标与打分规则

共8个指标，每个打分为 +1 / 0 / -1，并乘以各自的权重。

| ID | 指标 | 数据来源 | +1 (Risk-On) | 0 (Neutral) | -1 (Risk-Off) | 权重（默认） |
|---|---|---|---|---|---|---|
| L2-1 | SPX vs 50DMA | 已有 | SPX高于50DMA超过1% | 在±1%范围内 | SPX低于50DMA超过1% | 1.5 |
| L2-2 | Market Breadth (S5FI) | **新增**（见第9节） | S5FI > 60% | 40%-60% | S5FI < 40% | 1.5 |
| L2-3 | VIX Level | 已有 | VIX < 18 | 18-25 | VIX > 25 | 1.0 |
| L2-4 | VIX Trend (10D) | 已有 | 10日变化率 < -10%（VIX下降=利好） | 变化率±10%内 | 10日变化率 > +10%（VIX上升=利空） | 1.0 |
| L2-5 | MOVE Index | 已有 | MOVE < 85 | 85-110 | MOVE > 110 | 1.0 |
| L2-6 | Credit Health (JNK趋势) | 已有 | JNK 20DMA 5日斜率为正（信用改善） | 斜率在阈值内 | 斜率为负（信用恶化） | 1.0 |
| L2-7 | Gold-SPX滚动相关性 | 已有 | 30日相关性 < 0.2（正常分化） | 0.2-0.4 | 30日相关性 > 0.4（避险共振，同涨=市场焦虑） | 0.5 |
| L2-8 | DXY Trend | 已有 | 月变化温和向下 | 月变化幅度正常 | 月涨 > 2% **或** 月跌 > 3%（极端双向均为利空） | 0.5 |

**L2-8 特殊逻辑说明**：DXY（美元指数）的信号是非线性的——极端走强意味着全球流动性收紧，极端走弱意味着对美元/美国经济信心危机。两种极端情况都是 risk-off 信号。只有温和变动是良性的。

### 3.4 Weighted Composite 计算

```
Weighted Composite = Σ (每个指标得分 × 该指标权重)
```

以默认权重计算，理论范围为 -8.0 到 +8.0。

### 3.5 Regime 判定与 Utilization 映射

| Weighted Score | Regime | Utilization Range（默认） | 颜色 |
|---|---|---|---|
| ≥ 5.0 | STRONG RISK-ON | 90% – 100% | 🟢 `#22c55e` |
| 2.0 到 4.9 | RISK-ON | 70% – 85% | 🟢 `#86efac` |
| -1.9 到 1.9 | NEUTRAL | 50% – 65% | ⚪ `#9ca3af` |
| -2.0 到 -4.9 | RISK-OFF | 25% – 40% | 🟠 `#f97316` |
| ≤ -5.0 | STRONG RISK-OFF | 0% – 20% | 🔴 `#ef4444` |

**业务含义举例**：如果 Layer 1 给出 Ceiling = 60%（CONTRACTING），Layer 2 给出 Utilization = 70%-85%（RISK-ON），那么目标仓位区间 = 60% × 70%-85% = **42%-51%**。市场短期不错，但流动性地基在收缩，所以仓位需要克制。

---

## 4. Layer 3: 即时风险哨兵

### 4.1 职责

二元熔断层。哨兵是"断路器"——正常情况下不影响任何计算，但一旦触发，**直接覆盖** Layer 1 × Layer 2 的计算结果，强制将仓位上限降至紧急水平。

### 4.2 更新频率

每次数据刷新时检查（建议 ≤ 15分钟间隔）。

### 4.3 哨兵定义

| ID | 哨兵名称 | 触发条件 | 紧急动作 | 重置条件 |
|---|---|---|---|---|
| L3-1 | VIX Spike | VIX > 35 | 强制仓位上限 ≤ 20% | VIX收盘 < 25 连续3天 |
| L3-2 | Credit Break | JNK 或 HYG 单日收益 < -1.5% | 强制仓位上限 ≤ 20% | JNK和HYG均连续5天正收益 |
| L3-3 | Bond Vol Spike | MOVE > 130 | **冻结**：禁止开新仓（不强制减仓） | MOVE < 110 连续5天 |
| L3-4 | Trend Break | SPX收于50DMA下方 **且** 同日VIX > 25 | 强制仓位上限 ≤ 20% | SPX收于50DMA上方 **且** VIX < 22 **且** S5FI > 50%，三个条件同时满足连续3天 |

### 4.4 核心设计原则：不对称重置

这是本系统最重要的设计理念之一：

- **触发**：任何单一条件满足 → 立即生效（快速反应）
- **重置**：该哨兵的**所有**重置条件必须**同时**满足，且**连续多天** → 才能解除（缓慢恢复信任）

原因：市场下跌速度远快于恢复速度。宁可让用户多持有现金几天（少赚一点），也不应在市场仍不稳定时让用户满仓（可能大亏）。

### 4.5 多哨兵同时触发

当多个哨兵同时触发时，取所有 `forced_ceiling` 中的**最小值**作为紧急上限。L3-3（冻结型，无forced_ceiling）不参与最小值计算，但"禁止开新仓"规则仍生效。

### 4.6 哨兵三态

每个哨兵有三个状态：

- **CLEAR**（正常）：绿色，不影响任何计算
- **TRIGGERED**（已触发）：红色，紧急措施生效
- **COOLING**（冷却中）：黄色，触发条件已消失但重置条件尚未完全满足，紧急措施仍然生效

### 4.7 状态持久化

哨兵状态需要**跨会话持久化**（记住触发时间和冷却进度）。每次计算后保存状态，每次启动时恢复状态。首次运行时所有哨兵初始化为 CLEAR。

---

## 5. 组合计算：Target Position Envelope

### 5.1 正常模式

当Layer 3无哨兵触发时：

```
Target Min = L1 Ceiling × L2 Utilization下限
Target Max = L1 Ceiling × L2 Utilization上限
```

展示标签示例：`42% – 51%`

### 5.2 紧急模式

当Layer 3有哨兵触发时：

```
Target Min = 0%
Target Max = L3 Override Ceiling（所有活跃哨兵中最低的forced_ceiling）
```

展示标签示例：`≤ 20% (紧急)`

**紧急模式完全忽略 Layer 1 和 Layer 2 的计算结果。**

### 5.3 典型场景矩阵

| L1 状态 | L2 状态 | L3 状态 | Target Envelope | 解读 |
|---|---|---|---|---|
| EXPANSIONARY (100%) | STRONG RISK-ON (90-100%) | All Clear | 90% – 100% | 一切良好，可满仓 |
| NEUTRAL (80%) | RISK-ON (70-85%) | All Clear | 56% – 68% | 流动性还行，市场不错，但仓位别太激进 |
| CONTRACTING (60%) | RISK-ON (70-85%) | All Clear | 42% – 51% | 流动性在收缩但市场还没反应，保持警惕 |
| CONTRACTING (60%) | RISK-OFF (25-40%) | All Clear | 15% – 24% | 流动性和市场都不好，大幅降仓 |
| EXPANSIONARY (100%) | STRONG RISK-ON (90-100%) | VIX Spike | ≤ 20% | 之前一切很好但突发事件，紧急熔断 |
| SEVERE (40%) | STRONG RISK-OFF (0-20%) | Credit Break | ≤ 20% | 全面危机，最低仓位 |

---

## 6. 持仓建议模块

### 6.1 职责

将 Target Position Envelope + 用户实际持仓 → 逐个持仓的具体操作建议。

### 6.2 用户输入

用户通过CSV上传持仓数据，需包含以下字段：

| 字段 | 说明 | 示例 |
|---|---|---|
| ticker | 股票/期权代码 | NVDA |
| type | 持仓类型 | stock / etf / option_long_call / option_long_put / option_short_call / option_short_put |
| shares_or_contracts | 数量 | 150 |
| cost_basis | 成本价 | 120.50 |
| current_price | 当前价 | 145.00 |
| market_value | 市值 | 21750 |
| notional_exposure | 名义敞口 | 对stock/etf = market_value；对options = delta-adjusted notional |
| sector | 行业/主题分类 | AI_Semiconductor |
| conviction | 信念等级 | S / A / B / C / Hedge |
| beta_spx | 相对SPX的Beta | 1.65 |
| underlying | 标的（options专用） | NVDA |
| expiry | 到期日（options专用） | 2025-06-20 |

此外，用户需提供总账户价值（total_value）和现金余额（cash）。

### 6.3 风险敞口计算

- **Risk Exposure** = 所有非Hedge持仓的 `notional_exposure` 之和
- `conviction = "Hedge"` 的持仓（如 protective puts）**不计入**风险敞口，也不参与减仓排序
- **当前仓位百分比** = Risk Exposure / Total Account Value

### 6.4 单持仓限额：Conviction × Regime 矩阵

每个持仓有一个最大占比，取决于其 conviction 等级和当前 L2 regime：

| Conviction \ Regime | STRONG RISK-ON | RISK-ON | NEUTRAL | RISK-OFF | STRONG RISK-OFF |
|---|---|---|---|---|---|
| **S** (最高信念) | 25% | 20% | 15% | 10% | 5% |
| **A** | 18% | 15% | 10% | 7% | 3% |
| **B** | 12% | 10% | 7% | 4% | 0%（应清仓） |
| **C** (最低信念) | 8% | 5% | 3% | 0%（应清仓） | 0%（应清仓） |

**业务含义**：当市场进入 RISK-OFF，低conviction持仓应被首先清除。只有你最有信心的持仓（S级）才值得在恶劣环境中保留。

### 6.5 减仓优先级排序

当需要减仓时（当前敞口 > Target Max），按以下优先级排序（先减的排前面）：

1. **Conviction低者优先**：C → B → A → S
2. 同Conviction：**Beta高者优先**（先减波动大的）
3. 同Conviction + Beta：**未实现收益率高者优先**（先卖盈利的，出于税务效率考虑）

### 6.6 体制特殊规则

以下规则根据当前体制自动生效：

| 条件 | 规则 |
|---|---|
| L1 = CONTRACTING 或 SEVERE | Options notional 总额 ≤ 10%（默认）；禁止使用杠杆/保证金 |
| L1 = SEVERE CONTRACTION | 仅保留 S-conviction 持仓，其余应清仓 |
| L3-3 MOVE Spike 触发中 | 冻结：禁止开新仓（现有持仓不受影响） |
| L3 任意哨兵触发 | 紧急模式：仅保留最核心持仓 |

### 6.7 操作类型

每个持仓的建议操作为以下四种之一：

- **CLOSE**：完全清仓（当限额为0%或持仓占比极小时）
- **TRIM**：部分减仓到目标占比
- **HOLD**：维持当前仓位
- **ADD**：可加仓（仅在低配时出现）

### 6.8 输出内容

持仓建议的输出需包含：每个持仓的操作优先级、操作类型、当前占比、目标占比、调整金额（美元）、原因简述，以及当前生效的全部体制规则列表。

---

## 7. LLM叙事生成与现有分析师集成

### 7.1 现有系统现状

现有dashboard已有一个LLM宏观策略分析师，基于原始指标数据生成四个叙事板块：Executive Summary、Liquidity Analysis、Risk Signals、Investment Playbook。

### 7.2 改造方案

```
改造前:
  原始指标 → LLM → 四个叙事板块（纯LLM驱动）

改造后:
  阶段1: 原始指标 → 三层引擎（rule-based）→ 结构化打分结果
  阶段2: 结构化打分结果 → Position Advisor（rule-based）→ 持仓建议
  阶段3: 结构化打分结果 + 原始指标 + 持仓建议 → LLM（1次调用）→ 叙事内容
```

**核心原则**：rule-based引擎做决策，LLM做解释。LLM不决定仓位数字或操作建议，它只负责将结构化结果翻译成人类可读的叙事。

### 7.3 LLM输出内容

一次LLM调用需生成以下六段内容：

| 输出字段 | 嵌入位置 | 长度 | 内容要求 |
|---|---|---|---|
| L1 Summary | Layer 1 scoring table下方 | 1-2句 | 总结流动性基底状态及对仓位的含义 |
| L2 Summary | Layer 2 scoring table下方 | 1-2句 | 总结市场体制及各信号的关键矛盾或一致性 |
| L3 Summary | Layer 3 sentinel卡片下方 | 1句 | 总结哨兵状态 |
| Executive Summary | **替换**现有Executive Summary板块 | 3-5句 | 全局总结，含市场状态颜色判定、核心矛盾、最关键的单一风险因素 |
| Position Narrative | Position Advisory卡片底部 | 4-6句 | 当前仓位vs目标仓位偏差量化、最优先的1-2个操作、操作时间窗口、下一个催化剂 |
| Investment Playbook | **替换**现有Investment Playbook板块 | 分资产类别 | 按Equities/Bonds/Crypto/Cash分类的具体策略建议 |

### 7.4 LLM Prompt设计要求

向LLM传入的prompt应包含：

- 三层打分的完整结构化数据（每个指标的原始值、命中阈值、得分）
- Target Envelope计算过程和结果
- 持仓建议的汇总数据（如果用户已上传持仓）
- 原始市场数据（与现有LLM分析师相同的输入，确保兼容）

LLM system prompt应强调：所有结论必须引用具体数字；矛盾信号必须明确指出；建议必须包含具体操作和时间框架；禁止"建议关注"等模糊措辞。

### 7.5 降级策略

如果LLM叙事生成失败：

- Executive Summary 和 Investment Playbook 回退到现有LLM分析师的输出
- 各层summary回退为空（仅显示结构化scoring table，不显示叙事）
- **不影响**三层评分和持仓建议的展示（这些是rule-based的，不依赖LLM）

### 7.6 与现有代码的关系

- **保留**现有LLM调用代码不删除（作为fallback）
- **保留** Liquidity Analysis 和 Risk Signals 板块内容不变（与新增的scoring tables互补）
- **替换** Executive Summary 和 Investment Playbook 的内容来源

---

## 8. 新增数据源：S5FI Market Breadth

### 8.1 需求

Layer 2 的 L2-2 指标需要 **S5FI**：S&P 500成分股中，价格高于自身50日均线的股票占比（0-100%）。

### 8.2 当前状态

现有数据管道中**不包含**此数据，需要新增获取逻辑。

### 8.3 推荐实现方案

**Sector ETF近似法**：下载11个SPDR行业ETF（XLK, XLF, XLV, XLC, XLY, XLI, XLP, XLE, XLRE, XLU, XLB），判断每个ETF当前价格是否高于自身50DMA，然后按各行业在S&P 500中的权重加权得到整体breadth近似值。

行业权重（默认值，应可配置，每季度根据最新S&P 500权重更新）：

| ETF | 行业 | 权重 |
|---|---|---|
| XLK | Technology | 32% |
| XLF | Financials | 13% |
| XLV | Health Care | 12% |
| XLY | Consumer Discretionary | 10% |
| XLC | Communication Services | 9% |
| XLI | Industrials | 8% |
| XLP | Consumer Staples | 6% |
| XLE | Energy | 4% |
| XLRE | Real Estate | 2% |
| XLU | Utilities | 2% |
| XLB | Materials | 2% |

此方法的优点是仅需获取11个ETF的数据（快速）；缺点是精度不如逐个成分股计算。对于本系统的打分用途足够准确。

**可选增强**：提供精确版本（逐个下载500只成分股），仅在日终batch job中使用，不在实时刷新中调用。

### 8.4 无数据时的降级

如果ETF数据获取失败，S5FI应返回中性值50.0（使该指标得分为0，不影响整体打分方向）。

---

## 9. UI / 可视化需求

### 9.1 整体布局

新增组件插入现有dashboard页面**顶部**（在现有内容之前），布局从上到下依次为：

```
页面顶部
├── [L3 Alert Banner]       ← 条件渲染：仅L3触发时显示
├── [Regime Gauge]           ← 全宽 hero 组件
├── [两列布局]
│   ├── [L1 Scoring Table]   ← 左半
│   └── [L2 Scoring Table]   ← 右半
├── [L3 Sentinel Row]        ← 全宽紧凑行
├── [Position Advisory]      ← 全宽（需用户上传持仓后显示）
├── [Regime Timeline]        ← 全宽（12个月历史）
├── ─── 以下为现有组件 ───
├── [现有图表: Liquidity vs Market 等]
└── [现有LLM分析: 被替换后的 Executive Summary / Investment Playbook]
```

### 9.2 L3 Alert Banner

**触发条件**：任何L3哨兵状态为 TRIGGERED 或 COOLING 时显示。

**视觉**：全宽红色横幅，固定在页面顶部（sticky），白色文字。

**内容**：

- 图标 ⚡ + 标题："LAYER 3 ALERT: {哨兵名称} TRIGGERED"
- 紧急仓位上限显示
- 触发时间
- 重置进度："重置条件: {描述}（还需{N}天）"
- 多个哨兵同时触发时，按严重程度（forced_ceiling从低到高）依次显示

### 9.3 Regime Gauge（Hero组件）

这是新增内容中最醒目的组件，用户打开dashboard首先看到它。

**视觉**：水平条形仪表盘，从0%到100%。

**核心元素**：

- **目标区间高亮**：在条形图上用填充色块标注目标仓位区间（例如42%到51%之间用色块填充）
  - 色块颜色随target_max变化：>70% 绿色，50-70% 黄色，30-50% 橙色，<30% 红色
  - 紧急模式下为红色
- **当前仓位标记**（仅用户上传持仓后显示）：三角形标记 ▼ 在条上标注当前仓位百分比
  - 超出target_max：红色标记 + "⚠️ 超配 X pp"
  - 在目标范围内：绿色标记 + "✅ 在目标范围内"
  - 低于target_min：蓝色标记 + "ℹ️ 低配 X pp"

**推导过程展示**（条形图下方文字）：

- 正常模式：`L1 Ceiling (CONTRACTING): 60% × L2 Utilization (RISK-ON): 70%-85% = 42%-51%`
- 紧急模式：`🚨 L3紧急覆盖: 仓位上限 20% (无视L1/L2计算)`
- L3状态一句话总结：`L3 Sentinels: All Clear ✅` 或具体触发状态

### 9.4 L1 Scoring Table

**视觉**：卡片容器。

**卡片头部**：

- 标题："LAYER 1: 流动性基底"
- 右上角badge：`Regime: 🟢 EXPANSIONARY   Ceiling: 100%`（颜色随regime变化）

**表格**：

| 列 | 内容 |
|---|---|
| 指标 | 指标名称 |
| 当前值 | 原始数据展示值 |
| 命中阈值 | 当前值命中了哪个阈值区间的描述 |
| 得分 | 🟩+1 / ⬜0 / 🟥-1（用彩色方块展示） |

**底部汇总行**：`COMPOSITE: {分数}`，背景色用regime颜色高亮。

**汇总行下方**：LLM生成的1-2句总结，灰色斜体显示。

### 9.5 L2 Scoring Table

与L1类似但多两列：

| 列 | 内容 |
|---|---|
| 指标 | 名称 |
| 当前值 | 原始值 |
| 命中阈值 | 阈值描述 |
| 得分 | 🟩/⬜/🟥 |
| 权重 | 该指标权重 |
| 加权分 | 得分 × 权重 |

**额外元素**：汇总行下方增加一个 **Score Bar** 微型可视化——水平条从-8.0到+8.0，当前分数位置用 ▲ 标注，条上用竖线标注各regime区间的分界线。

右上角badge：`Regime: 🟠 RISK-OFF   Utilization: 25%-40%`

### 9.6 L3 Sentinel Row

**视觉**：紧凑的单行布局（不是卡片展开），四个哨兵并排。

**格式**：`"LAYER 3: 哨兵   {All Clear ✅ 或 X个触发中 🚨}"`

每个哨兵显示为一个小方块：

- CLEAR：绿色背景 + ✅ + 当前值
- TRIGGERED：红色背景 + 🚨 + 当前值
- COOLING：黄色背景 + ⏳ + "重置中 (N天后)" + 当前值

下方显示LLM的L3 summary（仅在有触发时显示；全clear时可省略）。

### 9.7 Position Advisory

**条件渲染**：用户未上传持仓时，显示占位文本 "上传持仓CSV以获取个性化建议" + 文件上传按钮。

**上传持仓后的内容**：

**顶部摘要区**：

- 当前敞口百分比
- 目标区间
- 状态标签（超配/正常/低配）
- 需调整金额

**减仓优先级表格**：

| 列 | 内容 |
|---|---|
| 优先级 | 操作顺序编号 |
| Ticker | 持仓代码 |
| Conviction | S/A/B/C |
| 当前占比 | 百分比 |
| 目标占比 | 百分比 |
| 操作 | CLOSE/TRIM/HOLD/ADD |
| 调整金额 | 美元 |
| 原因 | 简述 |

行背景色：CLOSE=红色，TRIM=橙色，HOLD=灰色（默认折叠），ADD=绿色。

**当前生效规则列表**：列出当前体制下所有自动生效的规则（如"流动性收缩期→Options notional ≤ 10%"）。

**底部**：LLM生成的持仓操作综合叙事。

### 9.8 Regime Timeline（历史时间线）

**数据来源**：需要每日打分结果的持久化存储。首次部署时无历史数据，显示"体制评分历史将从今日开始积累"。

**视觉**：4行堆叠时间线图，共享同一时间轴（过去12个月）：

- **行1**：L1 Regime — 彩色条带（颜色=regime颜色），展示体制在不同时期的切换
- **行2**：L2 Regime — 彩色条带
- **行3**：L3 Events — 时间轴上的 ⚡ 标记点，标注每次哨兵触发事件
- **行4**：Target Envelope — 阴影区域图（y轴=0-100%），展示目标仓位区间随时间的变化

**叠加**：SPX价格走势线（半透明，使用右侧y轴），让用户直观看到体制变化与市场走势的关系。

---

## 10. 配置项清单

以下所有数值为默认值，必须可通过配置文件修改。

### Layer 1 配置

| 配置项 | 默认值 | 说明 |
|---|---|---|
| net_liquidity.lookback_weeks | 3 | 判定趋势所需的连续周数 |
| net_liquidity.rising_threshold | 0.5%/周 | 周涨幅阈值 |
| net_liquidity.falling_threshold | -0.5%/周 | 周跌幅阈值 |
| tga.lookback_days | 21 | 月变化回看天数 |
| tga.rising_threshold | +5% | TGA上升阈值 |
| tga.falling_threshold | -5% | TGA下降阈值 |
| rrp.high_threshold | $200B | RRP充裕阈值 |
| rrp.low_threshold | $50B | RRP枯竭阈值 |
| policy_rate.lookback_days | 63 | 利率变化回看天数 |
| policy_rate.cut_threshold | 10bp | 降息阈值 |
| policy_rate.hike_threshold | 10bp | 加息阈值 |
| ceiling_map.expansionary | 100% | Composite ≥ 3 时的Ceiling |
| ceiling_map.neutral | 80% | Composite 1-2 |
| ceiling_map.contracting | 60% | Composite -1 到 0 |
| ceiling_map.severe | 40% | Composite ≤ -2 |

### Layer 2 配置

| 配置项 | 默认值 |
|---|---|
| weights (8个) | 见第3.3节表格 |
| 各指标阈值 (16+个) | 见第3.3节表格 |
| utilization_map (5档) | 见第3.5节表格 |

### Layer 3 配置

| 配置项 | 默认值 |
|---|---|
| vix_spike.trigger | 35 |
| vix_spike.reset_below | 25 |
| vix_spike.reset_days | 3 |
| vix_spike.forced_ceiling | 20% |
| credit_break.trigger_return | -1.5% |
| credit_break.reset_days | 5 |
| credit_break.forced_ceiling | 20% |
| move_spike.trigger | 130 |
| move_spike.reset_below | 110 |
| move_spike.reset_days | 5 |
| move_spike.forced_ceiling | null (冻结) |
| trend_break.trigger_vix | 25 |
| trend_break.reset_vix | 22 |
| trend_break.reset_breadth | 50% |
| trend_break.reset_days | 3 |
| trend_break.forced_ceiling | 20% |

### 持仓限额配置

| 配置项 | 默认值 |
|---|---|
| conviction_regime_matrix | 见第6.4节表格 |
| options_notional_limit_contracting | 10% |
| options_notional_limit_normal | 25% |

### Breadth配置

| 配置项 | 默认值 |
|---|---|
| sector_weights (11个) | 见第8.3节表格 |

---

## 11. 非功能性需求

### 性能

- 三层引擎计算（不含数据获取和LLM调用）应在 < 2秒内完成
- S5FI近似法数据获取应在 < 30秒内完成
- LLM叙事生成允许最长30秒超时

### 可靠性

- 任何单个数据源获取失败不应导致整个引擎崩溃——该指标得分回退为0
- LLM调用失败不应影响scoring tables和gauge的渲染（见第7.5节降级策略）
- 哨兵状态文件损坏时，所有哨兵初始化为CLEAR

### 兼容性

- 新增模块不应改变现有dashboard的任何现有功能
- 所有新增组件使用与现有dashboard一致的设计语言和组件库

---

## 12. 验收标准

以下为系统实现完成后的验收条件：

### 打分正确性

1. 当L1四个指标均为+1时（构造：net_liq连续上升、TGA下降、RRP充裕、降息周期），composite必须 ≥ 3，regime = EXPANSIONARY，ceiling = 100%
2. 当L1四个指标均为-1时，composite必须 ≤ -2，regime = SEVERE_CONTRACTION，ceiling = 40%
3. L1必须恰好包含4个指标结果

### 哨兵行为

4. VIX = 37 且之前为CLEAR → 状态必须变为TRIGGERED，forced_ceiling = 20%
5. VIX Spike已触发后，VIX < 25 仅持续1天 → 状态不应重置为CLEAR（不对称重置）
6. VIX Spike已触发后，VIX < 25 连续3天 → 状态应重置为CLEAR
7. 多个哨兵同时触发时，override_ceiling取最小值（忽略null）

### Envelope计算

8. L1=CONTRACTING(60%) + L2=RISK-ON(70%-85%) + L3=All Clear → target_min ≈ 42%, target_max ≈ 51%
9. L3触发（override=20%）→ 无论L1和L2多乐观，target_max = 20%，模式 = EMERGENCY
10. L1=EXPANSIONARY + L2=STRONG_RISK_ON + L3=Clear → target_max ≥ 90%

### 持仓建议

11. conviction="C" 在 RISK_OFF 体制下的限额必须为0%（应被建议CLOSE）
12. 减仓排序中，C-conviction持仓必须排在S-conviction之前
13. conviction="Hedge" 的持仓不计入风险敞口
14. 当前敞口 70%、target_max 51% → is_overweight = true，excess_dollars > 0

### UI渲染

15. L3任意哨兵触发时，红色Alert Banner必须出现在页面顶部
16. L3全部CLEAR时，Alert Banner不显示
17. 用户未上传持仓时，Position Advisory显示上传入口；上传后显示建议表格
18. Regime Gauge正确展示目标区间色块和（如有）当前仓位标记

### LLM集成

19. LLM叙事生成失败时，scoring tables和gauge仍正常渲染
20. 生成成功时，Executive Summary和Investment Playbook的内容应来自新的regime narrative

---

*文档结束。Coding Agent请基于以上需求进行技术设计和开发。*