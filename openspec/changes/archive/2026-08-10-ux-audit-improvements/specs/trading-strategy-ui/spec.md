## ADDED Requirements

### Requirement: 行业名称标准化映射
股票池表格的"行业"列 SHALL 统一通过 `src/utils/sector_map.py` 中的静态映射字典输出行业名称，不直接使用原始 API 返回值。映射表提供两个版本：
- `SECTOR_MAP_ZH: dict[str, str]`：申万一级行业中文名（用于中文模式）
- `SECTOR_MAP_EN: dict[str, str]`：GICS 行业英文名（用于英文模式）

键为股票代码（如 `"AMD"`、`"300308_SZ"`），当前股票池所有标的 SHALL 在映射表中有对应条目。未命中的代码 SHALL 显示 `t("sector_unknown")`（中：未分类；英：Uncategorized）而非原始 API 值。

#### Scenario: 美股代码使用英文 GICS 行业名（英文模式）
- **WHEN** 语言为英文，股票池表格渲染行业列，代码为"AMD"
- **THEN** 该行行业列显示"Semiconductors"（GICS 英文标准名），而非"芯片"或"Information Technology"

#### Scenario: A 股代码使用中文申万行业名（中文模式）
- **WHEN** 语言为中文，股票池表格渲染行业列，代码为"300308_SZ"
- **THEN** 该行行业列显示申万一级行业名（如"通信"），而非"光通信"或英文值

#### Scenario: 未知代码降级显示
- **WHEN** 股票池中新增了一个不在映射表中的代码
- **THEN** 该行行业列显示 `t("sector_unknown")` 而非空字符串或原始 API 值

### Requirement: 信号图例常驻表格上方
交易策略股票池表格上方 SHALL 展示一个横向图例栏，说明"当前信号"列所有可能的信号符号含义。图例 SHALL 固定可见（非 expander），格式为：`🔴 减仓  ⚠️ 谨慎  — 观望  ✅ 持有/加仓`。图例文字通过 `t("key")` 国际化。

#### Scenario: 图例常驻显示不可折叠
- **WHEN** 用户访问交易策略页
- **THEN** 表格上方始终显示图例栏，无需展开任何折叠组件即可看到

#### Scenario: 中文模式下图例显示中文标签
- **WHEN** 语言为中文
- **THEN** 图例显示"🔴 衰竭减仓 · ⚠️ 不追加速 · — 观望 · ✅ 持有加仓"

### Requirement: 宏观体制缺失时提示包含可跳转链接
当宏观体制上下文（`us_regime_result` / `china_regime_result`）尚未加载时，提示文字 SHALL 包含可点击的页面跳转链接，而非仅文字说明。

链接格式：`st.page_link("main.py", label=t("goto_us_markets"), icon="🇺🇸")` 和 `st.page_link("pages/China_HK.py", label=t("goto_china_hk"), icon="🇨🇳")`，在 `st.info()` 下方独立渲染。

#### Scenario: 体制未加载时显示含跳转链接的提示
- **WHEN** `st.session_state` 中既无 `us_regime_result` 也无 `china_regime_result`，用户直接访问交易策略页
- **THEN** 页面显示 `st.info(t("regime_context_missing"))` + 两个 `st.page_link` 按钮，分别指向美股和 A股页面

#### Scenario: 任一体制已加载时不显示缺失提示
- **WHEN** `us_regime_result` 存在（即用户已访问过美股页面）
- **THEN** 体制缺失提示不显示，横幅正常展示已有的体制状态

## MODIFIED Requirements

### Requirement: 股票池汇总表
系统 SHALL 展示过滤后的股票池为表格，每行包含：标的/名称/市场/行业/策略类型/状态/趋势得分/当前信号。

行业列 SHALL 通过 `sector_map.py` 映射，按当前语言返回标准化行业名称（中文申万 / 英文 GICS），不再使用原始 API 返回值。

趋势得分用进度条形式展示（0–6 分）。当前信号为简短文字：如「回踩买入 ↓」「整固观望」「不追加速段」「数据待接入」等。

#### Scenario: 行业列统一显示标准化名称
- **WHEN** 股票池表格渲染，语言为英文，标的 MU、QCOM、AMD 均在 sector_map 中
- **THEN** 三只股票的行业列均显示 GICS 英文标准名（如"Semiconductors"），无中英混用

#### Scenario: Populated pool displayed
- **WHEN** 股票池有 trending_up 策略标的且日线数据已缓存
- **THEN** 汇总表展示趋势得分和当前信号，得分 ≥ 4 时信号列绿色高亮

#### Scenario: HK stock placeholder in table
- **WHEN** 汇总表中有 market="港股" 的标的
- **THEN** 趋势得分显示「-」，当前信号显示「数据待接入」

#### Scenario: Non-trending_up strategy placeholder
- **WHEN** 汇总表中有 strategy_type="value" 或 "oscillation" 的标的
- **THEN** 当前信号显示「策略分析即将推出」，不调用趋势分析引擎
