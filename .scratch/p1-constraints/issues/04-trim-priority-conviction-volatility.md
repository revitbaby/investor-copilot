# 04 — 减仓优先级排序重构：conviction 全市场 + 52 周波动率

**What to build:** conviction 分级（S/A/B/C）扩展为全市场通用：任意市场个股均可打标，存储进账本（存储位置——主线映射表扩展 vs 独立表——是 spec 开放项，实施时裁定并回报；基金 conviction 手工维护直到 P3）。减仓优先级排序改为「低信念先砍 → 高波动先砍 → 盈利仓先砍」：波动率键从 beta_spx 替换为 52 周历史波动率（经账本 QuoteProvider 历史价格计算），使排序对全市场标的成立（ADR-0009）。

**Blocked by:** 03 — Position Advisor 接入账本 + 砍 options/beta_spx/仓位上限矩阵

**Status:** ready-for-agent

- [ ] 任意市场个股的 conviction 可录入账本并在 Advisor 中展示/参与排序
- [ ] 排序键为 conviction 升序 → 52 周波动率降序 → 浮盈降序，不再有 beta_spx
- [ ] 52 周波动率经注入的 QuoteProvider 计算，测试不走网络
- [ ] conviction 存储位置已裁定并记录在 ticket 完成说明中
- [ ] 构造持仓的排序测试覆盖：同级信念比波动、同波动比浮盈、缺波动率数据的降级

**Parent spec:** .scratch/p1-constraints/spec.md（切片 2，User Stories 9、11）
