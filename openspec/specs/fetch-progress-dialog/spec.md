# Fetch Progress Dialog Specification

## Purpose
描述中国/港股页面在 session cache miss 时的 st.status 进度弹窗、stale 标注、超时中断与 i18n 覆盖。
## Requirements

### Requirement: Session cache miss 时显示进度弹窗
中国/港股页面 SHALL 在 `china_regime_YYYY-MM-DD` 不存在于 `st.session_state` 时，使用 `st.status()` widget 展示 A 股数据获取的逐步执行进度。Cache hit（已有 session_state）时 SHALL NOT 显示弹窗，直接读取缓存结果。

#### Scenario: 首次加载（session cache miss）显示进度步骤
- **WHEN** 用户在当天首次访问中国/港股页面（session_state 中无当天体制评分结果）
- **THEN** 页面上方出现展开的 `st.status()` 弹窗，标题为"📡 正在获取A股指标数据..."，内部按顺序显示 8 个 fetch 步骤的进度消息

#### Scenario: Cache hit 时无进度弹窗
- **WHEN** 用户已在当天完成过一次数据加载（session_state 中存在当天体制评分结果），再次切换到中国/港股页面或刷新片段
- **THEN** 页面直接渲染体制评分结果，不出现进度弹窗

#### Scenario: 加载完成后弹窗自动折叠
- **WHEN** 所有 8 个 fetch 步骤执行完毕
- **THEN** `st.status()` 状态更新为 `state="complete"`，弹窗自动折叠，标题显示完成摘要（如"✅ 所有A股数据已更新"或"⚠️ 数据加载完成（N 项使用历史值）"）

---

### Requirement: `_fetch_china_regime_data` 接受可选 progress 参数
函数 `_fetch_china_regime_data(today, progress=None)` SHALL 接受一个可选的 `progress` 对象（`st.status()` 实例或 `None`）。当 `progress` 为 `None` 时函数行为 SHALL 与原版完全一致（向后兼容）。

#### Scenario: progress=None 时不影响函数逻辑
- **WHEN** `_fetch_china_regime_data(today, progress=None)` 被调用（如单元测试或非 UI 场景）
- **THEN** 函数正常执行所有 fetch 步骤并返回结果，不抛出任何异常

#### Scenario: 每个 fetch 步骤写入进度消息
- **WHEN** `progress` 非 None 且某个 fetch_* 函数调用开始前
- **THEN** `progress.write()` 被调用，消息包含步骤名称和数据源标识（例如"🔗 融资融券余额 (Tushare)..."）

---

### Requirement: stale 数据在进度弹窗中标注
进度弹窗完成时的标题 SHALL 反映数据质量：若所有指标均为最新数据则显示 `t("progress_all_fresh")`（中：✅ 所有A股数据已更新；英：✅ All A-Share data updated）；若有任意一个 `data_stale=True` 的指标则显示 `t("progress_partial_stale")` 格式化字符串，包含 stale 计数，例如"⚠️ 数据加载完成（N 项使用历史值）"。

新增行为：弹窗 SHALL 对每个 stale 指标在内部额外显示一行 `⚠️ <指标名>：使用 <last_data_date> 缓存值`，明确指出哪些指标是历史数据。

#### Scenario: 全部数据新鲜时显示成功状态
- **WHEN** 所有 fetch 函数返回 `data_stale=False`
- **THEN** 弹窗折叠标题为 `t("progress_all_fresh")`，内部无 stale 警告行

#### Scenario: 存在 stale 数据时显示各项 stale 来源
- **WHEN** QVIX fetch 返回 `data_stale=True`，`last_data_date="2026-05-20"`
- **THEN** 弹窗折叠标题含 stale 计数；弹窗内部额外显示"⚠️ QVIX：使用 2026-05-20 缓存值"

#### Scenario: API 超时时也记录为 stale
- **WHEN** 某个 Tushare API 调用触发 25 秒超时，从缓存返回 stale 值
- **THEN** 该指标在进度弹窗中显示"⏰ <指标名>：API 超时，使用历史缓存值"（与数据本身延迟的 stale 区分标识符）

### Requirement: 进度弹窗支持超时中断显示
`st.status()` 弹窗 SHALL 在全局 30 秒兜底触发时，将未完成的步骤标记为 `⏰ 超时（使用缓存值）`，并将整体状态切换为 `state="complete"`（而非 `state="error"`），确保页面不被阻塞。

#### Scenario: 超时触发时弹窗仍能完成关闭
- **WHEN** 全局 30 秒兜底触发，此时仍有 2 个步骤未完成
- **THEN** 这 2 个步骤各在进度弹窗中写入"⏰ 超时，已使用历史值"；弹窗状态切换为 complete 并折叠，标题反映 stale 计数

### Requirement: 进度弹窗 i18n 覆盖
弹窗内所有文字 SHALL 通过 `t("key")` 国际化，包括步骤标签、折叠标题、stale 警告文字。

#### Scenario: 中文模式下进度弹窗显示中文
- **WHEN** `st.session_state["language"] = "zh"` 且页面加载触发进度弹窗
- **THEN** 弹窗标题为"📡 正在获取A股指标数据..."，步骤文字为中文，stale 警告为中文
