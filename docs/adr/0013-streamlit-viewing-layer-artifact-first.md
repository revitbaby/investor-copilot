# Streamlit 留任查阅层，确立工件优先原则

用户的消费模式：手机只看周报/告警（邮件送达），深度查阅都在电脑前。裁决：

- **工件优先（Artifact-First）**：周报/月审/年审的本体是 markdown/HTML 工件，邮件送达即完成主要信息消费，不依赖打开任何 app。
- **Streamlit 留任查阅层**：只服务电脑前的深挖场景（交互式图表、账本明细、历史对比）。ADR-0012 已将其降级为"读文件、画图"，rerun 模型的计算耦合弱点被架构切除。
- P4 时若 Streamlit 打开频率趋近于零，直接降级为内部调试工具，不再投入。

## Considered Options

- **静态站点生成**（Observable Framework / Evidence / Quarto）：被否——唯一胜出场景是手机深度查阅，与用户实际模式不符；需重写全部 plotly 图表与约 6000 行展示逻辑，交互能力还会缩水。
- **平迁 Dash/Panel/marimo**：被否——迁移成本换不来质变。
- **Next.js + FastAPI 全栈**：被否——单用户系统的过度工程。

2026-08-06，经 grilling 会话裁决。
