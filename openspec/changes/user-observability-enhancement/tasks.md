## 1. 同步遥测基础设施（sync-telemetry）

- [x] 1.1 在 `src/data/china_market_fetcher.py` 中新增 `_update_sync_log(filename, duration_s, status)` 函数：读取 `data_cache/sync_log.json`（不存在则初始化为 `{}`），更新对应 key，写回全量 JSON；从对应 CSV 文件最后一行 index 读取 `last_data_date`
- [x] 1.2 在 `china_market_fetcher.py` 中新增 `_record_sync(filename: str)` context manager（使用 `contextlib.contextmanager`）：记录开始时间，`yield`，捕获异常，计算 `duration_s`，调用 `_update_sync_log`，异常时重新 `raise`
- [x] 1.3 在 `fetch_margin_ratio()` 的 API 调用分支（`try:` 块内，`_save_cache` 调用之后）包裹 `with _record_sync("china/margin_ratio.csv"):`
- [x] 1.4 在 `fetch_csi300_pe()` 的 API 调用分支包裹 `_record_sync("china/csi300_pe.csv")`
- [x] 1.5 在 `fetch_cgb10y_yield()` 的 API 调用分支包裹 `_record_sync("china/cgb10y_yield.csv")`
- [x] 1.6 在 `fetch_equity_bond_spread()` 的 API 调用分支包裹 `_record_sync("china/equity_bond_spread.csv")`
- [x] 1.7 在 `fetch_limit_counts()` 的 API 调用分支包裹 `_record_sync("china/limit_counts.csv")`
- [x] 1.8 在 `fetch_northbound_flow()` 的 API 调用分支包裹 `_record_sync("china/northbound_flow.csv")`
- [x] 1.9 在 `fetch_southbound_flow()` 的 API 调用分支包裹 `_record_sync("china/southbound_flow.csv")`
- [x] 1.10 在 `fetch_market_total_amount()` 的 API 调用分支包裹 `_record_sync("china/total_amount.csv")`
- [x] 1.11 在 `fetch_qvix()` 的 API 调用分支包裹 `_record_sync("china/qvix.csv")`
- [x] 1.12 在 `fetch_m2_monthly()` 的 API 调用分支包裹 `_record_sync("china/m2_monthly.csv")`
- [x] 1.13 在 `src/data/loader.py` 的 `fetch_all_data()` cache miss 分支加入相同计时逻辑，key 为 `"macro_data.csv"`（可直接复用或导入 `_record_sync`）
- [x] 1.14 在 `loader.py` 的 `fetch_sector_etf_data()` cache miss 分支加入计时，key 为 `"sector_etf_data.csv"`
- [x] 1.15 在 `loader.py` 的 `fetch_china_data()` cache miss 分支加入计时，key 为 `"china_data.csv"`
- [x] 1.16 将 `data_cache/sync_log.json` 加入 `.gitignore`（运行时生成，不入库）

## 2. 进度弹窗（fetch-progress-dialog）

- [x] 2.1 修改 `_fetch_china_regime_data(today: date, progress=None)` 函数签名，加入可选 `progress` 参数
- [x] 2.2 在函数体内定义内部 helper `def _step(msg: str) -> None: if progress is not None: progress.write(msg)`
- [x] 2.3 在每个 `fetch_*` 调用前插入 `_step(...)` 调用，消息格式为"[emoji] [数据名称] ([数据源])..."，共 8 条（margin、equity_bond_spread、deposit_ratio、limit_counts、northbound、southbound、total_amount、qvix）
- [x] 2.4 在函数末尾，计算 `stale_count = sum([m_stale, eb_stale, dep_stale, lim_stale, nb_stale, sb_stale, amt_stale, qvix_stale])`，如 `progress` 非 None 则调用 `progress.update(label=..., state="complete", expanded=False)`，标签根据 `stale_count` 为 0 或非 0 区分
- [x] 2.5 修改 `render_china_dashboard` 中调用 `_fetch_china_regime_data` 的位置：当 `regime_cache_key not in st.session_state` 时，用 `with st.status("📡 正在获取A股指标数据...", expanded=True) as status:` 包裹，将 `status` 传给 `_fetch_china_regime_data(today, progress=status)`
- [x] 2.6 验证 `progress=None` 时（cache hit 路径）不显示 `st.status()` 弹窗

## 3. Multipage App 导航重构（multipage-navigation）

- [x] 3.1 在项目根目录创建 `pages/` 目录
- [x] 3.2 创建 `pages/2_China_HK.py`：将 `render_china_dashboard()` 及其所有依赖的 import、helper 函数（`_fetch_china_regime_data`、`_cache_mtime`、共享 sidebar 逻辑）迁移至该文件；顶部调用 `load_dotenv()`、`init_i18n()`、`st.set_page_config`（若需要）
- [x] 3.3 创建 `pages/3_Trading_Strategy.py`：将 `render_trading_strategy()` 迁移至该文件
- [x] 3.4 重构 `main.py`（或 `src/ui/app.py` 视入口而定）：移除 `st.tabs()` 和 Tab 分发逻辑，保留全球/美股渲染为默认首页内容；共享 sidebar（语言切换、days_back slider、force_refresh 按钮）保留在此
- [x] 3.5 确认 `st.session_state["language"]`、`st.session_state[regime_cache_key]` 等关键 key 在页面切换后仍然存在（手动测试：在全球/美股页面触发加载后切到中国页面，验证不触发重复计算）
- [x] 3.6 更新 i18n key：为新页面名称添加中英文翻译（`"page_data_management"`、`"page_china_hk"` 等），在 `src/utils/i18n.py` 中注册

## 4. Data Management 页面（data-management-page）

- [x] 4.1 创建 `pages/4_Data_Management.py`，顶部调用 `load_dotenv()`、`init_i18n()`
- [x] 4.2 实现 `_load_sync_log() -> dict` 函数：读取 `data_cache/sync_log.json`，不存在则返回 `{}`
- [x] 4.3 实现 `_classify_status(key, record, today) -> str` 函数：按 spec 中的 5 条规则返回状态图标字符串（✅/❌/⚠️/🔶/⬜）
- [x] 4.4 定义 A 股 13 个文件的显示名称映射 `CHINA_FILES: list[dict]`，包含 `key`（sync_log key）、`display_name`（中文名）、`is_monthly`（月频标志）
- [x] 4.5 定义美股 3 个文件的显示名称映射 `US_FILES: list[dict]`
- [x] 4.6 实现表格渲染：读取 sync_log，结合 CSV 文件 OS mtime 和行数，构建 `pd.DataFrame`，用 `st.dataframe()` 渲染，列：数据集、最后同步时间、数据截至、耗时、状态；耗时 > 30s 时附加"（含历史补全）"
- [x] 4.7 实现"🔄 刷新全部"按钮：加确认 checkbox，确认后调用 `st.cache_data.clear()`，删除今日 mtime 的 A 股细粒度 CSV，`st.rerun()`
- [x] 4.8 实现"🗑 清除今日缓存"按钮：加确认 checkbox，确认后仅删除今日 mtime 的 A 股细粒度 CSV（不清 cache_data），`st.rerun()`
- [x] 4.9 所有用户可见文本通过 `t("key")` 调用，在 `i18n.py` 注册中英文 key（页面标题、列标题、按钮文字、状态说明等）

## 5. 静态数据流文档（docs/data_flow_spec.md）

- [ ] 5.1 创建 `docs/` 目录（若不存在）
- [ ] 5.2 创建 `docs/data_flow_spec.md`，内容包含：数据源目录（API 名、数据集、T+N 延迟、单位注意事项）、缓存文件清单（文件名、列名、更新频率）、数据流链路 Mermaid 图（Remote API → CSV → @st.cache_data → session_state → UI）、已知性能瓶颈（backfill 慢路径、串行 fetch、重复读）、优化建议（并行化、regime 结果磁盘持久化、消除重复 fetch）
