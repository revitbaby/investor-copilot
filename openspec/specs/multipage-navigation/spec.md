# Multipage Navigation Specification

## Purpose
描述 Streamlit Multipage 导航结构、共享设置、入口简化、开发者顶栏隐藏与首屏上传组件处理。
## Requirements

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

新增约束：`st.set_page_config` 的 `page_title` 参数 SHALL 设置为 `"US Markets — Macro Liquidity AI Analyst"`，`page_icon` 参数设置为 `"🇺🇸"`，确保浏览器标签页和侧边栏均显示语义化标题。

#### Scenario: 直接访问应用根路径显示全球/美股内容
- **WHEN** 用户访问应用根 URL（`/`）
- **THEN** 显示全球/美股仪表盘内容（等同于原 tab1），无 Tab 组件

#### Scenario: 浏览器标签页显示语义化标题
- **WHEN** 用户访问美股主页
- **THEN** 浏览器标签页显示"US Markets — Macro Liquidity AI Analyst"，而非"main"

### Requirement: 隐藏 Streamlit 开发者顶栏
应用 SHALL 在生产配置中隐藏 Streamlit 默认顶栏（包含 "Deploy" 按钮、三点菜单），终端用户不应看到这些开发者工具。

实现方式：在 `.streamlit/config.toml` 中添加：
```toml
[ui]
toolbarMode = "minimal"
```

`minimal` 模式 SHALL 仅保留 Streamlit 必要的运行状态指示（如 Stop 按钮，当脚本运行时显示），移除 Deploy 入口和 Share 等选项。

#### Scenario: 页面加载时不显示 Deploy 按钮
- **WHEN** 用户访问应用任意页面
- **THEN** 右上角不显示"Deploy"按钮，仅在脚本运行时显示 Stop 图标

#### Scenario: config.toml 不影响本地开发调试
- **WHEN** 开发者在本地通过 `uv run streamlit run main.py` 启动
- **THEN** 顶栏仍受 minimal 模式限制；开发者如需完整工具栏，可临时修改本地 config.toml

### Requirement: 首页导航标题语义化
导航菜单第一项 SHALL 从小写 "main" 改为语义化标题，与其他导航项（"China HK"、"Trading Strategy"、"Data Management"）保持命名规范一致。

方式：将 `main.py` 的 `st.set_page_config(page_title=...)` 设置为 `"US Markets"` 或中英双语 `"🇺🇸 US Markets"`；同时将页面文件视需要重命名，确保侧边栏显示 `"US Markets"` 而非 `"main"`。

#### Scenario: 侧边栏导航显示 "US Markets" 而非 "main"
- **WHEN** 用户打开应用，侧边栏渲染导航列表
- **THEN** 第一个导航项显示"US Markets"（或语义等价名），不显示"main"

#### Scenario: 中文模式下导航项随语言切换
- **WHEN** 语言切换为中文
- **THEN** 侧边栏导航第一项如有国际化版本则显示"美股分析"；如 Streamlit 多页面导航不支持动态 i18n，则保持英文名 "US Markets"（可接受）

### Requirement: 文件上传组件从首屏移除
`main.py` 首屏 SHALL 不再在核心内容区直接渲染 CSV 文件上传组件（`st.file_uploader`）。文件上传功能 SHALL 改为以下两种方式之一实现：
- **方案 A**：折叠进 `st.expander(t("upload_custom_csv"))` 中，expander 默认折叠
- **方案 B**：迁移至 Data Management 页面的专属上传区域

首屏呈现的首要内容 SHALL 为体制评分结果（进度条 + Layer 1/2 表格）。

#### Scenario: 首屏加载完成后不显示文件上传框
- **WHEN** 用户访问美股主页且数据加载完成
- **THEN** 首屏可见区域内无 "Drag and drop file here" 上传框，核心内容为体制评分看板

#### Scenario: 用户可通过折叠区域找到上传功能
- **WHEN** 用户需要上传自定义 CSV（方案 A）
- **THEN** 页面中存在 `t("upload_custom_csv")` 标题的 expander，展开后显示上传组件，功能完整
