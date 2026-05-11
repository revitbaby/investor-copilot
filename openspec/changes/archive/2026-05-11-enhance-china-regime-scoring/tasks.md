## 1. 数据获取层（Tushare 新接口）

- [x] 1.1 确认 Tushare token 订阅级别，验证以下接口可用：`pro.margin`、`pro.index_dailybasic`、`pro.cn_bond_price`（或 yield curve 等效接口）、`pro.stk_limit`、`pro.cn_m`、`pro.moneyflow`、`pro.moneyflow_hsgt`（北向资金，替代 AkShare 渠道）
- [x] 1.2 确认是否支持 QVIX 相关接口（`pro.opt_daily` 或等效），记录结果并更新 design.md Open Questions
- [x] 1.3 确认 DR007 数据是否继续使用 AkShare 还是迁移至 Tushare 宏观接口，避免重复拉取
- [x] 1.4 在 `src/data/` 下创建（或扩展）`china_market_fetcher.py`，实现 `fetch_margin_ratio(date) -> pd.Series`（融资融券余额 + A 股总市值 → 比率），带 CSV 缓存（`data_cache/china/margin_ratio.csv`）
- [x] 1.5 实现 `fetch_csi300_pe(date) -> float`（沪深300 PE TTM，T-1 滞后），带缓存（`data_cache/china/csi300_pe.csv`）
- [x] 1.6 实现 `fetch_cgb10y_yield(date) -> float`（10 年期国债收益率），带缓存（`data_cache/china/cgb10y_yield.csv`）
- [x] 1.7 实现 `fetch_equity_bond_spread(date) -> float`（基于 PE TTM 和 CGB yield 计算，T-1 PE 滞后），带缓存（`data_cache/china/equity_bond_spread.csv`）
- [x] 1.8 实现 `fetch_limit_counts(date) -> dict`（当日涨停 + 跌停数量 + ZT/DT 比率），带缓存（`data_cache/china/limit_counts.csv`），含 < 5 的完整性检查
- [x] 1.9 实现 `fetch_northbound_flow(date) -> dict`（北向净买入额 + 5 日累计，via Tushare `pro.moneyflow_hsgt`），带缓存（`data_cache/china/northbound_flow.csv`）；废弃原有 AkShare 北向接口调用
- [x] 1.10 实现 `fetch_southbound_flow(date) -> dict`（南向净买入额 + 20 日均值 + σ 偏差），带缓存（`data_cache/china/southbound_flow.csv`）
- [x] 1.11 实现 `fetch_m2_monthly() -> pd.Series`（月度 M2 存量），带缓存（`data_cache/china/m2_monthly.csv`），中月份无数据时返回最新已知值 + `data_month` 字段
- [x] 1.12 实现 `fetch_market_total_amount(date) -> float`（全市场日成交额），带缓存（`data_cache/china/total_amount.csv`）
- [x] 1.13 实现 `fetch_deposit_ratio(date) -> float`（M2 ÷ A 股总市值），带月频缓存（`data_cache/china/deposit_ratio.csv`）
- [x] 1.13 为所有新 fetcher 添加 API 失败处理：超时/配额限制时返回 last-known-good 值并附 `data_stale=True` 标志，不使 pipeline 崩溃

## 2. 分析引擎 — 类型定义与辅助工具

- [x] 2.1 在 `src/analysis/china_regime.py`（新建或扩展）中定义 dataclass / TypedDict：`ChinaL1Signals`、`ChinaL1Result`、`ChinaL2Result`、`ChinaSentinelState`、`ChinaEnvelopeResult`、`ChinaRegimeResult`
- [x] 2.2 实现 `load_china_sentinel_state() -> ChinaSentinelState`，从 `data_cache/china_sentinel_state.json` 读取状态；文件损坏或不存在时初始化全 CLEAR
- [x] 2.3 实现 `save_china_sentinel_state(state: ChinaSentinelState)`，将状态写入 `data_cache/china_sentinel_state.json`

## 3. 分析引擎 — Layer 1 评分

- [x] 3.1 实现 `score_dr007_signal(dr007: float, omo_rate: float) -> int`：DR007 低于 OMO → +1，高于 → -1，否则 0
- [x] 3.2 实现 `score_m1_yoy_signal(m1_yoy: float | None) -> int`：M1 同比正且加速 → +1，持续负 → -1，否则 0；None → 0
- [x] 3.3 实现 `score_m1_m2_spread_signal(spread: float | None) -> int`：差值收窄/转正 → +1，持续扩大负值 → -1；None → 0
- [x] 3.4 实现 `score_tsf_signal(tsf_yoy: float | None) -> int`：社融同比加速 → +1，减速 → -1；None → 0
- [x] 3.5 实现 `compute_china_layer1(signals: ChinaL1Signals) -> ChinaL1Result`，合并 4 个信号得分，映射为 Regime（EXPANSIONARY / NEUTRAL / CONTRACTING）和 Position Ceiling（80% / 60% / 40%）
- [x] 3.6 为 Layer 1 所有函数编写单元测试（覆盖全牛市、全熊市、混合信号、缺失数据场景）

## 4. 分析引擎 — Layer 2 体制分类

- [x] 4.1 实现 `classify_equity_bond_signal(spread_pct: float) -> Literal["UNDERVALUED", "NEUTRAL", "OVERVALUED"]`（阈值：> 3% 低估，< 1% 高估）
- [x] 4.2 实现 `classify_margin_signal(ratio_pct: float) -> Literal["OVERHEATED", "NORMAL", "COLD"]`（阈值：> 2.5% 过热，< 1.5% 冷淡）
- [x] 4.3 实现 `classify_qvix_signal(qvix: float | None) -> Literal["HIGH", "NORMAL", "LOW"] | None`（> 30 高，< 15 低；None 时返回 None）
- [x] 4.4 实现 `compute_northbound_utilization_adjustment(northbound_5d_cumulative: float | None) -> float`：5 日累计净流入 > 20 亿 → +0.05；< -20 亿 → -0.05；否则 0；None → 0
- [x] 4.5 实现 `classify_china_regime(equity_bond_signal, margin_signal, qvix_signal, northbound_adjustment) -> ChinaL2Result`，根据信号组合映射四态体制和 Utilization Rate 区间，应用北向资金调整；QVIX 缺失时降级为 2 信号分类
- [x] 4.6 为 Layer 2 分类函数编写单元测试（覆盖 VALUE_BULL、SENTIMENT_BULL、PANIC_BOTTOM、OVERVALUATION_RISK、NEUTRAL、QVIX 缺失、北向流入/流出/缺失）

## 5. 分析引擎 — Layer 3 哨兵

- [x] 5.1 实现 `evaluate_limit_up_heat(count: int | None, state: SentinelEntry) -> SentinelEntry`：count > 200 → TRIGGERED；count < 5（数据异常）→ 维持 CLEAR；3 日 hold-down 逻辑
- [x] 5.2 实现 `evaluate_limit_down_panic(count: int | None, state) -> SentinelEntry`：count > 50 → TRIGGERED；3 日 hold-down
- [x] 5.3 实现 `evaluate_zt_dt_ratio(zt: int | None, dt: int | None, state) -> SentinelEntry`：比率 > 10 或 < 0.2 → TRIGGERED；3 日 hold-down
- [x] 5.4 实现 `evaluate_southbound_surge(net_buy: float | None, sigma_dev: float | None, state) -> SentinelEntry`：|σ 偏差| > 2 → TRIGGERED；3 日 hold-down
- [x] 5.5 实现 `evaluate_volume_spike(amount: float | None, ma20: float | None, state) -> SentinelEntry`：amount > ma20 × 1.5 → TRIGGERED；3 日 hold-down
- [x] 5.6 实现 `evaluate_china_sentinels(market_data, current_state) -> ChinaSentinelState`，串联调用上述 5 个评估函数，返回更新后的完整状态
- [x] 5.7 为 Layer 3 函数编写单元测试（覆盖触发、hold-down、自动重置、数据缺失场景）

## 6. 分析引擎 — Envelope 合成与历史记录

- [x] 6.1 实现 `compute_china_envelope(l1_result, l2_result, l3_state) -> ChinaEnvelopeResult`：normal mode = Ceiling × Utilization；multi-sentinel emergency = Ceiling × 50%；单哨兵降低 10%–15%
- [x] 6.2 为 `compute_china_envelope` 编写单元测试（覆盖 normal、单哨兵、多哨兵 emergency）
- [x] 6.3 实现 `compute_china_regime(data: ChinaInputData) -> ChinaRegimeResult`，内部依次调用 Layer 1、2、3 和 Envelope 函数，返回 `ChinaRegimeResult`
- [x] 6.4 实现 `write_china_regime_snapshot(date, l1_result, l2_result, l3_state, envelope, csi300_close)`，追加写入 `data_cache/china_regime_history.csv`；文件不存在时自动创建

## 7. 指标计算辅助函数

- [x] 7.1 实现 `compute_margin_ratio_distance(current: float, references: dict) -> dict`，计算最新值与 2015 / 2021 历史高点的距离并输出描述文字（"很远 / 较远 / 较近 / 接近"）
- [x] 7.2 实现 `compute_equity_bond_spread_description(spread: float) -> str`，返回估值解释文字（"A 股低估，配置价值高" / "中性" / "A 股相对高估"）
- [x] 7.3 实现 `get_deposit_ratio_description(ratio: float) -> str`，返回潜在入市资金解释文字

## 8. i18n 文本扩展

- [x] 8.1 在 `src/utils/i18n.py` 中添加以下新 key 的中英文翻译：China Layer 1/2/3 标题、四种体制名称、三个指标卡片标题、哨兵名称、警告横幅模板文字、数据时效说明、距离描述词（"很远 / 较远 / 较近 / 接近"）

## 9. Dashboard — 新增 UI 组件

- [x] 9.1 实现 `render_margin_ratio_card(margin_data, language)`：含 Plotly 折线图（叠加 2015/2021 参考水位虚线）、最新值卡片、距离描述文字
- [x] 9.2 实现 `render_equity_bond_spread_card(spread_data, language)`：含 Plotly 折线图（叠加 2008/2014/2022 参考水位）、最新值卡片、估值解释文字
- [x] 9.3 实现 `render_deposit_ratio_card(deposit_data, language)`：含 Plotly 月频散点图（叠加历史参考水位）、最新值卡片、潜在资金描述
- [x] 9.4 实现 `render_data_freshness_note(data_dates: dict, language)`：在三个指标卡片下方渲染数据来源和更新日期小字
- [x] 9.5 实现 `render_china_scoring_table(regime_result: ChinaRegimeResult, language)`：三层评分表，信号状态颜色编码（绿/黄/红），含每层推理说明
- [x] 9.6 实现 `render_china_envelope_gauge(envelope: ChinaEnvelopeResult, language)`：Gauge 仪表盘显示 min%–max%，emergency mode 时橙红色渲染
- [x] 9.7 实现 `render_china_sentinel_banner(l3_state: ChinaSentinelState, language)`：哨兵触发时显示橙色/红色警告横幅（列出所有触发哨兵），全 CLEAR 时返回 None（不渲染）
- [x] 9.8 实现 `render_china_regime_timeline(history_df: pd.DataFrame, language)`：12 个月 A 股体制色带时间轴（VALUE_BULL=深绿，SENTIMENT_BULL=浅绿，NEUTRAL=黄，PANIC_BOTTOM=橙，OVERVALUATION_RISK=红）
- [x] 9.9 更新北向资金图表组件，在图表标题或图例附近添加"实时披露已于 2024-08 停止"橙色提示文字

## 10. Dashboard — 集成到 China 模块

- [x] 10.1 在 China 模块主渲染函数中，在现有内容前添加：调用所有新 fetcher → 调用 `compute_china_regime()` → 保存 sentinel state 和 history snapshot
- [x] 10.2 在 China 模块顶部（条件显示）插入 `render_china_sentinel_banner()`
- [x] 10.3 在 China 模块顶部渲染三个指标卡片（`render_margin_ratio_card`、`render_equity_bond_spread_card`、`render_deposit_ratio_card`）和数据时效说明
- [x] 10.4 在 China 模块中部插入 `render_china_scoring_table()` 和 `render_china_envelope_gauge()`
- [x] 10.5 在 China 模块底部插入 `render_china_regime_timeline()`
- [x] 10.6 将 `ChinaRegimeResult` 存入 `st.session_state["china_regime_result"]` 供后续 LLM 集成使用
- [ ] 10.7 在 Streamlit 中手动测试 China 模块完整渲染流程（黄金路径：所有数据正常获取）
- [ ] 10.8 测试边缘情况：QVIX 不可用、某个 Tushare 接口失败（last-known-good fallback）、初次部署无历史记录

## 11. 最终验收

- [x] 11.1 确认所有新 UI 文本均通过 `t()` 调用，中英文两种语言下渲染正确
- [x] 11.2 确认所有新 Tushare fetcher 在 `data_cache/china/` 下写入缓存，第二次调用不重复请求 API
- [x] 11.3 运行所有单元测试，确认 Layer 1/2/3 测试通过
- [x] 11.4 确认 `china_sentinel_state.json` 和 `china_regime_history.csv` 在应用重启后状态正确恢复
- [x] 11.5 确认北向资金图表显示停止披露提示，历史数据仍正常展示
