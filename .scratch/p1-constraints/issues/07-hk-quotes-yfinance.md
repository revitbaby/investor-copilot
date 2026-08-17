# 07 — 港股取价：yfinance `.HK` 替换 None placeholder

**What to build:** 消除港股取价盲区（ADR-0008）。废弃股票取数中"港股返回 None"的 placeholder 分支，港股标的日线经 yfinance `.HK` 正常取价，并入现有生产 QuoteProvider；取价失败沿用 stale 降级规则（最近有效价 + 标记），快照序列不断档。账本周度快照中港股持仓估值不再降级。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 港股标的（如 0700.HK）日线数据可正常获取，不再有 None placeholder 分支
- [ ] 账本快照中港股持仓按真实价格估值
- [ ] 取价失败时使用最近有效价并标记 stale
- [ ] HK 取价路径经注入 QuoteProvider 测试；yfinance 壳手动验证

**Parent spec:** .scratch/p1-constraints/spec.md（切片 4，User Story 23）
