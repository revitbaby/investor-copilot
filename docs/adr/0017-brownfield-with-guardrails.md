# 不从零重写：同 repo 内新域绿地开发 + 显式拆除 + 强制边界护栏

针对"旧 codebase 技术债会被无意继承"的担忧，裁决不开新 repo、不整体重写，采用：

1. **新域绿地**：`src/ledger/`、`src/themes/`、`src/dossier/`、`jobs/` 全部新写，P0 阶段不触碰旧代码。
2. **显式拆除**：被 ADR-0006/0009 判死的代码（金字塔仓位、固定止损止盈、Position Advisor CSV/options、北向日度调整项）作为独立的 openspec 拆除 change 执行并物理删除，不留注释僵尸；对应旧 spec requirement 同步标注 deprecated。旧 UI 页面按新 IA（ADR-0015）全部新写文件，旧文件 P1 结束时删除。
3. **import 边界规则（机械强制）**：新域与 `jobs/` 只准 import `src/analysis/`、`src/data/`、`src/utils/`，**永远不准 import `src/ui/`**；`src/ui/` 只读不写。用 import-linter 或架构测试在 pytest 中强制，P1.5 起生效。

## 理由

债与资产分布不均：债集中在 UI 层（app.py 单体、打开即算、session_state 耦合）——已被 ADR-0012/0015 排期拆除；资产集中在数据/引擎层——`src/data/` 编码了大量 API 配额换来的知识（行数截断绕行、单位换算、T-1 规则、缓存自愈），`src/analysis/`+`src/regime/` 有 99 个测试护体，`data_cache/` 有 2015 至今回填历史。从零重写 = 扔掉资产、把反正要重写的东西再写一遍。"被动继承"用几十行架构测试防御即可，不需要付出重写取数层的代价。

2026-08-07，经 grilling 会话裁决。
