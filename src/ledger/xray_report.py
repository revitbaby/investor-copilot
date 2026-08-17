"""QDII 季报原文 → X-Ray 桶的确定性解析器（纯函数，不触网）。

口径（SOP 见 docs/code-standards.md「账本写入契约」）：
- 地区分布节（QDII 季报强制披露，占净值比）→ CN/HK/US_equity，其他地区 → other
- 基金投资明细按名称/管理人关键词分类（美国 ETF 提供商 → US_equity；
  Taiwan/Korea/港韩 等 → other；未命中 → other + 待人工确认 note）
- 债券 = 5.1 固定收益投资金额 ÷ 净资产（净资产 = 地区合计公允价值 ÷ 合计占净值比）
- 现金 = 残差（货币 + 其他资产的合并近似，季报级精度）

前十重仓外推法仅在本解析器不可用（无地区分布节）时由 Agent 兜底使用。
"""

from __future__ import annotations

import re
from datetime import date

REGION_TO_BUCKET = {
    "中国内地": "CN_equity",
    "中国大陆": "CN_equity",
    "中国": "CN_equity",
    "中国香港": "HK_equity",
    "美国": "US_equity",
}
KNOWN_REGIONS = (
    "中国内地", "中国大陆", "中国香港", "中国台湾", "美国", "中国",
    "韩国", "日本", "德国", "英国", "法国", "瑞士", "荷兰", "瑞典",
    "意大利", "西班牙", "印度", "越南", "新加坡", "澳大利亚", "加拿大",
    "印度尼西亚", "泰国", "巴西", "墨西哥", "南非", "爱尔兰", "开曼群岛",
)

# 基金明细分类：先判 OTHER 关键词，再判美国提供商，否则 other + 待确认
#（pdftotext 会把单词断行，分类前先去空格；管理人名也可命中——名称与
#  管理人在部分排版中会分离，如 Rafferty=Direxion 管理人、CSOP=南方东英）
FUND_OTHER_KEYWORDS = ("Taiwan", "台湾", "Korea", "韩国", "Hynix", "港韩",
                       "Japan", "日本", "MSCITaiwan", "CSOP", "南方东英")
FUND_US_KEYWORDS = ("Direxion", "Rafferty", "Roundhill", "SPDR",
                    "StateStreet", "SSgA", "BlackRock", "Invesco", "Vanguard",
                    "ProShares", "iShares", "Nasdaq", "S&P")

_REGION_HEADING = "在各个国家（地区）证券市场的股票及存托凭证投资分布"
_PCT_RE = re.compile(r"^\d{1,3}\.\d{1,2}$")
_VALUE_RE = re.compile(r"^\d{1,3}(,\d{3})+\.\d{1,2}$")
_PAGE_RE = re.compile(r"^第\s*\d+\s*页\s*共\s*\d+\s*页$")
_CN_NUM = str.maketrans({"〇": "0", "零": "0", "O": "0", "一": "1", "二": "2",
                         "三": "3", "四": "4", "五": "5", "六": "6", "七": "7",
                         "八": "8", "九": "9"})

_QUARTER_END = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}


class XrayReportParseError(ValueError):
    pass


def report_period(text: str) -> date:
    """从报告标题解析报告期（支持阿拉伯/中文数字、数字间空格、换行）。"""
    for candidate in (text, text.translate(_CN_NUM)):
        m = re.search(
            r"(2\s*0\s*\d\s*\d)\s*年\s*第\s*([1-4])\s*季度报告", candidate
        )
        if m:
            year = re.sub(r"\s", "", m.group(1))
            return date.fromisoformat(f"{year}-{_QUARTER_END[int(m.group(2))]}")
    raise XrayReportParseError("无法从标题识别报告期（第 N 季度报告）")


def _lines(text: str) -> list[str]:
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or _PAGE_RE.match(line) or "季度报告" in line and "第" in line:
            continue
        out.append(line)
    return out


def _is_pct(line: str) -> bool:
    return bool(_PCT_RE.match(line)) and 0 < float(line) <= 100


def _is_value(line: str) -> bool:
    return bool(_VALUE_RE.match(line))


def parse_region_allocation(text: str) -> tuple[dict[str, float], float, float]:
    """地区分布节 → ({地区: 占净值小数}, 合计占比小数, 合计公允价值)。

    行式（地区→金额→百分比）与列式（地区…金额…百分比…）排版兼容：
    地区、金额、百分比各入 FIFO 队列，百分比到达时弹出最老的地区与金额配对；
    无待配地区时的金额/百分比归入合计（「合计」标签前后两种排版均覆盖）。
    """
    idx = text.find(_REGION_HEADING)
    if idx < 0:
        raise XrayReportParseError("季报中无地区分布节（非 QDII 或排版未覆盖）")
    section = text[idx:]
    lines = _lines(section)

    pairs: dict[str, float] = {}
    pending_regions: list[str] = []
    pending_values: list[float] = []
    total_pct: float | None = None
    total_value = 0.0
    for line in lines:
        if total_pct is not None and line.startswith("注"):
            break
        if line == "合计":
            continue
        if line in KNOWN_REGIONS:
            if line not in pairs:
                pending_regions.append(line)
        elif _is_value(line):
            pending_values.append(float(line.replace(",", "")))
        elif _is_pct(line):
            if pending_regions:
                region = pending_regions.pop(0)
                pairs[region] = float(line) / 100.0
                if pending_values:
                    pending_values.pop(0)
            elif pairs and total_pct is None:
                total_pct = float(line) / 100.0
                if pending_values:
                    total_value = pending_values.pop(0)
    if not pairs:
        raise XrayReportParseError("地区分布节解析为空")
    if total_pct is None:
        total_pct = sum(pairs.values())
    if abs(sum(pairs.values()) - total_pct) > 0.005:
        raise XrayReportParseError(
            f"地区合计校验失败：分项和 {sum(pairs.values()):.4f} ≠ 合计 {total_pct:.4f}"
        )
    if total_value <= 0:
        # 合计行未解析到时，用任一地区金额反推净资产亦可，此处退化为 0（债券按 0 计）
        total_value = 0.0
    return pairs, total_pct, total_value


def parse_fund_holdings(text: str) -> list[tuple[str, float]]:
    """5.9 基金投资明细 → [(名称上下文, 占净值小数)]。"""
    m = re.search(r"前十名基金投资明细(.*?)(?:5\.10|§6|\n6\.|$)", text, re.S)
    if not m:
        return []
    body = m.group(1)
    if "未持有基金" in body or re.search(r"^\s*无[。\s]", body):
        return []
    entries: list[tuple[str, float]] = []
    buffer: list[str] = []
    for line in _lines(body):
        if _is_pct(line):
            name = " ".join(buffer)
            buffer = []
            if name:
                entries.append((name, float(line) / 100.0))
        elif _is_value(line) or line in ("-",) or line.isdigit():
            continue  # 金额、占位符、序号
        else:
            buffer.append(line)
    return entries


def classify_fund_holding(context: str) -> tuple[str, str | None]:
    """基金明细 → (bucket, note)。note 非空表示待人工确认。"""
    squashed = context.replace(" ", "")  # pdftotext 断词：MSCIT aiwan → MSCITaiwan
    if any(k in squashed for k in FUND_OTHER_KEYWORDS):
        return "other", None
    if any(k in squashed for k in FUND_US_KEYWORDS):
        return "US_equity", None
    return "other", f"基金明细未能自动分类，已并入 other：{context[:60]}"


def parse_bond_pct(text: str, region_total_pct: float, region_total_value: float) -> float:
    """债券占净值比 = 5.1 固定收益投资金额 ÷ 净资产。无则 0。"""
    if region_total_pct <= 0 or region_total_value <= 0:
        return 0.0
    nav = region_total_value / region_total_pct
    m = re.search(r"固定收益投资\s*\n+\s*([-\d,.]+)", text)
    if not m or m.group(1) in ("-", ""):
        return 0.0
    try:
        amount = float(m.group(1).replace(",", ""))
    except ValueError:
        return 0.0
    return amount / nav


def build_buckets(text: str) -> tuple[dict[str, float], date, list[str]]:
    """季报全文 → (X-Ray 桶, 报告期, 备注)。确定性主路径。"""
    as_of = report_period(text)
    regions, total_pct, total_value = parse_region_allocation(text)
    notes: list[str] = []

    buckets: dict[str, float] = {}
    for region, pct in regions.items():
        bucket = REGION_TO_BUCKET.get(region)
        if bucket is None:
            bucket = "other"
            notes.append(f"地区「{region}」{pct:.2%} 并入 other")
        buckets[bucket] = buckets.get(bucket, 0.0) + pct

    for context, pct in parse_fund_holdings(text):
        bucket, note = classify_fund_holding(context)
        buckets[bucket] = buckets.get(bucket, 0.0) + pct
        if note:
            notes.append(note)

    bond = parse_bond_pct(text, total_pct, total_value)
    if bond >= 0.0005:
        buckets["bond"] = buckets.get("bond", 0.0) + bond

    cash = 1.0 - sum(buckets.values())
    if cash < -0.005:
        raise XrayReportParseError(f"分项合计超 100%（残差 {cash:.4f}），解析不可信")
    buckets["cash"] = max(cash, 0.0)

    rounded = {k: round(v, 4) for k, v in buckets.items() if v >= 0.0005}
    drift = round(1.0 - sum(rounded.values()), 4)
    rounded["cash"] = round(rounded.get("cash", 0.0) + drift, 4)
    return rounded, as_of, notes
