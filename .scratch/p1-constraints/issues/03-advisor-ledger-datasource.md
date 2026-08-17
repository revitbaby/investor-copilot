# 03 — Position Advisor 接入账本 + 砍 options/beta_spx/仓位上限矩阵

**What to build:** Position Advisor 数据源从 CSV 手工上传切换为总资产账本只读门面（ADR-0009）。新增 Ledger→Advisor 适配层（薄，只做数据形状转换，不含业务规则）；删除 CSV 上传入口与解析器；删除 options/beta_spx 字段及一切派生逻辑（名义本金上限、SEVERE CONTRACTION 只留 S 级等）；废弃 conviction×体制仓位上限矩阵及其配置——Advisor 不再输出任何仓位上限/目标仓位数字（仓位单一出处，ADR-0006）。减仓优先级排序的旧键（beta_spx）在本 ticket 可临时保留，ticket 04 替换。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] Advisor 页面不再有 CSV 上传入口，持仓数据来自账本
- [ ] Advisor 视图覆盖 A股/港股/美股/基金四类资产
- [ ] 界面与数据模型中不再出现 options、beta_spx 相关内容
- [ ] conviction×体制仓位上限矩阵及其配置已删除，Advisor 输出不含仓位数字
- [ ] 适配层有 temp SQLite 端到端测试；compute_advisory 纯函数测试更新后全绿

**Parent spec:** .scratch/p1-constraints/spec.md（切片 2，User Stories 7、8、10、12）
