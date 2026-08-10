## MODIFIED Requirements

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

## ADDED Requirements

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
