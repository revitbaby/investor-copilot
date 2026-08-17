# 代码规范

编码与数据接入约束。产品定位与 ADR 索引见根目录 `CLAUDE.md`；词汇表见 `CONTEXT.md`。

## 关键约束

- **i18n 中文优先**（ADR-0016）：`t()` 基础设施保留；**新功能只注册中文 key**，英文停止供给，已有翻译不删；中文文案可保留英文金融术语
- **Pure Functions**：分析逻辑（`src/analysis/`）必须是纯函数，无副作用；唯一例外是 `compute_china_regime`（读写 sentinel state）
- **仓位单一出处**（ADR-0006）：任何新代码不得输出仓位建议数字（含金字塔加仓、固定止损止盈类逻辑——已判拆除，P1 执行）
- **双运行时**（ADR-0012）：数字由 Python 确定性内核 / headless `jobs/` 产出；Agent 仪式层只取数、装配叙事、经写入接口写账本；Streamlit 是**纯查阅层**（工件优先，ADR-0013）
- **持久化分层**（ADR-0014）：账本域 = SQLite（`data_cache/ledger.db`，Agent **不直接碰库文件**）；市场数据 = ETL-on-demand CSV
- **ETL-on-demand 缓存**：先查 CSV → miss 则调 API → 追加写回；目录 `data_cache/china/` 等，index 为日期
- **LLM 报告缓存**：按 `data_cache/reports/` 缓存，禁止每次请求都调 LLM
- **错误不崩溃**：Tushare/AkShare 失败返回 `(last_known_value, stale=True)`，不抛到 UI
- **import 边界**（ADR-0017）：`src/ledger/`、`src/themes/`、`src/dossier/`、`jobs/` 只准 import `src/analysis/`、`src/data/`、`src/utils/`，**永远不准 import `src/ui/`**；`src/ui/` 只读不写。同 repo 绿地+显式拆除，不从零重写、不留注释僵尸
- **阈值治理**（ADR-0009）：阈值在配置中标注来源与方向性理由；年度校准审查；**不做参数优化回测**
- **北向资金**（ADR-0009）：2024-08 后日度「净买入」均为估算值，**不采信**；改用成交总额（活跃度）+ 季度持股变动（方向）

## 数据单位（血泪教训）

- `pro.margin` `rzye/rqye/rzrqye`：单位为**元**，转亿元用 `_YUAN_TO_YI = 1e-8`
- `index_dailybasic` `total_mv`：单位为**元**，不是万元
- `daily_basic` `total_mv`：单位为**万元**，转亿元用 `_WAN_TO_YI = 1e-4`
- `index_daily` `amount`：单位为**千元**，转亿元用 `_QIAN_TO_YI = 1e-5`
- `cn_m` `m2`：单位直接为**亿元**，无需转换
- `pro.margin` 的 `exchange=` 参数**无效**，API 始终返回全市场 BSE+SSE+SZSE 三行，必须调用一次后汇总 `rzrqye`，不能循环两次累加

## API 使用注意

- **T-1 查询**：margin、csi300_pe 等发布有 T+1 滞后，使用 `_last_weekday_before(query_date)` 而非 `date - timedelta(days=1)`（避免周末无数据）
- **总市值**：用 `pro.daily_basic(trade_date=...)` 汇总所有 A 股 `total_mv`（万元），比用 `index_dailybasic` 对两个不完整指数更准确
- **QVIX**：来源 `ak.index_option_50etf_qvix()`，AkShare 有约 3-5 日延迟（节假日后更长），stale=True 时仍应使用 last-known-good 值
- Tushare/AkShare **行数与日期范围截断**约束见 `openspec/specs/data-ingestion/spec.md`

## 测试

```bash
uv run pytest
uv run pytest tests/test_china_regime.py -v
```

新增分析逻辑与账本 Facade 写入/聚合必须有单元测试，覆盖：正常路径、边界阈值、None/缺失数据、状态机转换。账本测试注入 QuoteProvider + 显式日期，不走网络。

## 账本写入契约（P0 钉死）

- **唯一接缝**：`src/ledger.Ledger` Facade；注入 QuoteProvider + 显式日期，内核不触网
- **ttfund 基金 JSON**（`schema_version: 1`，经 `python -m src.ledger.cli import-funds` 写入）：

```json
{
  "schema_version": 1,
  "funds": [
    {"code": "016532", "name": "某纳指QDII", "shares": 1000.0,
     "nav": 1.5, "nav_date": "2026-08-09",
     "currency": "CNY", "market": "CN"}
  ]
}
```

  必填 `code/name/shares/nav`；`nav <= 0`、`shares < 0`、schema 版本不符一律拒绝（exit 2）
- **ttfund 真实输出 → 契约映射**（2026-08-12 已对真实账户数据对齐，12 只基金市值误差 ¥0.01 内）：
  - `ACCOUNT_HOLDING/holding_list` 只给 `fundCode/fundName/assetValue`（市值），**不给份额与净值**
  - `shares` 由 Agent 逐基金调 `TTFUND_NAV_INFO`（action=query，取 `nav_history.items[-1]` 的 `DWJZ`/`FSRQ`）折算：`shares = assetValue / DWJZ`，保留 2 位小数
  - `nav_date` = `FSRQ`；QDII 净值滞后 T-1（境内 T 日），stale 规则（7 天）天然覆盖
  - `ptype=fund` 行进账本；**`ptype=hqb`（活期宝汇总行）不进基金导入**，走 `upsert-cash`（货币基金 nav 恒 1，市值即余额）
  - `holdProfit/constantProfit`（持仓/持有收益）P0 不采信入账，成本口径留待需要时再定
- **X-Ray 桶**：`CN_equity / HK_equity / US_equity / bond / cash / other`，权重和容差 ±0.02；基金未穿透时暴露计入 `UNPENETRATED`、卫星口径保守按全额计
- **X-Ray 例行刷新 SOP**（2026-08-17 起，替代前十外推法）：
  1. **QDII 一律读季报原文**「报告期末在各个国家（地区）证券市场的股票及存托凭证投资分布」节（强制披露）——跑 `uv run python -m jobs.xray_refresh`（干跑提案）→ 审阅备注 → `--write` 经门面落库。数字全程不过 LLM 手（ADR-0014）
  2. **非 QDII / 联接基金**（无地区分布节）：job 自动跳过；境内基金用 ttfund `TTFUND_HOLDING_INFO` 前十外推兜底（误差有界，主敞口是 CN）；联接基金按目标 ETF 口径
  3. **禁止手工填数**：如必须手工校正（如解析器未覆盖的排版），`data_as_of` 必须填**报告期日期**而非操作日期——否则旧的手工会遮蔽新的原文数据（2026-08-17 513310 教训）
  4. 解析器：`src/ledger/xray_report.py`（测试基准确诂 = 6 只基金 2026Q2 季报手工核对值，`tests/test_xray_report.py` + `tests/fixtures/xray/`）；韩/日/台等非 CN/HK/US 地区归入 `other` 并打备注
- **stale 规则**：报价超过 7 天未更新视为不新鲜；快照用最近有效价并标记 stale，序列不断档
- **基准配置**：`config/baseline.yaml`（示例见 `config/baseline.yaml.example`），缺失即「未设定」
- **生产 QuoteProvider**：`src/ledger/market_quotes.py`（股票复用 `stock_daily_fetcher`，FX = yfinance `USDCNY=X`/`HKDCNY=X`，基金净值只来自 ttfund 写入路径）

## 环境变量

参考 `example.env`。必须配置：
- `TUSHARE_API_KEY`：A 股数据（需 Tushare Pro 订阅）
- `OPENAI_API_KEY` + `OPENAI_BASE_URL`：LLM（通过 OpenRouter 调用 Gemini）
- `FRED_API_KEY`：美联储数据

AkShare 无需 API key。基金数据经 Agent 会话内的天天基金 `ttfund-*` Skills 拉取，不经 Python 直连公开 API。
