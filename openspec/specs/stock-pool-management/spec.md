## ADDED Requirements

### Requirement: Stock pool persisted as JSON
系统 SHALL 将股票池数据持久化至 `data_cache/stock_pool.json`，文件为 JSON 数组，每项为一个 `StockPoolItem`。应用启动时自动加载，写操作完成后立即写回磁盘。

#### Scenario: Load existing pool on startup
- **WHEN** `data_cache/stock_pool.json` 存在且格式合法
- **THEN** 系统加载所有条目到内存，UI 展示完整股票池

#### Scenario: Handle missing file gracefully
- **WHEN** `data_cache/stock_pool.json` 不存在
- **THEN** 系统返回空列表，不抛异常，UI 展示空股票池并引导用户添加

#### Scenario: Handle corrupted JSON
- **WHEN** `data_cache/stock_pool.json` JSON 格式损坏
- **THEN** 系统返回空列表并在 UI 显示警告，不崩溃

### Requirement: StockPoolItem 数据模型
每个股票池条目 SHALL 包含以下字段：
- `ticker: str`（必填，如 `600519.SH`、`AAPL`）
- `name: str`（必填，显示名称）
- `market: str`（必填，枚举：`A股` / `美股` / `港股`）
- `sector: str`（必填，申万一级（A股）或 GICS 一级（美股），自由文本）
- `strategy_type: str`（必填，枚举：`trending_up` / `value` / `oscillation`）
- `status: str`（必填，枚举：`watching` / `holding`）
- `cost_basis: float | None`（可选，持仓成本价）
- `shares: float | None`（可选，持仓数量）
- `notes: str`（可选，备注）
- `added_date: str`（系统自动填充，ISO 8601 日期）

#### Scenario: Valid item with all fields
- **WHEN** 用户提交包含所有字段的合法表单
- **THEN** 系统创建 StockPoolItem 并写入 JSON，ticker 大写存储

#### Scenario: Valid item with only required fields
- **WHEN** 用户只填写必填字段，cost_basis/shares/notes 留空
- **THEN** 系统创建条目，可选字段设为 None / 空字符串

### Requirement: Add stock to pool via UI form
系统 SHALL 在 `st.expander("+ 添加标的")` 内提供表单，允许用户输入所有 StockPoolItem 字段并提交。ticker 提交后转大写。

#### Scenario: Successful add
- **WHEN** 用户填写合法的 ticker、name、market、sector、strategy_type、status 后点击"添加"
- **THEN** 条目出现在股票池汇总表中，JSON 文件已更新，expander 收起

#### Scenario: Duplicate ticker rejected
- **WHEN** 用户添加的 ticker 已存在于股票池
- **THEN** 系统显示错误提示"该标的已在股票池中"，不重复添加

#### Scenario: Missing required field
- **WHEN** 用户未填写 ticker 或 name 即点击"添加"
- **THEN** 系统显示字段级错误提示，不提交

### Requirement: Edit existing stock
系统 SHALL 允许用户从股票池汇总表选择一条记录，在 expander 中修改其字段并保存。

#### Scenario: Successful edit
- **WHEN** 用户修改标的的 status（如从 watching 改为 holding）并输入 cost_basis、shares
- **THEN** JSON 文件中该条目字段更新，UI 汇总表同步刷新

### Requirement: Delete stock from pool
系统 SHALL 允许用户删除股票池中的条目，删除前需二次确认。

#### Scenario: Confirmed delete
- **WHEN** 用户勾选"确认删除"并点击"删除"按钮
- **THEN** 条目从 JSON 中移除，UI 汇总表移除该行

#### Scenario: Unconfirmed delete ignored
- **WHEN** 用户点击"删除"但未勾选确认 checkbox
- **THEN** 系统不执行删除，显示提示"请先勾选确认删除"

### Requirement: Filter stock pool by multiple dimensions
系统 SHALL 提供市场/策略类型/行业/状态四个过滤控件，多个过滤条件同时生效（AND 逻辑）。

#### Scenario: Filter by market
- **WHEN** 用户选择市场 = "A股"
- **THEN** 汇总表只显示 market == "A股" 的条目

#### Scenario: Combined filter
- **WHEN** 用户选择市场 = "A股" 且 strategy_type = "trending_up"
- **THEN** 汇总表只显示同时满足两个条件的条目

#### Scenario: No results
- **WHEN** 过滤条件组合下股票池为空
- **THEN** 显示"当前筛选条件下无标的"提示，不报错
