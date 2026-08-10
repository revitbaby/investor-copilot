## Context

当前应用存在三类 UX 债务：

1. **加载透明度**：Streamlit `st.spinner()` / 两行纯文字是唯一的加载反馈，当外部 API（Tushare / AkShare / FRED）耗时超过 5 秒时，用户面对空白页无法判断系统是否正常工作。China HK 页面在实测中持续 loading 未完成，无超时降级。

2. **数据一致性**：股票行业分类来源混用（部分股票用 AkShare 中文行业名，部分用 Yahoo Finance GICS 英文名）；体制评分表格列宽未设置导致 Threshold Hit 列截断；i18n 仅覆盖页面标题/按钮，未覆盖表格内指标行名。

3. **视觉/导航细节**：Streamlit 默认顶栏（Deploy 按钮）暴露；首页文件上传组件占据核心位置；导航首项无语义；交易策略页信号图例缺失。

变更跨越 4 个文件层（UI / 数据拉取 / i18n / 配置），需协调改动。

## Goals / Non-Goals

**Goals:**
- 所有数据拉取步骤在 UI 层可见（分项进度 + 状态图标）
- API 超时 ≤ 30s；超时后展示 stale 缓存值 + 标注，而非 blocking
- 行业名称在全应用内统一（选择中文申万分类，英文模式下使用 GICS 英文名）
- 体制评分表格列宽固定，Threshold Hit 列完整显示
- 移动端（375px）Data Management 表格可横向滚动
- 交易策略信号图例常驻表格上方
- `.streamlit/config.toml` 隐藏 Streamlit 顶栏
- i18n 补全：指标行名 + 行业名

**Non-Goals:**
- 重构整体状态管理架构（保持现有 `st.session_state` 模式）
- 引入新的外部 API 数据源
- 修改分析引擎逻辑（纯 UI 层 + 数据层边界修改）
- 实现真正的后台任务队列（仍在 Streamlit 同步执行模型内）

## Decisions

### D1：分项加载进度 — 使用生成器回调模式，而非后台线程

**选择**：在 `china_market_fetcher.py` 各数据拉取函数中添加可选 `on_progress: Callable[[str, str], None]` 回调参数；UI 层通过 `st.status()` 容器（Streamlit 1.28+）逐项更新状态。

**备选**：`threading` + `st.experimental_rerun` 轮询 → 增加复杂度，Streamlit 并发模型不稳定，放弃。

**理由**：Streamlit 是同步执行模型，生成器/回调方式无需改变执行流，仅在每个数据拉取完成后通知 UI 组件更新 status item，兼容现有 ETL-on-demand 架构。

### D2：超时降级 — 函数级 timeout 包装器

**选择**：在 `china_market_fetcher.py` 的每个 API 调用外层加 `signal.alarm` 或 `concurrent.futures.ThreadPoolExecutor` 的 `timeout` 参数（Python `signal` 仅支持主线程，优先用 `ThreadPoolExecutor(max_workers=1).submit().result(timeout=N)`）；超时时返回 `(last_known_value, stale=True)`（现有 stale 模式已有基础）。

**理由**：已有返回 `(value, stale: bool)` 的接口约定（CLAUDE.md 约束），只需补充超时机制，UI 层无需大改，stale=True 时显示 `⚠️` 标注。

### D3：行业名标准化 — 静态映射表，数据层处理

**选择**：在 `src/portfolio/` 或新建 `src/utils/sector_map.py` 维护 `TICKER_TO_SECTOR_ZH: dict[str, str]` 和 `TICKER_TO_SECTOR_EN: dict[str, str]` 两份静态映射，按 `st.session_state["language"]` 选择。A 股代码使用申万一级行业，美股使用 GICS。

**备选**：运行时调用 AkShare / yfinance 行业接口动态获取 → 增加 API 调用、引入延迟，放弃。

**理由**：现有股票池规模小（< 20 只），静态映射维护成本低，完全可控，不引入新的网络依赖。

### D4：移动端表格 — CSS 注入横向滚动

**选择**：通过 `st.markdown('<style>.stDataFrame { overflow-x: auto; }</style>', unsafe_allow_html=True)` 注入 CSS，使 Data Management 表格在小屏下可横向滚动。

**备选**：重构为卡片列表 → 改动量大，且 Streamlit 的 dataframe 组件已内置响应式支持，只需暴露 overflow，放弃。

**理由**：最小改动成本，不影响桌面端显示，快速消除移动端截断问题。

### D5：Streamlit 顶栏 — config.toml

**选择**：在 `.streamlit/config.toml` 添加：
```toml
[ui]
toolbarMode = "minimal"
```

**理由**：官方支持的配置方式，无需修改任何 Python 代码，零风险。

### D6：体制评分表格列宽 — `column_config` 显式设置

**选择**：在渲染 Layer 1/2 表格的 `st.dataframe()` 调用中，通过 `column_config={"Threshold Hit": st.column_config.TextColumn(width="large")}` 固定列宽，或改用 `st.dataframe(use_container_width=True)` 配合列比例设置。

**理由**：Streamlit 原生 API，无需自定义组件。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| `st.status()` 在 Streamlit < 1.28 版本不可用 | 检查 `streamlit.__version__`，降级为 `st.expander` + `st.info` 组合；或直接固定依赖版本 ≥ 1.28 |
| `ThreadPoolExecutor` timeout 在 Tushare 连接池内可能留下僵尸线程 | 设置 daemon=True；记录 timeout 日志；30s 超时后的僵尸线程不影响主程序 |
| 静态行业映射维护负担 | 仅覆盖现有 stock_pool 中的股票，新增股票时 PR checklist 要求补充映射 |
| CSS 注入可能因 Streamlit 版本升级失效 | 将 CSS 封装为 `inject_mobile_styles()` 函数，便于版本升级后定点修复 |
| `toolbarMode = "minimal"` 在 Streamlit Community Cloud 部署时行为不同 | 本地开发和生产环境均测试；minimal 模式仍保留 Stop 按钮（可接受） |

## Migration Plan

变更不涉及数据 schema 变更，无需数据迁移：

1. 在 feature branch 上按模块顺序实施（配置 → i18n → 数据层 → UI 层）
2. 每个模块改完后运行 `uv run pytest` 确认无回归
3. 手动在浏览器验证：加载进度、stale 降级、移动端表格、信号图例
4. Rollback：revert 对应文件即可，无持久化副作用

## Open Questions

- `st.status()` 是否已在当前 Streamlit 版本（需确认 `requirements.txt` 中版本号）可用？如不可用，需决定降级方案。
- 交易策略页的"宏观体制依赖"状态，长期是否应改为自动触发加载，而非提示用户手动跳转？（当前提案仅加跳转链接，不改加载逻辑）
