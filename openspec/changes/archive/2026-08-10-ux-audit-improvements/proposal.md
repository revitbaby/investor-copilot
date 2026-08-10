## Why

UX 探索性测试（2026-05-18）在全部 4 个页面发现 14 个问题，其中 3 个 Critical 阻塞发布：首屏加载超 5 秒无反馈、A 股页面 API 超时无降级、股票行业名中英混用。专业金融工具的可信度直接依赖数据展示的一致性与加载状态的透明度，必须在下一个发布周期系统性修复。

## What Changes

- **加载进度透明化**：所有数据拉取页（main / China HK）在加载期间显示分项进度，超时后展示 stale 缓存数据而非永久 blocking
- **降级策略**：API 调用失败或超时时，展示最近缓存值 + `⚠️ 数据可能过时` 标注，而非空白页面
- **数据一致性**：股票行业名称统一为中文（申万分类）或英文（GICS），不再随原始数据源随机混用；体制评分表格 Threshold Hit 列不截断
- **移动端适配**：数据管理页缓存状态表格在 375px 下支持横向滚动或卡片布局；交易策略过滤器折叠为按钮
- **视觉打磨**：隐藏 Streamlit Deploy 按钮；导航首项从 "main" 改为语义化标题；补全信号图例；i18n 覆盖表格内指标行名
- **文件上传组件**：从首屏移至折叠区域，不再抢占核心视觉位置

## Capabilities

### New Capabilities

- `loading-progress-feedback`: 数据拉取期间的分项进度展示 + 超时降级策略（stale 值兜底）

### Modified Capabilities

- `fetch-progress-dialog`: 当前仅有加载动画骨架，需扩展为分项打勾式进度 + stale 降级渲染
- `data-management-page`: 缓存状态表格需支持移动端横向滚动 / 卡片布局
- `trading-strategy-ui`: 行业名标准化映射 + 信号图例 + 宏观上下文跳转链接
- `multipage-navigation`: 导航标题语义化 + 隐藏 Deploy 顶栏 + 文件上传组件重定位

## Impact

- `src/ui/app.py`：主页加载状态重构，文件上传组件重定位
- `src/ui/china_regime_components.py`：A 股分项加载进度 + stale 降级渲染
- `src/data/china_market_fetcher.py`：超时参数 + 返回 stale 值的错误边界
- `src/data/loader.py`：美股数据加载进度回调
- `src/utils/i18n.py`：补全指标行名、行业名国际化 key
- `pages/`：导航页面重命名（main → US_Markets）
- `.streamlit/config.toml`：`toolbarMode = "minimal"` 隐藏 Deploy 按钮
- `src/ui/app.py` Trading Strategy 区：行业名映射 + 信号图例组件
