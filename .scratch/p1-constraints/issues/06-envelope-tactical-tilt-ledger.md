# 06 — envelope 战术偏移接入总资产层

**What to build:** 宏观引擎的约束第一次落到总资产上（ADR-0002/0003）。新增战术偏移纯函数：把某市场 envelope（0–100% 市场内仓位）的 min/max 分别线性映射到该市场基准区间 [min, max]，得到该市场核心仓占总资产的当期许可区间（结果天然落在基准区间内）。账本门面新增只读聚合，按市场输出「实际占比 / 基准区间 / 引擎许可区间」三元组；总资产页渲染三层对照（遵循可视化三规则，ADR-0015），市场约束页新增"占总资产许可区间"视角。envelope 引擎本体与历史落盘格式零改动。基准未设定时显示"先定基准"引导而非报错。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 各市场（A股/美股）许可区间由 envelope 映射得出，且永不突破基准区间
- [ ] 总资产页可见各市场实际占比 vs 基准区间 vs 许可区间的三层对照
- [ ] 基准未设定时许可区间视图为引导态而非报错
- [ ] envelope 引擎计算逻辑与历史 CSV 格式未变，既有测试不受影响
- [ ] 映射纯函数测试覆盖：clamp、基准未设定、空账本边界；门面聚合沿用 temp SQLite + 注入 QuoteProvider 模式

**Parent spec:** .scratch/p1-constraints/spec.md（切片 3，User Stories 17–22）
