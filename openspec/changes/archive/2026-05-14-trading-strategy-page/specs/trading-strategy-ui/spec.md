## ADDED Requirements

### Requirement: 新增第三 Tab「交易策略」
系统 SHALL 在 `src/ui/app.py` 中将现有 `tab1, tab2 = st.tabs([...])` 改为三个 Tab，第三个 Tab 调用 `render_trading_strategy()`。Tab 标题通过 `t("tab_trading")` 国际化，中文为「交易策略」，英文为「Trading Strategy」。

#### Scenario: Tab renders without breaking existing tabs
- **WHEN** 用户打开应用并切换到「交易策略」Tab
- **THEN** 美股/A股宏观 Tab 正常渲染，不受影响

#### Scenario: i18n tab title switches with language
- **WHEN** 用户在 sidebar 切换语言
- **THEN** Tab 标题随之切换为对应语言

### Requirement: 体制联动横幅
策略页顶部 SHALL 展示当前 A股和美股的体制状态及仓位调整系数横幅。

- A股体制：读取 `st.session_state.get("china_regime_result")`
- 美股体制：读取 `st.session_state.get("us_regime_result")`
- 仓位乘数映射：BULL→1.0（绿色）/ BULL_WATCH→0.75（黄色）/ NEUTRAL→0.85（黄色）/ BEAR→0.30（红色）

#### Scenario: Both regimes available
- **WHEN** session_state 中 china_regime_result 和 us_regime_result 均存在
- **THEN** 横幅显示两个体制状态 + 对应仓位乘数，格式：「A股: BULL_WATCH ⚠️ 仓位上限 75% | 美股: NEUTRAL 仓位上限 85%」

#### Scenario: Regime not yet computed
- **WHEN** session_state 中无体制结果（用户直接访问 Tab3）
- **THEN** 横幅显示「请先加载美股/A股宏观页面以获取体制评分」，以 `st.info` 展示

### Requirement: 股票池汇总表
系统 SHALL 展示过滤后的股票池为表格，每行包含：标的/名称/市场/行业/策略类型/状态/趋势得分/当前信号。

趋势得分用进度条形式展示（0–6 分）。当前信号为简短文字：如「回踩买入 ↓」「整固观望」「不追加速段」「数据待接入」等。

#### Scenario: Populated pool displayed
- **WHEN** 股票池有 trending_up 策略标的且日线数据已缓存
- **THEN** 汇总表展示趋势得分和当前信号，得分 ≥ 4 时信号列绿色高亮

#### Scenario: HK stock placeholder in table
- **WHEN** 汇总表中有 market="港股" 的标的
- **THEN** 趋势得分显示「-」，当前信号显示「数据待接入」

#### Scenario: Non-trending_up strategy placeholder
- **WHEN** 汇总表中有 strategy_type="value" 或 "oscillation" 的标的
- **THEN** 当前信号显示「策略分析即将推出」，不调用趋势分析引擎

### Requirement: 点击标的展开详情面板
系统 SHALL 提供 `st.selectbox` 或行选择机制，选择标的后在页面下方展示详情面板，包含：
1. 趋势确认清单（6 项，✅/❌ 图标）
2. 阶段判断卡片（当前阶段 + 推荐策略文字）
3. 金字塔仓位计算器（建仓次序 selectbox + 仓位建议 + 止损/止盈价格）
4. 衰竭信号提醒（exit_warning=True 时红色 banner）

#### Scenario: Pullback phase with entry recommendation
- **WHEN** 选择一只 trend_phase="pullback" 的标的
- **THEN** 详情面板展示「当前阶段：回踩期 ↓」、推荐策略「策略2：回踩均线买入」和具体入场条件

#### Scenario: Acceleration phase warning
- **WHEN** 选择一只 trend_phase="acceleration" 的标的
- **THEN** 详情面板展示橙色警告「⚠️ 当前处于加速段，勿追入，等待下次回踩」

### Requirement: K线图与技术指标副图
系统 SHALL 为选中标的展示：
- 主图：Plotly Candlestick + MA20（蓝）/ MA60（橙）/ MA120（绿）叠加 + 成交量柱状图（副轴）
- 副图（可展开 expander）：RSI(14) + MACD（主线/信号线/柱状）+ ADX(14)
- 默认展示 120 个交易日，提供 slider 扩展至 250 日

#### Scenario: MA lines rendered on candlestick
- **WHEN** 用户选择有足够历史数据的标的
- **THEN** 主图显示 K 线 + 三条 MA 线 + 成交量，MA 线颜色区分

#### Scenario: Insufficient data fallback
- **WHEN** 标的数据少于 60 行（data_insufficient=True）
- **THEN** 展示折线图（不显示 K 线），显示「数据不足，图表可能不完整」提示

### Requirement: 金字塔仓位计算器交互
系统 SHALL 在详情面板提供交互式仓位计算器：
- 输入：总资金（数字输入）、当前建仓次序（1/2/3/4 selectbox）
- 读取：当前标的所对应市场的体制仓位乘数
- 输出：本次建议买入金额、参考止损价（-6.5%）、目标1价（+25%）、目标2价（+45%）

#### Scenario: Position size adjusted by BEAR regime
- **WHEN** 选择 A股标的，A股体制为 BEAR，总资金=100000，建仓次序=1
- **THEN** 显示「体制警告：当前 A股体制为 BEAR，仓位上限 30%」，建议买入金额 = 100000 × 0.40 × 0.30 = 12000

### Requirement: 一键生成交易计划文本
系统 SHALL 提供"生成交易计划"按钮，点击后输出基于 deal_strategy.md 模板的文字版交易计划。

计划包含：标的确认清单、入场规则、仓位分配、止损规则、止盈规则、纪律红线，均自动填入当前分析数值。

#### Scenario: Generate trade plan
- **WHEN** 用户点击「生成交易计划」按钮
- **THEN** 页面展示格式化的交易计划文本框（可复制），所有价格/仓位数值自动填入

### Requirement: 所有新增 UI 文本国际化
策略页所有用户可见静态文本 SHALL 通过 `t("key")` 调用，同时注册中英文。不得硬编码中文字符串直接渲染。

#### Scenario: Language switch applies to strategy page
- **WHEN** 用户在 sidebar 切换为 English
- **THEN** 策略页所有标签/按钮/提示文字切换为英文
