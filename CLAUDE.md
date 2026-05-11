# Claude Code 使用规范 — investor-copilot

## 语言

**默认使用中文回复**。技术术语、金融指标名称、库名/API名、代码标识符可保留英文，例如：
- 正确：「在 `fetch_margin_ratio` 中修复了 T-1 weekday 的问题」
- 正确：「两融余额市值比 (Margin Ratio) 当前为 2.08%，处于 NORMAL 区间」
- 避免：全程英文回复，除非用户主动用英文提问

## 项目概述

**Macro Liquidity AI Analyst** — 宏观流动性 AI 分析工具。

核心功能：
- 全球/美股：Fed 净流动性 (Net Liquidity = WALCL - RRP - TGA)、信号灯体制评分
- 中国/港股：A 股三层体制评分引擎（Layer 1 流动性基底 → Layer 2 市场体制 → Layer 3 即时哨兵）

运行方式：`uv run streamlit run main.py`

## 代码规范

### 关键约束
- **i18n 强制**：所有用户可见的静态文本必须通过 `t("key")` 调用，key 同时注册中英文，不得硬编码字符串直接渲染
- **Pure Functions**：分析逻辑（`src/analysis/`）必须是纯函数，无副作用；唯一例外是 `compute_china_regime`（读写 sentinel state）
- **ETL-on-demand 缓存**：数据拉取函数遵循「先查 CSV 缓存 → miss 则调 API → 追加写回」模式，缓存目录 `data_cache/china/`，文件格式为 CSV，index 为日期
- **LLM 报告缓存**：所有 LLM 生成内容必须按 `data_cache/reports/YYYY-MM-DD_lang.json` 缓存，禁止每次请求都调 LLM
- **错误不崩溃**：Tushare/AkShare 调用失败时返回 `(last_known_value, stale=True)`，不抛异常到 UI 层

### 数据单位（血泪教训）
- `pro.margin` `rzye/rqye/rzrqye`：单位为**元**，转亿元用 `_YUAN_TO_YI = 1e-8`
- `index_dailybasic` `total_mv`：单位为**元**，不是万元
- `daily_basic` `total_mv`：单位为**万元**，转亿元用 `_WAN_TO_YI = 1e-4`
- `index_daily` `amount`：单位为**千元**，转亿元用 `_QIAN_TO_YI = 1e-5`
- `cn_m` `m2`：单位直接为**亿元**，无需转换
- `pro.margin` 的 `exchange=` 参数**无效**，API 始终返回全市场 BSE+SSE+SZSE 三行，必须调用一次后汇总 `rzrqye`，不能循环两次累加

### API 使用注意
- **T-1 查询**：margin、csi300_pe 等发布有 T+1 滞后，使用 `_last_weekday_before(query_date)` 而非 `date - timedelta(days=1)`（避免周末无数据）
- **总市值**：用 `pro.daily_basic(trade_date=...)` 汇总所有 A 股 `total_mv`（万元），比用 `index_dailybasic` 对两个不完整指数更准确
- **QVIX**：来源 `ak.index_option_50etf_qvix()`，AkShare 有约 3-5 日延迟（节假日后更长），stale=True 时仍应使用 last-known-good 值

## 架构速查

```
src/
  analysis/
    china_regime.py      # 三层体制评分：纯函数 + compute_china_regime（有状态）
    engine.py            # 美股体制评分引擎
  data/
    china_market_fetcher.py  # 所有 A 股数据拉取，ETL-on-demand CSV 缓存
    loader.py            # 历史数据加载（FRED / Yahoo / AkShare 综合）
  ui/
    app.py               # Streamlit 主入口，tab1=美股 tab2=中国
    china_regime_components.py  # A 股 UI 组件（9 个 render 函数）
    regime_components.py # 美股体制 UI 组件
  utils/
    i18n.py              # 翻译表，t("key") 调用
  regime/                # 美股体制评分引擎（RegimeEngine）
  portfolio/             # 持仓分析与仓位建议
  llm/                   # AI 报告生成（MacroAnalyst、RegimeNarrator）

data_cache/
  china/                 # A 股指标缓存 CSV（margin_ratio、csi300_pe 等）
  china_sentinel_state.json   # 哨兵状态（CLEAR/TRIGGERED/COOLING），跨重启持久化
  china_regime_history.csv    # 体制历史快照，用于时间线图表
  reports/               # LLM 报告缓存

tests/
  test_china_regime.py   # 99 个单元测试，覆盖 L1/L2/L3/Envelope
```

## 测试

```bash
uv run pytest                     # 所有测试
uv run pytest tests/test_china_regime.py -v   # A 股体制评分专项
```

新增分析逻辑必须有单元测试，覆盖：正常路径、边界阈值、None/缺失数据、状态机转换。

## 环境变量

参考 `example.env`。必须配置：
- `TUSHARE_API_KEY`：A 股数据（需 Tushare Pro 订阅）
- `OPENAI_API_KEY` + `OPENAI_BASE_URL`：LLM（通过 OpenRouter 调用 Gemini）
- `FRED_API_KEY`：美联储数据

AkShare 无需 API key。
