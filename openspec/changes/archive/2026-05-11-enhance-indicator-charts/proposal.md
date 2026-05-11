# Proposal: A股指标图表体验增强

> **所属系统**: Macro Liquidity Copilot Dashboard — China 模块  
> **日期**: 2026-05-11  
> **状态**: Proposal  

---

## 1. 背景与动机

三个核心 A 股指标（两融余额市值比、股债利差、存款市值比）的数据拉取函数已完成，但图表体验存在以下问题：

1. **历史数据空白**：三个指标的缓存文件各只有 1-2 行最新数据，无法展示历史走势折线图
2. **参考点呈现方式弱**：当前用水平虚线（`add_hline`）表示历史牛市水位，参考截图使用圆圈锚点标注具体历史日期，信息更直观
3. **距离卡片缺失**：截图中"最新 vs 2015 / 最新 vs 2021 / 最新值"三列卡片样式未实现，当前只用 `st.caption()` 简陋展示
4. **无市场指数叠加**：无法对比历史指标值与沪深300/创业板指的走势关系
5. **无时间范围选择**：无法缩放至 1年/3年/5年/10年视图

---

## 2. 用户价值

| 需求 | 当前体验 | 改善后 |
|------|----------|--------|
| 判断两融比是否接近历史牛市水位 | 仅有今日数值，无历史 | 折线图 + 2015/2021 圆圈锚点，一眼看出距离 |
| 感知指标当前所处历史分位 | 无 | 时间范围切换，可对比 1Y/3Y/5Y/10Y 视角 |
| 关联市场走势理解指标含义 | 无 | 叠加沪深300或创业板指（可切换） |
| 快速读取与历史高点的距离 | st.caption 文字 | 样式化三列卡片，颜色编码距离远近 |

---

## 3. 方案设计

### 3.1 历史数据 Backfill（所有其他功能的前提）

**触发时机**：在 `fetch_margin_ratio` / `fetch_equity_bond_spread` / `fetch_deposit_ratio` 内部，加载缓存后检测：

```python
HISTORY_START = date(2015, 1, 1)

if cache.empty or cache.index.min() > pd.Timestamp(HISTORY_START):
    _backfill_<indicator>(HISTORY_START)
    cache = _load_cache(filename)
```

**共享总市值缓存**：三个指标共用 `total_mv_daily.csv`（避免重复 API 调用）

```
_backfill_total_mv_daily(start_date, end_date)
  ↳ 按月循环调用 pro.daily_basic(start_date, end_date, fields="total_mv")
  ↳ group_by(trade_date).sum(total_mv) → 亿元
  ↳ 存入 data_cache/china/total_mv_daily.csv
```

各指标 backfill 函数：

| 函数 | 数据来源 |
|------|----------|
| `_backfill_margin_ratio` | `pro.margin(start, end)` 批量 + `total_mv_daily.csv` join |
| `_backfill_equity_bond_spread` | `pro.index_dailybasic(000300.SH)` pe_ttm 批量 + `ak.bond_china_yield()` 批量 |
| `_backfill_deposit_ratio` | `m2_monthly.csv`（已有）+ `total_mv_daily.csv` 月末值 join |

首次 backfill 预计耗时 1-3 分钟（月批次），之后每日增量更新不受影响。

### 3.2 历史牛市锚点（圆圈标注）

在 `china_regime.py` 中定义锚点字典，UI 层将其渲染为 Scatter marker：

```python
MARGIN_RATIO_ANCHORS = {
    "2015年牛市": "2015-06-30",
    "2021年牛市": "2021-03-09"
}
EQUITY_BOND_ANCHORS = {
    "2008年牛市": "2008-01-14",
    "2015年牛市": "2015-06-15",
    "2021年牛市": "2021-02-18"
}
DEPOSIT_RATIO_ANCHORS = {
    "2008年牛市": "2008-01-10",
    "2015年牛市": "2015-06-15",
    "2021年牛市": "2021-01-21",
}
```

图表中，每个锚点对应一个空心大圆圈（`marker_symbol="circle-open"`，size=12）+ 文字标注（取代原来的水平 `add_hline`）。

### 3.3 "最新 vs 历史" 距离卡片

新增 `render_bull_distance_cards(latest, latest_date, anchors, accent_color)` 组件，输出 HTML 三列卡片：

```
┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐
│  最新 vs 2015   │  │  最新 vs 2021   │  │     最新值        │
│    较远         │  │  超 0.05%  [橙] │  │    2.03%   [青框] │
│    3.33%        │  │    1.98%        │  │  2026-02-25       │
│  2015-06-30     │  │  2021-03-09     │  │                   │
└─────────────────┘  └─────────────────┘  └──────────────────┘
```

颜色逻辑：
- 若当前值**超过**历史高点 → 橙/红色文字 + "超X%"
- 若当前值**低于**历史高点 → 使用 `compute_margin_ratio_distance` 的文字描述（很远/较远/较近/接近）
- 最新值卡片：用指标的主题色做边框（两融=蓝，股债=橙，存款=绿）

### 3.4 叠加指数（可切换）

**新增数据函数**：

```python
def fetch_index_close(
    symbol: Literal["sh000300", "sz399006"],
    start_date: date,
) -> pd.Series:
    # ak.stock_zh_index_daily(symbol=symbol)
    # 缓存到 index_hs300_daily.csv / index_gem_daily.csv
```

**图表叠加方式**：次坐标轴（右轴），归一化为周期起始=100 的百分比变化：

```python
idx_norm = (idx_slice / idx_slice.iloc[0] - 1) * 100
fig.add_trace(..., yaxis="y2")
fig.update_layout(yaxis2=dict(overlaying="y", side="right", title="%变化"))
```

### 3.5 时间范围选择（共用控件）

在三个卡片上方放置两个共用控件（`st.columns` 行）：

```python
col_idx, col_period = st.columns([1, 1])
with col_idx:
    index_choice = st.radio("叠加指数", ["沪深300", "创业板指"], horizontal=True)
with col_period:
    period = st.radio("时间范围", ["1Y", "3Y", "5Y", "10Y"], index=1, horizontal=True)
```

默认值：叠加指数 = 沪深300，时间范围 = 3Y。

各 render 函数接受 `time_period: str` 和 `index_series: pd.Series | None` 参数，在函数内部做 `series[cutoff:]` 滤波。

---

## 4. 文件变更范围

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/data/china_market_fetcher.py` | 新增 + 修改 | `HISTORY_START`、`_backfill_total_mv_daily`、三个 backfill 函数、backfill 触发、`fetch_index_close` |
| `src/analysis/china_regime.py` | 新增 | 三个 `*_ANCHORS` 字典 |
| `src/ui/china_regime_components.py` | 新增 + 修改 | `render_bull_distance_cards`、修改三个 render 函数签名和图表逻辑 |
| `src/utils/i18n.py` | 新增 key | 新增距离卡片、时间范围、指数选择相关文案 |
| `src/ui/app.py` | 修改 | 新增共用控件、传递参数到 render 函数 |
| `tests/test_china_regime.py` | 新增 | backfill 触发逻辑、距离卡片计算的单元测试 |

---

## 5. 超出范围

- 北向资金历史图表改造（独立需求）
- LLM 叙事整合（待体制评分引擎稳定后）
- 指标阈值回测验证
