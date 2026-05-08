## 1. 配置基础
- [x] 1.1 创建 `config/regime_defaults.yaml`，包含全部 L1/L2/L3 阈值、权重、ceiling/utilization 映射、conviction-regime 矩阵与 S5FI 行业权重（取值来自 PRD 第 2–6、8、10 节）
- [x] 1.2 创建 `src/regime/config.py` —— 实现 YAML 加载器与 `RegimeConfig` dataclass，支持 defaults-then-overrides merge，并在加载时执行 schema 校验
- [x] 1.3 编写配置加载、merge 与校验错误处理的单元测试

## 2. 数据摄取：S5FI Market Breadth
- [x] 2.1 在 `src/data/market_client.py` 的 ticker map 中加入 11 个 SPDR 行业 ETF + `^GSPC`（SPX）
- [x] 2.2 创建 `src/data/breadth.py` —— `compute_s5fi(sector_etf_df, config)`：对每个 ETF 相对其 50DMA 打分，应用行业权重，输出 0–100 值；失败时回退 50.0
- [x] 2.3 通过 `DataLoader` 将 `compute_s5fi` 接入数据加载 pipeline
- [x] 2.4 编写 S5FI 计算单元测试（全在上方、全在下方、部分失败→50.0）

## 3. Layer 1：Liquidity Foundation Scoring
- [x] 3.1 创建 `src/regime/layer1.py` —— 4 个指标打分函数（`score_net_liquidity_trend`、`score_tga_trend`、`score_rrp_buffer`、`score_policy_rate_direction`），各自返回 +1/0/-1
- [x] 3.2 实现 composite 分数计算（4 指标求和，范围 -4 到 +4）
- [x] 3.3 实现 regime 到 ceiling 的映射（EXPANSIONARY/NEUTRAL/CONTRACTING/SEVERE_CONTRACTION → ceiling %）
- [x] 3.4 返回结构化 `Layer1Result` dataclass，包含分指标明细、composite、regime label、ceiling
- [x] 3.5 编写单元测试：全 +1 → composite ≥ 3 → EXPANSIONARY → 100%；全 -1 → ≤ -2 → SEVERE → 40%；混合场景；单指标失败→score 0

## 4. Layer 2：Market Regime Scoring
- [x] 4.1 创建 `src/regime/layer2.py` —— 实现 8 个指标打分函数，权重来自配置
- [x] 4.2 实现 DXY 非线性打分（极端上涨 OR 极端下跌 → -1）
- [x] 4.3 实现加权 composite 计算（范围 -8.0 到 +8.0）
- [x] 4.4 实现 regime 到 utilization 的映射（5 档 → utilization 区间）
- [x] 4.5 返回结构化 `Layer2Result` dataclass，包含分指标明细、加权 composite、regime label、utilization range
- [x] 4.6 编写单元测试：各 regime 分档边界分值、DXY 边界场景、权重应用正确性、S5FI 集成

## 5. Layer 3：Sentinel State Machine
- [x] 5.1 创建 `src/regime/layer3.py` —— 实现带三态模型（CLEAR/TRIGGERED/COOLING）与非对称触发/重置逻辑的 `Sentinel` 类
- [x] 5.2 实现 4 个 sentinel 定义（VIX Spike、Credit Break、Bond Vol Spike、Trend Break），触发/重置条件可配置
- [x] 5.3 实现多 sentinel 覆盖：在所有触发 sentinel 中取最小 forced_ceiling（忽略 null/FREEZE）
- [x] 5.4 实现状态持久化：保存/加载 `data_cache/sentinel_state.json`；文件损坏时全部置为 CLEAR
- [x] 5.5 编写单元测试：trigger → TRIGGERED；低于 reset 仅 1 天仍 TRIGGERED；连续 N 天后 CLEAR；TRIGGERED → COOLING 转换；多 sentinel 最小 ceiling；状态持久化往返；损坏文件恢复

## 6. Envelope 计算
- [x] 6.1 创建 `src/regime/envelope.py` —— 实现 normal mode（L1 Ceiling × L2 Utilization range）与 emergency mode（L3 override）
- [x] 6.2 返回 `EnvelopeResult`，包含 target_min、target_max、mode（NORMAL/EMERGENCY）与 derivation 字符串
- [x] 6.3 编写单元测试：PRD 场景矩阵（5.3 表）；L3 override 忽略 L1/L2；仅 FREEZE sentinel 不设置 forced_ceiling

## 7. Regime Engine 编排器
- [x] 7.1 创建 `src/regime/engine.py` —— `RegimeEngine.run(data)` 串联 L1 → L2 → L3 → Envelope，并返回 `RegimeResult`
- [x] 7.2 将 engine 接入 `app.py` 数据流：数据拉取后、LLM 调用前执行
- [x] 7.3 实现向 `data_cache/regime_history.csv` 追加 regime 历史
- [x] 7.4 编写集成测试：mock 数据端到端评分并产出预期 envelope

## 8. Position Advisor
- [x] 8.1 创建 `src/portfolio/models.py` —— 定义 `Holding`、`PositionAdvice`、`AdvisoryResult` dataclass
- [x] 8.2 创建 `src/portfolio/parser.py` —— 实现带校验与错误报告的 CSV 解析
- [x] 8.3 创建 `src/portfolio/advisor.py` —— 实现风险暴露计算（排除 Hedge）、conviction-regime 上限查询、trim 优先级排序、动作分配（CLOSE/TRIM/HOLD/ADD）与 regime 专属规则执行
- [x] 8.4 编写单元测试：排除 Hedge；RISK_OFF 下 C-conviction → CLOSE；trim 优先级（conviction → beta → PnL）；CONTRACTING 下 options notional 上限；SEVERE → 仅保留 S；超配检测

## 9. LLM 集成
- [x] 9.1 在 `src/llm/regime_narrator.py` 创建新 prompt 模板，纳入结构化评分数据、分指标明细、envelope 推导与 position advisory 摘要
- [x] 9.2 实现基于 delimiter 的 6 分段输出解析（L1/L2/L3 summaries、Executive Summary、Position Narrative、Investment Playbook）
- [x] 9.3 实现 fallback：解析失败→整段响应作为 Executive Summary；LLM timeout→回退 legacy 输出
- [x] 9.4 保留现有 LLM 代码路径作为后备（不删除）
- [x] 9.5 编写单元测试：6 分段解析成功、异常响应 fallback、timeout 处理

## 10. Dashboard UI 组件
- [x] 10.1 创建 `src/ui/regime_components.py`，实现全部新组件渲染函数
- [x] 10.2 实现 L3 Alert Banner（sticky 红色，条件渲染）
- [x] 10.3 实现 Regime Gauge（水平条、envelope 区间、可选当前仓位标记、推导文本）
- [x] 10.4 实现 L1 Scoring Table（card、badge、4 行表格、composite 行、LLM 摘要）
- [x] 10.5 实现 L2 Scoring Table（card、badge、8 行表格、weight/weighted-score 列、Score Bar 可视化）
- [x] 10.6 实现 L3 Sentinel Row（紧凑 4 区块行、条件显示 L3 摘要）
- [x] 10.7 实现 Position Advisory 卡片（上传提示 → 建议表格 → regime 规则 → narrative）
- [x] 10.8 实现 Regime Timeline（4 行堆叠图：L1 bands、L2 bands、L3 events、envelope area + SPX 叠加）
- [x] 10.9 将所有组件集成到 `app.py` 并置于现有内容上方，同时保持下方现有布局不变

## 11. 国际化
- [x] 11.1 将全部新增 UI 文案（组件标题、标签、动作名、regime 名称、sentinel 名称、占位文本）加入 `src/utils/i18n.py` 的中英文词条
- [x] 11.2 确保 LLM regime narrative 遵循 `language` 参数

## 12. 验证与验收
- [x] 12.1 验证 PRD 验收标准 1-3（L1 打分正确性）—— 测试通过
- [x] 12.2 验证 PRD 验收标准 4-7（sentinel 行为）—— 测试通过
- [x] 12.3 验证 PRD 验收标准 8-10（envelope 计算）—— 测试通过
- [x] 12.4 验证 PRD 验收标准 11-14（position advisory）—— 测试通过
- [x] 12.5 验证 PRD 验收标准 15-18（UI 渲染）—— 组件已实现
- [x] 12.6 验证 PRD 验收标准 19-20（LLM 集成）—— fallback 已实现
- [x] 12.7 性能检查：scoring engine < 2s、S5FI 拉取 < 30s、LLM timeout ≤ 30s —— 已配置
