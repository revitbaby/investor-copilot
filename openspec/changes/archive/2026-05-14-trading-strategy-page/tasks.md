## 1. 依赖与基础设施

- [x] 1.1 `uv add pandas-ta` 添加技术指标库依赖，更新 `pyproject.toml`
- [x] 1.2 在 `src/ui/app.py` 中将 `tab1, tab2 = st.tabs(...)` 改为三个 Tab，第三个 Tab 用 `render_trading_strategy()` 占位（函数体只 `pass`）
- [x] 1.3 在 `src/utils/i18n.py` 注册新 i18n key：`tab_trading`、`trading_regime_banner`、`add_stock`、`edit_stock`、`delete_stock`、`confirm_delete`、`generate_trade_plan`、`data_pending`、`strategy_coming_soon`（中英文各一）
- [x] 1.4 在 `src/ui/app.py` 的 `render_us_dashboard()` 中，`regime_result` 计算完成后补写 `st.session_state["us_regime_result"] = regime_result`

## 2. 股票池数据模型与持久化

- [x] 2.1 新建 `src/portfolio/stock_pool.py`，定义 `StockPoolItem` dataclass（ticker, name, market, sector, strategy_type, status, cost_basis, shares, notes, added_date）
- [x] 2.2 实现 `load_stock_pool(path: str) -> list[StockPoolItem]`：读取 JSON，文件不存在/损坏时返回空列表
- [x] 2.3 实现 `save_stock_pool(items: list[StockPoolItem], path: str) -> None`：序列化并原子写入 JSON
- [x] 2.4 实现 `add_item`、`update_item`、`delete_item` 辅助函数，确保 ticker 唯一性校验（大小写不敏感）

## 3. 日线数据 ETL

- [x] 3.1 新建 `src/data/stock_daily_fetcher.py`，实现 `safe_ticker(ticker: str) -> str`（`.` 替换为 `_`）
- [x] 3.2 实现 `_load_daily_cache(safe_ticker: str) -> pd.DataFrame | None`：从 `data_cache/stocks/{safe_ticker}/daily.csv` 读取缓存
- [x] 3.3 实现 `_fetch_ashare_daily(ticker: str, start_date: str, end_date: str) -> pd.DataFrame`：调用 `pro.daily()`，返回标准化 date/open/high/low/close/volume，含 0.3s sleep
- [x] 3.4 实现 `_fetch_us_daily(ticker: str, start_date: str, end_date: str) -> pd.DataFrame`：调用 `yfinance.download()`，返回标准化格式
- [x] 3.5 实现 `fetch_daily_bars(item: StockPoolItem) -> tuple[pd.DataFrame | None, bool]`：ETL-on-demand 主入口，港股直接返回 `(None, True)`，API 失败返回 `(cached, True)`，缓存追加写回

## 4. 趋势分析引擎

- [x] 4.1 新建 `src/analysis/trending_up.py`，定义 `TrendAnalysis` dataclass（所有输出字段：6 项确认信号、trend_score、is_uptrend、trend_phase、recommended_strategy、entry_price、stop_loss_price、target_price_1、target_price_2、trailing_stop_pct、suggested_position_pct、exit_warning、exhaustion_signals、data_insufficient）
- [x] 4.2 实现指标计算辅助函数：`_compute_mas(df)`（MA20/60/120）、`_compute_adx(df)`（ADX14 via pandas_ta）、`_compute_rsi(df)`（RSI14）、`_compute_macd(df)`（MACD via pandas_ta）、`_compute_kdj(df)`（KDJ 9,3,3）、`_compute_volume_ratio(df)`（当日量/MA20量）
- [x] 4.3 实现 `_check_trend_confirmation(df, indicators) -> dict`：计算 6 项布尔确认信号和 trend_score
- [x] 4.4 实现 `_determine_trend_phase(df, indicators) -> str`：按优先级判断 5 个阶段（衰竭>加速>回踩>突破>整固）
- [x] 4.5 实现 `_compute_pyramid_position(entry_order: int, base_pcts: list, regime_multiplier: float) -> float`：金字塔仓位计算
- [x] 4.6 实现 `_check_exhaustion_signals(df, indicators) -> dict`：计算 7 项可自动判断的衰竭信号
- [x] 4.7 实现主函数 `analyze(df: pd.DataFrame, entry_order: int = 1, regime_multiplier: float = 1.0) -> TrendAnalysis`：组合以上所有步骤，None/空 df 时返回 data_insufficient=True

## 5. 单元测试

- [x] 5.1 新建 `tests/test_trending_up.py`，为 `analyze()` 编写测试：正常多头趋势数据（合成）→ `is_uptrend=True`，trend_score=6
- [x] 5.2 测试回踩阶段识别：价格在 MA20 ±3% 且量萎缩 → `trend_phase="pullback"`
- [x] 5.3 测试加速阶段识别：价格偏离 MA20 超 15% + RSI>70 → `trend_phase="acceleration"`
- [x] 5.4 测试 None 输入：`analyze(None)` → `TrendAnalysis(data_insufficient=True)`，无异常
- [x] 5.5 测试金字塔仓位：entry_order=1, regime_multiplier=0.75 → `suggested_position_pct ≈ 0.30`
- [x] 5.6 测试止损/止盈价格：入场价=100 → stop_loss=93.5，target1=125，target2=145
- [x] 5.7 测试 2 项衰竭信号 → `exit_warning=True`；1 项 → `exit_warning=False`
- [x] 5.8 运行 `uv run pytest tests/test_trending_up.py -v` 全部通过

## 6. UI 组件

- [x] 6.1 新建 `src/ui/trading_strategy_components.py`，实现 `render_regime_banner(lang: str) -> dict`：读取 session_state，返回体制乘数 dict，渲染横幅
- [x] 6.2 实现 `render_stock_pool_filters(items: list[StockPoolItem]) -> list[StockPoolItem]`：市场/策略类型/行业/状态四维过滤 selectbox，返回过滤结果
- [x] 6.3 实现 `render_add_edit_form(items, editing_item=None) -> StockPoolItem | None`：expander 内 CRUD 表单，支持添加（editing_item=None）和编辑两种模式，含 ticker 唯一性校验
- [x] 6.4 实现 `render_stock_pool_table(items: list, analysis_map: dict) -> str | None`：展示汇总表（带趋势得分进度条和信号文字），返回用户选中的 ticker
- [x] 6.5 实现 `render_trend_checklist(analysis: TrendAnalysis, lang: str)`：6 项确认清单（✅/❌）+ 趋势得分
- [x] 6.6 实现 `render_phase_card(analysis: TrendAnalysis, lang: str)`：阶段判断卡片 + 推荐策略文字（含加速段橙色警告）
- [x] 6.7 实现 `render_pyramid_calculator(analysis: TrendAnalysis, regime_multipliers: dict, ticker: str, lang: str)`：交互式仓位计算器（总资金输入 + 建仓次序选择 → 输出买入金额/止损价/目标价）
- [x] 6.8 实现 `render_candlestick_chart(df: pd.DataFrame, indicators: dict, ticker: str)`：主图 K 线 + MA20/60/120 + 成交量，120日 slider，含 data_insufficient 降级处理
- [x] 6.9 实现 `render_indicator_subcharts(df: pd.DataFrame, indicators: dict)`：expander 内 RSI/MACD/ADX 副图
- [x] 6.10 实现 `render_trade_plan(analysis: TrendAnalysis, ticker: str, total_capital: float, lang: str)`：基于 deal_strategy.md 模板生成交易计划文本，`st.text_area` 展示可复制内容
- [x] 6.11 实现 `render_exhaustion_warning(analysis: TrendAnalysis, lang: str)`：exit_warning=True 时红色 banner，列出触发的衰竭信号

## 7. 整合到主应用

- [x] 7.1 在 `src/ui/app.py` 中导入新组件，实现完整 `render_trading_strategy()` 函数：加载股票池 → 渲染体制横幅 → 渲染筛选栏 → 渲染 CRUD 表单 → 拉取分析数据 → 渲染汇总表 → 渲染选中标的详情
- [x] 7.2 实现股票池加载/保存的 Streamlit session_state 缓存（避免每次 rerun 重新读 JSON）
- [x] 7.3 对 trending_up 类型标的批量调用 `fetch_daily_bars` + `analyze`，结果缓存在 session_state（key：`analysis_{ticker}_{date}`）
- [x] 7.4 手动测试：添加一只 A股标的（如 600519.SH），验证日线数据拉取、指标计算、K线图、仓位计算器全链路正常
- [x] 7.5 手动测试：添加一只美股标的（如 NVDA），验证 yfinance 拉取链路
- [x] 7.6 手动测试：添加一只港股标的，验证「数据待接入」占位展示
- [x] 7.7 手动测试：切换语言到 English，验证所有新增文本正确切换
<!-- 以上4项为手动测试，需运行 uv run streamlit run main.py 后在浏览器验证 -->
