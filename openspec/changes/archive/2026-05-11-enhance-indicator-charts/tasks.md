# Tasks: A股指标图表体验增强

> **变更**: `2026-05-11-enhance-indicator-charts`  
> **依赖**: `2026-05-09-enhance-china-regime-scoring`（数据层已实现）

---

## Task 1 ✅ — 共享总市值缓存 `_backfill_total_mv_daily`

**文件**: `src/data/china_market_fetcher.py`

新增函数 `_backfill_total_mv_daily(start_date: date, end_date: date) -> None`：

- 按月循环（`start_date` 到 `end_date`）
- 每月调用 `pro.daily_basic(start_date=month_start_str, end_date=month_end_str, fields="ts_code,trade_date,total_mv")`
- 按 `trade_date` 聚合：`group_by(trade_date).sum(total_mv)` → 转亿元（`* _WAN_TO_YI`）
- upsert 到 `data_cache/china/total_mv_daily.csv`（index=date，列=`Total_MV_Yi`）
- 跳过 cache 中已有数据的日期范围（只补空缺）

**验收**：`total_mv_daily.csv` 覆盖 2015-01-01 至今，行数 ≈ 2700+（A 股交易日数量）

---

## Task 2 ✅ — Margin Ratio 历史 backfill

**文件**: `src/data/china_market_fetcher.py`

新增函数 `_backfill_margin_ratio(start_date: date) -> None`：

- 调用 `pro.margin(start_date=start_str, end_date=today_str, fields="trade_date,rzrqye")`
- 按 `trade_date` 聚合 `rzrqye`（元 → 亿元，`* _YUAN_TO_YI`）
- 从 `total_mv_daily.csv` join `Total_MV_Yi`（需先确保 Task 1 已运行）
- 计算 `Margin_Ratio_Pct = margin / total_mv * 100`
- upsert 全量到 `margin_ratio.csv`

修改 `fetch_margin_ratio`：在 `_load_cache` 之后、返回之前，检测：
```python
HISTORY_START = date(2015, 1, 1)
if cache.empty or cache.index.min() > pd.Timestamp(HISTORY_START):
    _backfill_total_mv_daily(HISTORY_START, date.today())
    _backfill_margin_ratio(HISTORY_START)
    cache = _load_cache("margin_ratio.csv")
```

**验收**：首次调用后 `margin_ratio.csv` 含 2015-01-05 附近最早交易日至今的数据

---

## Task 3 ✅ — Equity-Bond Spread 历史 backfill

**文件**: `src/data/china_market_fetcher.py`

新增函数 `_backfill_equity_bond_spread(start_date: date) -> None`：

- `pro.index_dailybasic(ts_code="000300.SH", start_date=start_str, end_date=today_str, fields="trade_date,pe_ttm")` → 批量获取 CSI300 PE
- `ak.bond_china_yield(start_date=start_str, end_date=today_str)` → 批量获取 10Y 国债收益率
- 对齐日期（两个序列 inner join on date）
- 计算 `Equity_Bond_Spread = 100/PE_TTM - CGB_10Y_Yield`
- upsert 全量到 `equity_bond_spread.csv`（同时更新 `csi300_pe.csv` 和 `cgb10y_yield.csv`）

修改 `fetch_equity_bond_spread`：同 Task 2 模式，检测后触发 backfill。

**验收**：`equity_bond_spread.csv` 含 2015 年至今日频数据，2015-06-15 的值约 1.81%

---

## Task 4 ✅ — Deposit Ratio 历史 backfill

**文件**: `src/data/china_market_fetcher.py`

新增函数 `_backfill_deposit_ratio(start_date: date) -> None`：

- 从 `m2_monthly.csv` 读取 M2（已有 1990 年至今）
- 取每月末一条记录（`resample("ME").last()`），过滤 `>= start_date`
- 从 `total_mv_daily.csv` 取每月末的 `Total_MV_Yi`（`resample("ME").last()`）
- 计算 `Deposit_Ratio = M2_Yi / Total_MV_Yi`
- upsert 全量到 `deposit_ratio.csv`

修改 `fetch_deposit_ratio`：同 Task 2 模式。注意 Task 1 需先运行（M2 无需额外 API 调用）。

**验收**：`deposit_ratio.csv` 含月频数据，2015-06-30 附近的值约 0.68

---

## Task 5 ✅ — 叠加指数数据函数

**文件**: `src/data/china_market_fetcher.py`

新增函数：
```python
def fetch_index_close(
    symbol: Literal["sh000300", "sz399006"],
    start_date: date,
) -> tuple[pd.Series | None, bool]:
```

- `ak.stock_zh_index_daily(symbol=symbol)` → 获取日频收盘价
- 过滤 `>= start_date`
- 缓存到 `index_hs300_daily.csv`（symbol=sh000300）或 `index_gem_daily.csv`（symbol=sz399006）
- ETL-on-demand：缓存命中则直接返回，否则拉取全量并存盘
- 返回 `(pd.Series with date index and close prices, stale: bool)`

**验收**：两个缓存文件均含 2015 年至今数据；stale=True 时返回 last-known-good

---

## Task 6 ✅ — 牛市锚点字典（分析层）

**文件**: `src/analysis/china_regime.py`

在文件顶部（常量区）新增三个字典：

```python
MARGIN_RATIO_ANCHORS: dict[str, tuple[str, float]] = {
    "2015年牛市": ("2015-06-30", 3.33),
    "2021年牛市": ("2021-03-09", 1.98),
}
EQUITY_BOND_ANCHORS: dict[str, tuple[str, float]] = {
    "2008年牛市": ("2008-01-14", -2.22),
    "2015年牛市": ("2015-06-15",  1.81),
    "2021年牛市": ("2021-02-18",  2.63),
}
DEPOSIT_RATIO_ANCHORS: dict[str, tuple[str, float]] = {
    "2008年牛市": ("2008-01-10", 0.44),
    "2015年牛市": ("2015-06-15", 0.68),
    "2021年牛市": ("2021-01-21", 1.07),
}
```

值来源：参考截图中标注的历史实测值。

**无需测试**（纯常量，在 Task 9 图表集成测试中验证）

---

## Task 7 ✅ — i18n 新增文案

**文件**: `src/utils/i18n.py`

新增以下 key（中英双语）：

| key | 中文 | 英文 |
|-----|------|------|
| `cn_index_overlay_label` | 叠加指数 | Overlay Index |
| `cn_index_hs300` | 沪深300 | CSI 300 |
| `cn_index_gem` | 创业板指 | ChiNext |
| `cn_period_label` | 时间范围 | Time Period |
| `cn_bull_peak_label` | 牛市 | Bull Peak |
| `cn_latest_value` | 最新值 | Latest |
| `cn_vs_label` | 最新 vs | Latest vs |
| `cn_above_by` | 超 | Above by |
| `cn_backfill_spinner` | 正在补全历史数据，首次加载约需 1-2 分钟... | Loading historical data, first run takes ~1-2 min... |

---

## Task 8 ✅ — 距离卡片组件

**文件**: `src/ui/china_regime_components.py`

新增函数：
```python
def render_bull_distance_cards(
    latest: float,
    latest_date: str,
    anchors: dict[str, tuple[str, float]],
    unit: str,           # "%" 或 "倍" 或 "x"
    accent_color: str,   # 最新值卡片边框色
) -> None:
```

逻辑：
- 遍历 `anchors`，每个锚点生成一个信息卡片（灰色边框）
- 若 `latest > anchor_val`：显示橙色文字"超 {diff:.2f}{unit}"
- 若 `latest <= anchor_val`：调用 `compute_margin_ratio_distance(latest, {name: val})` 取文字描述
- 最后一列渲染"最新值"卡片（`accent_color` 边框，显示 latest 和 latest_date）
- 使用 `st.columns(len(anchors) + 1)` 布局，卡片用 `st.markdown(..., unsafe_allow_html=True)`

**验收**：能渲染正确数量的卡片；超过历史高点时文字和颜色正确；低于时显示文字描述

---

## Task 9 ✅ — 重构三个指标 render 函数

**文件**: `src/ui/china_regime_components.py`

修改 `render_margin_ratio_card`、`render_equity_bond_spread_card`、`render_deposit_ratio_card` 的签名：

```python
def render_margin_ratio_card(
    margin_df: pd.DataFrame | None,
    index_series: pd.Series | None,    # 新增：叠加指数收盘价
    time_period: str,                  # 新增："1Y"/"3Y"/"5Y"/"10Y"
    language: str = "en",
) -> None:
```

每个 render 函数内部统一改动：

1. **时间滤波**：根据 `time_period` 计算 `cutoff`，`series = series[series.index >= cutoff]`
2. **删除 `add_hline`**：移除原有参考水平线
3. **新增锚点圆圈**：遍历对应 `*_ANCHORS`，用 `go.Scatter(mode="markers+text", marker_symbol="circle-open", marker_size=14)` 标注。若锚点日期不在 `time_period` 范围内则跳过
4. **新增叠加指数**：若 `index_series` 不为空，取与主序列相同日期范围，归一化为 `(val / val.iloc[0] - 1) * 100`，添加为 `yaxis="y2"` trace（半透明蓝色/浅色）
5. **`update_layout`**：新增 `yaxis2=dict(overlaying="y", side="right", title="%变化", showgrid=False)`
6. **距离卡片**：调用 `render_bull_distance_cards(...)` 替换原 `st.metric` + `st.caption`

**验收**：三个图表均可在不同时间范围下正确渲染；创业板指 overlay 在右轴显示；锚点超出时间范围时自动隐藏

---

## Task 10 ✅ — App 层控件与参数串联

**文件**: `src/ui/app.py`

在 China Tab 三个指标卡片渲染区域上方，新增共用控件行：

```python
col_idx, col_period = st.columns([1, 1])
with col_idx:
    index_label = st.radio(
        t("cn_index_overlay_label"),
        [t("cn_index_hs300"), t("cn_index_gem")],
        horizontal=True,
        key="cn_index_choice",
    )
with col_period:
    period = st.radio(
        t("cn_period_label"),
        ["1Y", "3Y", "5Y", "10Y"],
        index=1,   # 默认 3Y
        horizontal=True,
        key="cn_period_choice",
    )
```

获取叠加指数数据：
```python
idx_symbol = "sh000300" if index_label == t("cn_index_hs300") else "sz399006"
index_series, _ = fetch_index_close(idx_symbol, start_date=date(2015, 1, 1))
```

将 `index_series` 和 `period` 传入三个 render 函数。

**验收**：切换时间范围和指数后图表立即响应；默认 3Y + 沪深300

---

## Task 11 ✅ — 单元测试

**文件**: `tests/test_china_regime.py`

新增测试（不调用真实 API，用 mock 或 fixture）：

- `test_backfill_trigger_when_cache_empty`：缓存为空时 backfill 被调用（mock `_backfill_margin_ratio`）
- `test_backfill_trigger_when_history_insufficient`：最早日期 > 2015-01-01 时触发
- `test_no_backfill_when_history_complete`：最早日期 <= 2015-01-01 时不触发
- `test_render_bull_distance_cards_above_peak`：latest > anchor 时返回"超X%"文字
- `test_render_bull_distance_cards_below_peak`：latest < anchor 时返回距离描述文字
- `test_anchor_dict_values_are_plausible`：三个 `*_ANCHORS` 字典的值符合量级预期（如 margin 锚点在 1%-4% 之间）

**验收**：`uv run pytest tests/test_china_regime.py -v` 全部通过，无 API 调用

---

## 实现顺序

```
Task 1 (共享总市值) → Task 2/3/4 (各指标 backfill) → Task 5 (叠加指数)
                                                       ↓
Task 6 (锚点常量) → Task 7 (i18n) → Task 8 (距离卡片) → Task 9 (render 重构)
                                                                    ↓
                                                            Task 10 (App 控件)
                                                                    ↓
                                                            Task 11 (测试)
```
