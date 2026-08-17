# Claude Code 使用规范 — investor-copilot

## 语言

**默认使用中文回复**。技术术语、金融指标名称、库名/API名、代码标识符可保留英文。除非用户主动用英文提问，避免全程英文回复。

## 项目概述

**Investor Copilot** — 面向单一个人投资者的**总资产配置 AI Copilot**（非宏观择时仪表盘）。

- **决策对象**：总账户资产配置（市场间怎么配、卫星仓多大、是否偏离基准）
- **配置模型**：核心-卫星；基准按 **10 年 5 倍（年化 17.5%）** 反推，10 倍不进公式；AI 卫星仓上限 **35%**（ADR-0018）
- **三层漏斗**：宏观（美股/A 股引擎→市场级约束；港股双引擎合成）→ 中观（投资主线+记分卡）→ 微观（尽调卡+基金 X-Ray）
- **仓位单一出处**：仓位数字只出自总资产层；微观层 / 技术模块 / LLM **不得**输出仓位建议

运行查阅层：`uv run streamlit run main.py`

## 权威文档

| 文档 | 用途 |
|------|------|
| [`CONTEXT.md`](CONTEXT.md) | 领域词汇表 |
| [`docs/adr/`](docs/adr/)（0001–0018） | 绑定裁决 |
| [`openspec/config.yaml`](openspec/config.yaml) | OpenSpec 项目上下文 |
| [`docs/code-standards.md`](docs/code-standards.md) | 代码规范、数据单位、API、测试、环境变量 |
| [`docs/architecture.md`](docs/architecture.md) | 目录树、双运行时、IA、仪式交互 |

冲突时以 ADR / `CONTEXT.md` 为准，勿重新发明。

## 建设路线（ADR-0011）

P0 总资产账本 → P1 约束改造+去糟粕 → P1.5 简版周报 → P2 主线记分卡 → P3 微观双轨 → P4 仪式全量。

当前可执行规格：[`.scratch/p0-ledger/spec.md`](.scratch/p0-ledger/spec.md)（`ready-for-agent`）。
