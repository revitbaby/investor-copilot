## Context

当前应用是单文件 Streamlit Tab 结构（`src/ui/app.py` ~870 行），所有页面渲染函数（`render_us_dashboard`、`render_china_dashboard`、`render_trading_strategy`）都在同一文件里用 `@st.fragment` 修饰。数据流分为两层缓存：磁盘 CSV（`data_cache/`）+ Streamlit `@st.cache_data`（进程内存），最终写入 `session_state`（会话内存）。

核心问题：

1. **导航扩展受阻**：第四页（数据管理）无法用 Tab 优雅呈现，Tab 水平空间有限
2. **加载不透明**：`_fetch_china_regime_data()` 调用 8 个 fetcher 全程串行，只有右上角转圈
3. **无同步遥测**：fetcher 层没有计时和状态记录，无法追踪哪个数据源慢、哪个失败

## Goals / Non-Goals

**Goals:**

- 将应用迁移至 Streamlit Multipage App，实现四页侧边栏导航
- 在 session cache miss 时通过 `st.status()` 展示 A 股数据获取的逐步进度
- 在 fetcher 层记录 API 调用耗时到 `sync_log.json`
- 新增 Data Management 页面消费 `sync_log.json` 数据
- 生成 `docs/data_flow_spec.md` 技术文档

**Non-Goals:**

- 并行化 fetch 调用（另一个优化方向，会引入 Tushare 限速复杂性）
- 美股进度弹窗（美股数据由 `@st.cache_data` 完全包裹，改造成本较高，暂不做）
- `sync_log.json` 的实时推送/WebSocket 更新
- 历史同步日志（只保留每个 key 的最新一次记录）

## Decisions

### 决策 1：Multipage App 迁移方案 — Streamlit native pages/ 目录

**选择**：使用 Streamlit 原生 Multipage（`pages/` 目录）而非 Sidebar Radio Button。

**理由**：
- Streamlit 自动生成侧边栏导航、URL 路由（`/?page=Data_Management`），无需手写
- 各页面文件独立，避免 app.py 继续膨胀
- 不同页面之间数据隔离，session_state 仍然全局共享

**共享状态处理**：`days_back`、语言选择、`force_refresh` 按钮移入各页面自己的 sidebar。全局配置（如语言）通过 `st.session_state["language"]` 共享（Multipage 下 session_state 跨页持久）。`init_i18n()` 在每个页面顶部调用（幂等，无副作用）。

**`main.py` 作用**：在 Multipage 模式下，`main.py`（即 `streamlit run main.py`）成为"默认首页"，渲染全球/美股内容；其余页面在 `pages/` 目录下按数字前缀排序。

```
main.py                    ← 全球/美股 (默认首页)
pages/
  2_China_HK.py            ← 中国/港股
  3_Trading_Strategy.py    ← 交易策略
  4_Data_Management.py     ← 数据管理 (新增)
```

**备选方案**：Sidebar Radio Button — 改动小，但保留单文件缺陷，未来再加页面仍然困难。舍弃。

---

### 决策 2：进度弹窗 — `st.status()` + 可选 `progress` 参数注入

**选择**：给 `_fetch_china_regime_data(today, progress=None)` 加可选参数，在调用方（`render_china_dashboard`）创建 `st.status()` context 并传入。

**理由**：
- `_fetch_china_regime_data` 是普通 Python 函数（非 Streamlit fragment），可以接收任何对象
- 调用方掌控"是否显示进度框"的条件（session cache miss），内部函数无需感知
- 向后兼容：`progress=None` 时行为完全不变，单元测试不受影响

**内部实现**：
```python
def _step(msg: str) -> None:
    if progress is not None:
        progress.write(msg)
```

**触发条件**：仅当 `regime_cache_key not in st.session_state` 时创建 `st.status()`，cache hit 时直接读 session_state（无 UI 干扰）。

**备选方案**：通过 `session_state` 传递进度消息 + `st.empty()` 轮询——过于迂回，不用。

---

### 决策 3：同步遥测 — context manager `_record_sync()` + `sync_log.json`

**选择**：在 `china_market_fetcher.py` 中新增 `_record_sync(filename)` context manager，仅包裹 **API 调用分支**（非 CSV cache 命中分支）。

**理由**：
- 只有 API 调用路径才有实质意义的"同步耗时"——cache hit 在毫秒级，不值得记录
- Context manager 封装干净，每个 fetcher 只加一行 `with _record_sync("xxx.csv"):`
- JSON 格式易于在 Data Management 页面读取，无需引入数据库

**`sync_log.json` schema**：
```json
{
  "china/margin_ratio.csv": {
    "last_sync_utc": "2026-05-15T08:43:22",
    "duration_s": 2.34,
    "status": "success",
    "last_data_date": "2026-05-14"
  }
}
```

`last_data_date` 由 `_record_sync` 内部在写入后读取 CSV 最后一行 index 得到（而非在每个 fetcher 单独传入，减少改动量）。

**DataLoader 计时**：`loader.py` 的三个方法用相同 `_record_sync()` 机制，key 为 `"macro_data.csv"`、`"sector_etf_data.csv"`、`"china_data.csv"`（不带 `china/` 前缀）。

**备选方案**：在 `_save_cache()` 里写 log——时机不对，`_save_cache` 不知道整个 fetch 的开始时间。舍弃。

---

### 决策 4：Data Management 页面 — 纯展示 + 手动操作

**状态分类逻辑**：
```
今天同步过 && status=success → ✅ 新鲜
今天同步过 && status=error   → ❌ 错误
非今天同步 && data_date 是今天或昨天 → 🔶 延迟（数据有但未重新拉）
非今天同步 && 月频数据（M2 等）     → ⚠️ 月频（正常）
sync_log 里没有记录                  → ⬜ 未知
```

**刷新操作**：「🔄 刷新全部」按钮调用 `st.cache_data.clear()` 并删除 `data_cache/sync_log.json` 的今日缓存标记，然后 `st.rerun()`——与现有 `force_refresh` 逻辑一致。

**「🗑 清除今日缓存」**：仅清除 `data_cache/china/` 下今天 mtime 的文件，让 fetcher 在下次加载时重新拉取，不删历史数据。

## Risks / Trade-offs

**[风险 1] Multipage 迁移时 session_state 共享机制变化** → Streamlit Multipage 的 session_state 在同一浏览器 tab 内跨页持久，但首次导航到新页面时该页面的初始化代码会重新执行。`init_i18n()` 已是幂等操作，不受影响。regime 结果已用日期 key，也不受影响。**缓解**：迁移后在每个页面顶部统一调用 `init_i18n()` 和 `load_dotenv()`。

**[风险 2] `_record_sync` 在 backfill 慢路径下计时包含整个 backfill 耗时** → `_backfill_total_mv_daily` 最长可能 90+ 秒。sync_log 里会出现超长耗时，不会报错，但数字可能让用户困惑。**缓解**：在 UI 展示时对 `duration_s > 30` 加注释"（含历史补全）"。

**[风险 3] `sync_log.json` 并发写入竞争（多浏览器 tab）** → 两个 tab 同时触发 fetch 可能导致 JSON 写入冲突。**缓解**：采用"读-改-写"原子性足够（Python GIL + 文件写入通常在毫秒内完成），对个人工具级别可接受；不引入文件锁复杂度。

**[风险 4] 进度弹窗干扰 `@st.fragment` 的局部重渲染** → `render_china_dashboard` 是 `@st.fragment`，`st.status()` 在 fragment 内完全支持。**缓解**：已验证 Streamlit 文档，fragment 内部可用 `st.status()`。

**[Trade-off] 不做并行 fetch** → 8 个 fetcher 串行在 cache miss 时累计可达 10-15s，有进度框后用户体验可接受，但不是最快。并行化涉及 Tushare 限速（每分钟调用次数），留作后续优化。
