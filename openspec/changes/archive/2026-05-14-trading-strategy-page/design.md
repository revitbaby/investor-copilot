## Context

现有 `src/ui/app.py` 通过两个 Streamlit tab 组织美股/A股宏观仪表板。宏观体制评分结果（`china_regime_result`、`regime_result`）已存入 `st.session_state`，可被新页面复用。`src/portfolio/` 已有持仓数据模型但面向"一次性 CSV 上传"场景，不适合持续维护的股票池。技术指标计算目前不存在，需要引入。

## Goals / Non-Goals

**Goals:**
- 新增第三 Tab，不破坏现有两个 Tab 的任何逻辑
- 股票池持久化：跨 Streamlit 重启不丢失
- 趋势分析逻辑为纯函数，可独立单元测试
- 技术指标数据 ETL 遵循现有 `data_cache/` 缓存约定
- 体制联动：复用 `st.session_state` 中已有的体制结果，不重复计算

**Non-Goals:**
- 港股日线数据接入（Phase 1 只显示"待接入"占位）
- 价值策略、震荡策略分析引擎
- 分钟级/实时数据
- LLM 交易计划生成（Phase 1 生成静态文本模板）
- 回测功能

## Decisions

### D1：技术指标库选 pandas-ta，而非 ta-lib
`ta-lib` 需要 C 编译依赖，在 macOS/Linux 安装复杂且 CI 不友好。`pandas_ta` 纯 Python，直接 `uv add pandas-ta`，覆盖 MA/ADX/RSI/MACD/KDJ/Volume 所有所需指标。备选 `ta`（ta-lib wrapper）因同样的 C 依赖问题排除。

### D2：股票池持久化用 JSON，不用 CSV
股票池条目有嵌套可选字段（`cost_basis`、`shares`、`notes`），JSON 比 CSV 更自然。文件路径 `data_cache/stock_pool.json`，与现有缓存目录保持一致，不纳入 git（`.gitignore` 已包含 `data_cache/`）。

### D3：日线缓存路径 `data_cache/stocks/{ticker}/daily.csv`
与现有 `data_cache/china/` 的 ETL-on-demand 模式一致：先查缓存 → miss 则调 API → 追加写回。ticker 用原始格式（如 `600519.SH`、`AAPL`）做目录名，特殊字符替换为 `_`（如 `600519_SH`）。

### D4：趋势分析引擎为纯函数，输入 DataFrame 输出 dataclass
`TrendingUpAnalyzer.analyze(df: pd.DataFrame, ticker: str) -> TrendAnalysis` 无 I/O 副作用，便于单元测试。数据拉取（`StockDailyFetcher`）与分析逻辑（`TrendingUpAnalyzer`）分层，与现有 `china_market_fetcher` / `china_regime.py` 的分层一致。

### D5：体制联动通过 session_state 读取，不重新计算
宏观页面已将体制结果写入 `st.session_state["china_regime_result"]` 和 `st.session_state["us_regime_result"]`（后者需在 `render_us_dashboard` 中补充写入）。策略页直接读取，根据 `envelope.label` / `regime_label` 映射仓位乘数。若 session_state 无值（用户直接访问 Tab3），显示"请先加载宏观页面"提示。

### D6：UI 采用 st.data_editor 展示汇总表 + expander 展示详情
汇总表用 `st.dataframe`（只读，可点击行）或 `st.selectbox` 选择标的触发详情渲染。CRUD 操作通过 `st.expander("+ 添加/编辑标的")` 展开表单，不污染主视图。删除操作需二次确认（`st.checkbox("确认删除")`）防误操作。

### D7：行业分类采用申万一级（A股）+ GICS 一级（美股）
申万一级（28个）：电子/计算机/通信/医药/消费等，是 A股分析师通行标准。美股用 GICS 一级（11个）：Information Technology / Health Care 等。前端显示时统一展示中文名，存储时保留英文 key 以便未来扩展。Phase 1 sector 字段为自由文本 + 枚举建议，不做强校验。

## Risks / Trade-offs

- **pandas_ta 与 pandas 2.x 兼容性**：pandas_ta 维护活跃度一般，部分方法在 pandas 2.x 下有 DeprecationWarning。→ 固定 pandas_ta 版本，出问题时手动实现 ADX（约 20 行 pandas 代码）。
- **Tushare 积分限制**：`pro.daily()` 单次最多拉 5000 行（约 20 年日线），通常够用；但若同时分析多只股票会触发频率限制。→ ETL-on-demand 缓存 + `time.sleep(0.3)` 间隔，初次拉取慢但后续命中缓存。
- **yfinance 不稳定**：Yahoo Finance 无官方 API，偶发 HTTP 429。→ 同样依赖本地 CSV 缓存，失败时返回 `(df, stale=True)` 而非抛异常，与现有 `fetch_qvix` 处理方式一致。
- **股票池 JSON 并发写入**：Streamlit 多用户场景下 JSON 文件写入可能冲突。→ 本工具为单用户本地工具，不考虑并发；写入前读取最新版本做 merge。
- **K线图性能**：plotly Candlestick 渲染 500+ 根 K 线时前端较重。→ 默认展示 120 个交易日（约 6 个月），提供 slider 扩展至 1 年。

## Migration Plan

1. `uv add pandas-ta` 添加依赖
2. 新建 4 个源文件（无需修改现有分析逻辑）
3. `src/ui/app.py` 末尾 `tab1, tab2 = st.tabs(...)` 改为 `tab1, tab2, tab3 = st.tabs(...)`，新增 `with tab3: render_trading_strategy()`
4. `src/utils/i18n.py` 追加新 i18n key
5. `src/ui/app.py` 中 `render_us_dashboard` 在计算完 `regime_result` 后补写 `st.session_state["us_regime_result"] = regime_result`
6. 回滚：git revert 即可，`data_cache/stock_pool.json` 不影响现有功能

## Open Questions

- `pandas_ta` 的 KDJ 实现与通达信/同花顺的参数是否一致（默认 9,3,3）？A股散户习惯看的 KDJ 参数需与主流看盘软件对齐，否则信号对不上。→ 实现时验证，必要时手动实现。
- 美股 regime_result 当前未写入 session_state，需要在 `render_us_dashboard` 中补充（设计上是小改动，但需确认不引入副作用）。
