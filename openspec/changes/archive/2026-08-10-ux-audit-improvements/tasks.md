## 1. 配置与基础设施（零风险，优先完成）

- [x] 1.1 创建 `.streamlit/config.toml`（如不存在），添加 `[ui] toolbarMode = "minimal"` 隐藏 Deploy 顶栏
- [x] 1.2 在 `main.py` 的 `st.set_page_config` 中将 `page_title` 改为 `"US Markets — Macro Liquidity AI Analyst"`，`page_icon` 改为 `"🇺🇸"`
- [x] 1.3 验证浏览器标签页和侧边栏导航第一项均显示"US Markets"而非"main"

## 2. i18n 补全（src/utils/i18n.py）

- [x] 2.1 在 `i18n.py` 中注册所有进度弹窗相关 key：`progress_all_fresh`、`progress_partial_stale`、`loading_market_data`、`goto_us_markets`、`goto_china_hk`、`regime_context_missing`
- [x] 2.2 注册 Data Management 页面相关 key：`page_data_mgmt_title`、表格列头（`col_dataset`、`col_last_synced`、`col_data_as_of`、`col_duration`、`col_status`）
- [x] 2.3 注册体制评分表格指标行名 key（Layer 1/2 所有指标：`indicator_net_liq_trend`、`indicator_tga_trend`、`indicator_rrp_buffer`、`indicator_policy_rate` 等）
- [x] 2.4 注册行业相关 key：`sector_unknown`、Trading Strategy 信号图例相关 key

## 3. sector_map.py — 行业名标准化映射

- [x] 3.1 新建 `src/utils/sector_map.py`，定义 `SECTOR_MAP_ZH: dict[str, str]`（申万中文）和 `SECTOR_MAP_EN: dict[str, str]`（GICS 英文）
- [x] 3.2 填充当前股票池所有代码的映射：SNDK、300308_SZ、AMD、MU、QCOM、LITE、NVDA、ARM 及其他已有标的
- [x] 3.3 提供 `get_sector(ticker: str, lang: str) -> str` 工具函数，未命中时返回 `t("sector_unknown")`
- [x] 3.4 在 Trading Strategy 页面（`pages/Trading_Strategy.py`）的股票池表格渲染处，将"行业"列改为调用 `get_sector(ticker, lang)`

## 4. 数据拉取层 — 超时与降级

- [x] 4.1 在 `src/data/china_market_fetcher.py` 中为每个 Tushare / AkShare API 调用包装 `concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(...).result(timeout=25)` 超时控制
- [x] 4.2 超时时捕获 `concurrent.futures.TimeoutError`，从 CSV 缓存读取最近一条值并返回 `(value, stale=True)`；若缓存不存在则返回 `(None, stale=True)`
- [x] 4.3 在每个超时处记录日志：`logging.warning("API timeout for %s, using stale cache", metric_name)`
- [x] 4.4 验证：单元测试 mock API 为超时场景，确认返回 stale 值且不抛出异常

## 5. A 股进度弹窗升级（fetch-progress-dialog）

- [x] 5.1 在 `src/ui/china_regime_components.py` 或对应 page 文件中，将现有 `st.status()` 弹窗的每个 fetch 步骤改为：开始前 `status.write("🔄 <步骤名>...")`，完成后更新为 `"✅ <步骤名>"` 或 `"⏰ 超时，使用历史值"`
- [x] 5.2 实现全局 30 秒兜底：若整体加载超过 30 秒，将未完成步骤标记为超时，调用 `status.update(state="complete", ...)`，页面不再 blocking
- [x] 5.3 弹窗折叠标题按 stale 计数更新：0 stale → `t("progress_all_fresh")`；N stale → `t("progress_partial_stale").format(n=N)`
- [x] 5.4 对每个 stale 指标在弹窗内额外显示一行 `⚠️ <指标名>：使用 <last_data_date> 缓存值`
- [x] 5.5 确保所有弹窗文字均通过 `t("key")` 国际化（中英双语）

## 6. 美股主页加载体验

- [x] 6.1 在 `main.py` / `src/ui/app.py` 的美股数据加载部分，用 `st.status()` 容器包裹各数据源调用，逐项展示进度（FRED 净流动性 / VIX / MOVE / SPX / Market Breadth 等）
- [x] 6.2 点击 "Refresh Data" 后，对已渲染数据区域叠加 `st.empty()` 占位 + CSS opacity 降低为 0.4 的遮罩，显示"数据更新中..."提示，加载完成后 `empty.empty()` 恢复
- [x] 6.3 将 `st.file_uploader` 组件移入 `st.expander(t("upload_custom_csv"), expanded=False)` 中折叠，首屏不再直接渲染上传框
- [x] 6.4 将体制评分表格的 `Threshold Hit` 列（及等价列）在 `st.dataframe(column_config=...)` 中显式设置 `width="large"`，确保列内容不被截断

## 7. Trading Strategy 页面 UX 改进

- [x] 7.1 在股票池表格上方添加常驻信号图例栏（`st.markdown` 或 `st.columns` 水平排列）：`🔴 衰竭减仓 · ⚠️ 不追加速 · — 观望 · ✅ 持有/加仓`，图例文字通过 `t("key")` 国际化
- [x] 7.2 将宏观体制缺失提示从纯文字 `st.info()` 改为：`st.info(t("regime_context_missing"))` + 两个 `st.page_link()`（分别跳转 main.py 和 China_HK.py）
- [x] 7.3 核对"当前信号"列中 🔴 / ⚠️ / △ 等符号用法，统一为规范的三级信号体系，修复不一致的三角符号（△ vs ⚠️）

## 8. Data Management 页面移动端适配

- [x] 8.1 在 `pages/Data_Management.py` 页面顶部添加 `_inject_mobile_table_styles()` 函数调用，注入 `st.markdown('<style>.stDataFrame { overflow-x: auto !important; }</style>', unsafe_allow_html=True)`
- [x] 8.2 将 `_inject_mobile_table_styles()` 封装为独立函数，便于版本升级后定点修复
- [x] 8.3 将 Data Management 页面中未通过 `t()` 的硬编码字符串（页面标题、列头、状态标签）统一替换为 `t("key")` 调用

## 9. 验证与测试

- [x] 9.1 运行 `uv run pytest tests/` 确认所有现有单元测试通过（无回归）——178 通过，1 个预存在失败（test_all_positive_expansionary，与本次改动无关）
- [x] 9.2 在桌面端（1280px）手动验证：Deploy 顶栏已隐藏 / 加载进度分项显示 / Threshold Hit 列完整 / 文件上传已折叠 / 行业名统一 / 信号图例可见 / 宏观体制跳转链接可点击
- [x] 9.3 在移动端（375px 或 Chrome DevTools）手动验证：Data Management 表格可横向滚动 / Trading Strategy 页面基本可用
- [x] 9.4 切换语言（中/英），验证所有新增 `t("key")` 均在两种语言下正确显示，无 key 遗漏——静态验证通过，35 个新增 key 在 EN/ZH 均有注册，格式占位符正确
- [x] 9.5 模拟 API 超时场景（可临时在代码中 `time.sleep(30)`），验证 stale 降级路径：弹窗显示超时标注、页面不 blocking、stale 计数正确
