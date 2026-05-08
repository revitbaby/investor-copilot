"""Regime-aware LLM narrative generation.

Generates 6 labeled sections from structured scoring results in a single LLM call.
Falls back to legacy output on failure.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)

SECTION_DELIMITER = "---SECTION:"
SECTION_NAMES = [
    "L1_SUMMARY", "L2_SUMMARY", "L3_SUMMARY",
    "EXECUTIVE_SUMMARY", "POSITION_NARRATIVE", "INVESTMENT_PLAYBOOK",
]

_SYSTEM_PROMPT = """You are a Senior Macro Strategist at a top-tier hedge fund.
You are provided with structured output from a three-layer regime scoring engine:
- Layer 1: Liquidity Foundation (Fed balance sheet, TGA, RRP, policy rates) → Position Ceiling
- Layer 2: Market Regime (8 indicators: SPX momentum, breadth, VIX, MOVE, credit, Gold-SPX correlation, DXY) → Utilization Rate
- Layer 3: Instant Risk Sentinels (VIX Spike, Credit Break, Bond Vol Spike, Trend Break) → Emergency Override
- Target Position Envelope = L1 Ceiling × L2 Utilization (or L3 override)

IMPORTANT RULES:
1. ALL conclusions MUST cite specific numbers (e.g., "VIX at 18.3, below the 25 threshold").
2. When signals contradict each other, you MUST explicitly identify the contradiction.
3. Recommendations MUST include specific actions and time frames. NEVER use vague phrases like "consider watching" or "monitor closely".
4. Position sizing references MUST align with the engine's computed Target Envelope — you explain WHY the numbers are what they are, you do NOT propose independent numbers.
5. You MUST write your ENTIRE response in {language}.

Output your response as exactly 6 labeled sections using this format:

---SECTION:L1_SUMMARY---
[1-2 sentences summarizing the liquidity foundation state and its meaning for positioning]

---SECTION:L2_SUMMARY---
[1-2 sentences summarizing the market regime, key signals, and contradictions]

---SECTION:L3_SUMMARY---
[1 sentence on sentinel status]

---SECTION:EXECUTIVE_SUMMARY---
[3-5 sentences: overall market state, regime color, core contradiction, single most critical risk factor]

---SECTION:POSITION_NARRATIVE---
[4-6 sentences: current vs target position gap, top 1-2 priority actions, timing window, next catalyst]
If no portfolio data is provided, state that no portfolio was uploaded and describe what the target envelope implies.

---SECTION:INVESTMENT_PLAYBOOK---
[Per asset class strategy:]
**Equities**: [specific recommendation]
**Bonds**: [duration bias and rationale]
**Crypto**: [risk stance]
**Cash**: [allocation rationale]
"""


@dataclass
class NarrativeResult:
    l1_summary: str = ""
    l2_summary: str = ""
    l3_summary: str = ""
    executive_summary: str = ""
    position_narrative: str = ""
    investment_playbook: str = ""
    raw_response: str = ""
    success: bool = False

    def to_dict(self) -> dict:
        return {
            "l1_summary": self.l1_summary,
            "l2_summary": self.l2_summary,
            "l3_summary": self.l3_summary,
            "executive_summary": self.executive_summary,
            "position_narrative": self.position_narrative,
            "investment_playbook": self.investment_playbook,
        }


def _parse_sections(response: str) -> dict[str, str]:
    """Parse a delimited LLM response into named sections."""
    sections: dict[str, str] = {}
    current_section = None
    current_lines: list[str] = []

    for line in response.split("\n"):
        stripped = line.strip()
        if stripped.startswith(SECTION_DELIMITER):
            if current_section:
                sections[current_section] = "\n".join(current_lines).strip()
            section_name = stripped.replace(SECTION_DELIMITER, "").rstrip("-").strip()
            if section_name in SECTION_NAMES:
                current_section = section_name
                current_lines = []
            else:
                current_section = None
                current_lines = []
        else:
            if current_section is not None:
                current_lines.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections


def generate_regime_narrative(
    regime_data: dict,
    advisory_data: dict | None = None,
    raw_market_data: dict | None = None,
    language: str = "en",
    timeout: float = 30.0,
) -> NarrativeResult:
    """Generate 6-section narrative from structured regime scoring results."""
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    model_name = os.getenv("LLM_MODEL", "google/gemini-2.0-flash-exp:free")

    lang_map = {"en": "English", "zh": "Chinese (Simplified)"}
    full_lang = lang_map.get(language, "English")

    context = {
        "regime_scoring": regime_data,
    }
    if advisory_data:
        context["position_advisory"] = advisory_data
    if raw_market_data:
        context["raw_market_data"] = raw_market_data

    context_json = json.dumps(context, indent=2, default=str)

    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PROMPT),
        ("user", "Here is the structured regime scoring data and market context:\n```json\n{context_json}\n```\n\nGenerate your 6-section assessment."),
    ])

    try:
        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0.3,
            request_timeout=timeout,
        )
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({
            "context_json": context_json,
            "language": full_lang,
        })
    except Exception as e:
        logger.warning("Regime narrative LLM call failed: %s", e)
        return NarrativeResult(raw_response=str(e), success=False)

    sections = _parse_sections(response)

    if len(sections) >= 4:
        return NarrativeResult(
            l1_summary=sections.get("L1_SUMMARY", ""),
            l2_summary=sections.get("L2_SUMMARY", ""),
            l3_summary=sections.get("L3_SUMMARY", ""),
            executive_summary=sections.get("EXECUTIVE_SUMMARY", ""),
            position_narrative=sections.get("POSITION_NARRATIVE", ""),
            investment_playbook=sections.get("INVESTMENT_PLAYBOOK", ""),
            raw_response=response,
            success=True,
        )
    else:
        # Parsing failed — use entire response as executive summary
        logger.warning("Section parsing failed (found %d/%d sections), using full response as fallback",
                       len(sections), len(SECTION_NAMES))
        return NarrativeResult(
            executive_summary=response,
            raw_response=response,
            success=False,
        )
