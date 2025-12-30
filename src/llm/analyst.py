import os
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

class MacroAnalyst:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
        # Default to a capable model on OpenRouter
        self.model_name = os.getenv("LLM_MODEL", "google/gemini-2.0-flash-exp:free")
        
        if not self.api_key:
            print("Warning: OPENAI_API_KEY not set. LLM features will fail.")
            
        self.llm = ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=0.3
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a Senior Macro Strategist at a top-tier hedge fund.
Your job is to analyze the "Net Liquidity" environment and provide a clear, actionable market assessment.

Key Definitions:
- Net Liquidity = Fed Assets (WALCL) - Reverse Repo (RRP) - TGA.
- Rising Net Liquidity -> Bullish (Risk-On).
- Falling Net Liquidity -> Bearish (Risk-Off).
- VIX < 20 & MOVE > 120 -> DANGER SIGNAL (Bond volatility warning).

Your Output Format MUST be valid Markdown.
IMPORTANT: You MUST write your response in {language}.

Structure:
# Market Status: [GREEN / YELLOW / RED]

## Executive Summary
[1-2 sentences on the current regime]

## Liquidity Analysis
- **Fed Balance Sheet**: [Analysis]
- **TGA/RRP Flows**: [Analysis]
- **Net Liquidity Trend**: [Analysis]

## Risk Signals
- **Volatility (VIX/MOVE)**: [Analysis]
- **Cross-Asset (DXY/Gold/BTC)**: [Analysis]

## Investment Playbook
- **Equities**: [Overweight/Neutral/Underweight]
- **Bonds**: [Duration bias]
- **Crypto**: [Risk stance]
"""),
            ("user", "Here is the current market data:\n```json\n{context_json}\n```\n\nProvide your strategic assessment.")
        ])
        
        self.chain = self.prompt | self.llm | StrOutputParser()
        
    def generate_report(self, context_data: dict, language: str = "en") -> str:
        """
        Generate a report based on the context data.
        """
        # Convert context to JSON string
        context_json = json.dumps(context_data, indent=2, default=str)
        
        # Map code to full language name for clearer instruction
        lang_map = {"en": "English", "zh": "Chinese (Simplified)"}
        full_lang = lang_map.get(language, "English")
        
        try:
            response = self.chain.invoke({
                "context_json": context_json,
                "language": full_lang
            })
            return response
        except Exception as e:
            return f"Error generating report: {e}"

