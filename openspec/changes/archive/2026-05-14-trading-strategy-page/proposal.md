## Why

现有宏观仪表板（美股/A股）提供 Top-down 的市场体制判断，但缺乏 Bottom-up 的个股操作层——用户无法在工具内管理自己的股票池、评估具体标的的入场时机、或按策略框架生成交易计划。Phase 1 补全"看懂市场 → 找到标的 → 制定操作计划"的最后一公里。

## What Changes

- **新增 Tab 3「交易策略」**：与现有美股/A股宏观页面平级，通过 Streamlit tabs 切换
- **股票池管理**：UI 内 CRUD（添加/编辑/删除），按市场×策略类型×行业三维分类，持久化至 `data_cache/stock_pool.json`
- **T-1 日线数据拉取**：A股用 Tushare `pro.daily()`，美股用 yfinance，ETL-on-demand 缓存至 `data_cache/stocks/{ticker}/daily.csv`
- **单边上涨趋势分析引擎**：计算 MA20/60/120、ADX、RSI、MACD、KDJ、成交量比，输出趋势确认清单、阶段判断（突破/回踩/整固/加速/衰竭）、推荐入场策略
- **金字塔仓位计算器**：联动宏观体制评分动态调整仓位上限（BULL→100%，BULL_WATCH→75%，BEAR→30%）
- **体制联动横幅**：策略页顶部展示当前 A股/美股体制状态及对应仓位调整建议
- **新增依赖**：`pandas_ta`（技术指标计算库）

## Capabilities

### New Capabilities

- `stock-pool-management`: 股票池数据模型（StockPoolItem）及 JSON 持久化 CRUD，支持按市场/策略类型/行业分类过滤
- `stock-daily-data`: A股（Tushare）与美股（yfinance）T-1 日线 ETL-on-demand 拉取与缓存
- `trending-up-analysis`: 单边上涨趋势分析引擎——趋势确认清单、阶段判断、入场策略推荐、移动止损/止盈目标计算
- `trading-strategy-ui`: 交易策略页面 UI 组件——体制联动横幅、股票池汇总表、详情面板（K线+副图+仓位计算器+交易计划生成）

### Modified Capabilities

（无现有 spec 级行为变更）

## Impact

- **新增文件**：
  - `src/portfolio/stock_pool.py`
  - `src/data/stock_daily_fetcher.py`
  - `src/analysis/trending_up.py`
  - `src/ui/trading_strategy_components.py`
  - `tests/test_trending_up.py`
- **修改文件**：
  - `src/ui/app.py`：新增 tab3，注册 `render_trading_strategy()`
  - `src/utils/i18n.py`：新增 `tab_trading` 等 i18n key
  - `pyproject.toml`：新增 `pandas-ta` 依赖
- **数据**：新增 `data_cache/stock_pool.json`、`data_cache/stocks/` 目录
- **不影响**：现有美股/A股宏观页面逻辑、体制评分引擎、LLM 报告缓存
