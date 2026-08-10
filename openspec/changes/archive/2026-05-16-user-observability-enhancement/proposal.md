## Why

当前应用数据加载过程对用户完全不透明（只有右上角转圈图标），且所有功能集中在单文件 `src/ui/app.py` 的 Tab 布局中，无法扩展第四个"数据管理"页面。用户需要在加载数据时看到执行步骤，以及一个专门的页面来监控各数据源的同步状态与耗时。

## What Changes

- **BREAKING**: 将 `src/ui/app.py` 的 Tab 布局重构为 Streamlit Multipage App，侧边栏自动生成四页导航
- 新增 `pages/` 目录，包含四个页面文件（全球/美股、中国/港股、交易策略、数据管理）
- `_fetch_china_regime_data()` 增加可选 `progress` 参数，在 session cache miss 时通过 `st.status()` 展示逐步执行进度
- `china_market_fetcher.py` 新增 `_record_sync()` context manager，在 API 调用分支（非 CSV cache 命中）记录同步耗时和状态
- `src/data/loader.py` 的三个 DataLoader 方法加入同步计时
- 写入 `data_cache/sync_log.json`，记录每个缓存文件的最后同步时间、耗时、状态、数据截至日期
- 新增 Data Management 页面，展示 A 股细粒度（13 个文件）+ 美股粗粒度（3 个文件）的缓存状态表格，支持手动刷新和清除缓存
- 新增 `docs/data_flow_spec.md`，作为数据链路技术文档（静态）

## Capabilities

### New Capabilities

- `multipage-navigation`: 将应用重构为 Streamlit Multipage App，实现侧边栏四页导航，替代原 Tab 结构
- `fetch-progress-dialog`: 在 session cache miss 时，通过 `st.status()` 展示数据获取的逐步执行进度（A 股体制评分引擎的 8 个 fetch 步骤）
- `data-management-page`: 新增数据管理页面，展示所有缓存文件的同步状态、更新时间、数据截至日期、同步耗时，支持手动刷新/清除缓存
- `sync-telemetry`: 在 fetcher 层记录 API 调用耗时与状态到 `sync_log.json`，供 Data Management 页面消费

### Modified Capabilities

（无现有 spec 需要修改）

## Impact

- **`src/ui/app.py`**: 拆分为 `pages/1_Global_US.py`、`pages/2_China_HK.py`、`pages/3_Trading_Strategy.py`、`pages/4_Data_Management.py`，原文件保留为空壳入口或删除
- **`main.py`**: 简化，移除 Tab 逻辑
- **`src/data/china_market_fetcher.py`**: 新增 `_record_sync()`、`_update_sync_log()`，修改 8 个 `fetch_*` 函数
- **`src/data/loader.py`**: 修改 `fetch_all_data()`、`fetch_sector_etf_data()`、`fetch_china_data()` 加入计时
- **`data_cache/sync_log.json`**: 新文件（运行时生成，不纳入 git）
- **`docs/data_flow_spec.md`**: 新文件（静态技术文档）
- **依赖**: 无新增外部依赖（`st.status()` 在 Streamlit ≥ 1.28 已内置）
