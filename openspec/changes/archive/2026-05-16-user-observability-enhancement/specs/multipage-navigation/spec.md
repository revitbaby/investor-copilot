## ADDED Requirements

### Requirement: Pages directory structure
应用 SHALL 采用 Streamlit Multipage App 结构：`main.py` 作为全球/美股默认首页，`pages/` 目录下存放其余三个页面文件，Streamlit 自动在侧边栏生成导航菜单。

#### Scenario: 侧边栏显示四个导航项
- **WHEN** 用户打开应用
- **THEN** 侧边栏导航中显示四个页面：全球/美股（默认）、中国/港股、交易策略、数据管理，按文件数字前缀排序

#### Scenario: 页面间导航不丢失 session_state
- **WHEN** 用户在全球/美股页面触发了 A 股体制评分计算后切换到其他页面再切回
- **THEN** `st.session_state["china_regime_YYYY-MM-DD"]` 仍然存在，不触发重新计算

---

### Requirement: 全局共享设置迁移
各页面 SHALL 在自己的 `st.sidebar` 中独立渲染语言切换、lookback 天数（days_back）和数据刷新按钮，不依赖单一全局入口。语言状态通过 `st.session_state["language"]` 在页面间共享（Multipage session_state 跨页持久）。

#### Scenario: 语言切换在各页面生效
- **WHEN** 用户在全球/美股页面将语言切换为中文后导航到中国/港股页面
- **THEN** 中国/港股页面所有 `t("key")` 调用输出中文文本，无需重新设置语言

#### Scenario: days_back 独立配置
- **WHEN** 用户在全球/美股页面将 lookback 设为 365 天，然后导航到中国/港股页面
- **THEN** 中国/港股页面的 lookback slider 默认值不受影响（各页面独立）

---

### Requirement: 入口文件简化
`main.py` SHALL 只保留页面配置（`st.set_page_config`）和全球/美股内容的渲染调用，移除 Tab 相关逻辑。

#### Scenario: 直接访问应用根路径显示全球/美股内容
- **WHEN** 用户访问应用根 URL（`/`）
- **THEN** 显示全球/美股仪表盘内容（等同于原 tab1）
