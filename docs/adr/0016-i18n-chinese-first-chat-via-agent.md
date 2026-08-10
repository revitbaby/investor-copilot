# i18n 降级为中文优先；Chat 查询以 Agent 会话为载体，不在 Streamlit 内造

## i18n 中文优先

系统用户只有一人，工作语言中文。裁决：`t()` 基础设施保留（拆除是负收益），新功能只注册中文 key，英文翻译停止供给，已有翻译不删。金融术语精确性靠中文文案内保留英文术语解决（与 CLAUDE.md 既有风格一致）。原"必须中英双语"约束废止。

## Chat 载体

深挖型 ad-hoc 查询（"帮我看看这只基金"、"给某股票跑尽调卡"）直接在 Cursor/Claude Agent 会话中进行——Agent 已具备全部 Skill（ttfund、repo 代码、数据文件、账本读取），是现成且能力最强的 chat 载体。Streamlit 内不做对话界面。

理由：在 Streamlit 内嵌 chat 等于重新发明残血版 Agent 运行时（工具调用、Skill 接入、会话管理全要自建）；ADR-0012 已确立 Agent 会话为仪式运行时，兼任 ad-hoc 查询运行时是零成本顺延。

2026-08-07，经 grilling 会话裁决。
