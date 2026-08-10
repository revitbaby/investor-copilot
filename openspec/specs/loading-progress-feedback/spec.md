# Loading Progress Feedback Specification

## Purpose
描述美股主页分项加载进度展示，以及 A 股数据拉取的 25 秒 API 超时与 30 秒页面兜底机制。
## Requirements

### Requirement: 美股主页分项加载进度展示
美股主页（`main.py`）SHALL 在数据加载期间，通过 `st.status()` 容器展示各数据源的逐项加载状态，而非仅显示两行纯文字。每个数据源（FRED 净流动性、VIX、MOVE、SPX 等）开始加载时 SHALL 显示"🔄 正在获取..."，完成后更新为"✅ 完成"。

#### Scenario: 首次加载时显示分项进度
- **WHEN** 用户首次访问美股主页（session_state 中无当天数据缓存）
- **THEN** 页面内容区上方出现展开的 `st.status()` 容器，标题为 `t("loading_market_data")` 对应文字，内部逐项显示各数据源加载状态

#### Scenario: 所有数据加载完成后状态自动折叠
- **WHEN** 所有数据源加载完毕（无论是否有 stale 项）
- **THEN** `st.status()` 状态切换为 `state="complete"`，容器自动折叠，主内容区正常渲染

#### Scenario: 加载进度与旧缓存数据不并存
- **WHEN** 用户点击 Refresh Data 触发重新加载
- **THEN** 数据区域加半透明遮罩（`st.empty()` 占位 + CSS opacity），提示"数据更新中..."，而非新旧数据并存

### Requirement: 单项 API 调用超时机制
`src/data/china_market_fetcher.py` 中每个 Tushare / AkShare API 调用 SHALL 受到独立超时控制，单次调用超时阈值为 **25 秒**。超时发生时，函数 SHALL 返回最近的缓存值并标记 `stale=True`，而非抛出异常或无限等待。

#### Scenario: API 调用在 25 秒内完成
- **WHEN** Tushare API 在 25 秒内返回响应
- **THEN** 函数正常返回最新数据，`stale=False`

#### Scenario: API 调用超时后降级为缓存值
- **WHEN** 某个 Tushare / AkShare API 调用耗时超过 25 秒
- **THEN** 函数中断该调用，从 CSV 缓存中读取最近一条历史值，返回 `(value, stale=True)`，并在日志中记录 `WARN: API timeout for <metric>, using stale cache`

#### Scenario: 缓存完全不存在时超时降级
- **WHEN** API 超时且对应 CSV 缓存文件不存在（首次运行）
- **THEN** 函数返回 `(None, stale=True)`，UI 层对 `None` 值显示"—"占位而非崩溃

### Requirement: 全页面 30 秒兜底超时
A 股页面整体数据加载 SHALL 设置 30 秒全局兜底：超过 30 秒后，已加载完成的指标正常展示，未完成的指标显示 stale 缓存值（或"—"），不再阻塞页面渲染。

#### Scenario: 30 秒内全部加载完成
- **WHEN** 所有 A 股指标在 30 秒内完成获取
- **THEN** 页面正常渲染全部数据，无兜底提示

#### Scenario: 超过 30 秒仍有指标未完成
- **WHEN** 某个指标（如 QVIX）获取耗时超过 30 秒
- **THEN** 已完成指标正常展示；未完成指标使用 stale 值占位，该指标对应单元格加 `⚠️ 使用历史值（YYYY-MM-DD）` 标注；页面不再 blocking，用户可正常浏览其他内容
