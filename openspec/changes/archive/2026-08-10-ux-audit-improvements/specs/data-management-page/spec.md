## ADDED Requirements

### Requirement: 移动端缓存状态表格支持横向滚动
数据管理页的 A-Share 缓存状态表格 SHALL 在 375px 宽度（移动端）下支持横向滚动，确保"Data As Of / Duration / Status"等列不被截断，用户可向右滑动查看完整数据。

实现方式：通过 `st.markdown('<style>.stDataFrame { overflow-x: auto !important; }</style>', unsafe_allow_html=True)` 注入 CSS；将 CSS 封装为 `_inject_mobile_table_styles()` 函数，在页面顶部调用一次。

#### Scenario: 移动端表格可横向滑动查看所有列
- **WHEN** 用户在 375px 宽度的设备上访问数据管理页
- **THEN** 缓存状态表格的所有列（Dataset / Last Synced / Data As Of / Duration / Status）均可通过横向滚动查看，无列内容被截断

#### Scenario: 桌面端不受 CSS 注入影响
- **WHEN** 用户在 1280px 宽度的桌面浏览器访问数据管理页
- **THEN** 表格行为与改动前一致，列宽按内容自动分配，无横向滚动条出现

### Requirement: 数据管理页 i18n 补全
数据管理页面所有用户可见文字 SHALL 通过 `t("key")` 国际化，包括：页面标题、副标题（"Cache status, sync telemetry, and manual refresh"）、表格列头（Dataset / Last Synced / Data As Of / Duration / Status）、操作按钮文字、状态图标文字（Fresh / Delayed / Monthly / Error / Unknown）。

#### Scenario: 中文模式下页面完整显示中文
- **WHEN** `st.session_state["language"] = "zh"` 且用户访问数据管理页
- **THEN** 页面标题显示 `t("page_data_mgmt_title")`（"数据管理"），列头显示中文，状态显示中文标签

#### Scenario: 英文模式下页面完整显示英文
- **WHEN** `st.session_state["language"] = "en"` 且用户访问数据管理页
- **THEN** 页面标题显示"Data Management"，列头显示英文，所有文字保持英文
