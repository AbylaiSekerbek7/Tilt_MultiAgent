"""LLM factory.

Production architecture (per Phase A) maps each agent role to a different
model, exploiting empirical strengths each model showed in Alpha Arena S1:

    Trader              -> Qwen3 Max
    Technical Analyst   -> DeepSeek V4
    Risk + Bull + Bear  -> Claude Sonnet 4.6
    Fund Manager        -> Claude Sonnet 4.6
    Fundamentals        -> Gemini 2.5 Pro
    News                -> GPT-5.2
    Sentiment           -> Claude Haiku 4.5
    Reflection          -> Llama 3.3 70B Instruct

The default production-equivalent path routes every role to its assigned model
through OpenRouter (one key, one billing relationship). The Anthropic-direct
path remains as a single-key fallback that runs Claude for every role.

Resolution order in `get_llm`:
  1. OPENROUTER_API_KEY set  -> ChatOpenAI against OpenRouter, asymmetric map
  2. ANTHROPIC_API_KEY set   -> ChatAnthropic, Claude-only fallback map
  3. neither                 -> raise
"""
from __future__ import annotations

import os
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

Role = Literal[
    "fundamentals",
    "technical",
    "news",
    "sentiment",
    "bull",
    "bear",
    "trader",
    "risk",
    "fund_manager",
    "reflection",
]

# Production map via OpenRouter. SKU IDs verified against
# https://openrouter.ai/api/v1/models on 2026-04-25. No substitutions —
# every architecture-spec model is currently listed.
OPENROUTER_ROLE_MAP: dict[Role, str] = {
    "fundamentals": "google/gemini-2.5-pro",
    "technical": "deepseek/deepseek-v4-pro",
    "news": "openai/gpt-5.2",
    "sentiment": "anthropic/claude-haiku-4.5",
    "bull": "anthropic/claude-sonnet-4.6",
    "bear": "anthropic/claude-sonnet-4.6",
    "trader": "qwen/qwen3-max",
    "risk": "anthropic/claude-sonnet-4.6",
    "fund_manager": "anthropic/claude-sonnet-4.6",
    # Reflection runs after a position closes — outside the single-cycle
    # prototype loop. Configured here so the production map is complete.
    "reflection": "meta-llama/llama-3.3-70b-instruct",
}

# Anthropic-direct fallback. Claude for every role so a single key works.
ANTHROPIC_FALLBACK_ROLE_MAP: dict[Role, str] = {
    "fundamentals": "claude-sonnet-4-6",
    "technical": "claude-sonnet-4-6",
    "news": "claude-sonnet-4-6",
    "sentiment": "claude-haiku-4-5-20251001",
    "bull": "claude-sonnet-4-6",
    "bear": "claude-sonnet-4-6",
    "trader": "claude-sonnet-4-6",
    "risk": "claude-sonnet-4-6",
    "fund_manager": "claude-sonnet-4-6",
    "reflection": "claude-sonnet-4-6",
}

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://github.com/meiirzhan/tilt-trading-agents",
    "X-Title": "Tilt AI Trading Agents",
}


def _temperature_for(role: Role) -> float:
    return 0.3 if role in ("trader", "risk", "fund_manager") else 0.5


def get_llm(role: Role, max_tokens: int = 1024) -> BaseChatModel:
    """Return a ChatModel for the given role.

    Prefers OPENROUTER_API_KEY (production-equivalent asymmetric assignment),
    falls back to ANTHROPIC_API_KEY (Claude for every role).
    """
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        return ChatOpenAI(
            model=OPENROUTER_ROLE_MAP[role],
            api_key=openrouter_key,
            base_url=OPENROUTER_BASE_URL,
            default_headers=OPENROUTER_HEADERS,
            max_tokens=max_tokens,
            temperature=_temperature_for(role),
        )

    if os.getenv("ANTHROPIC_API_KEY"):
        return ChatAnthropic(
            model=ANTHROPIC_FALLBACK_ROLE_MAP[role],
            max_tokens=max_tokens,
            temperature=_temperature_for(role),
        )

    raise RuntimeError(
        "No LLM provider key found. Set OPENROUTER_API_KEY (recommended — "
        "runs the full asymmetric architecture) or ANTHROPIC_API_KEY (Claude-"
        "only fallback). Or run with --mock to use deterministic stub LLMs."
    )


# ----- Mock LLM for offline/CI demos -----

class MockLLM:
    """Deterministic stub. Used when --mock is passed to run.py.

    Returns canned responses keyed on role so the graph can be exercised
    without API credentials. Output shape mirrors what the real chat model
    response looks like — a `.content` string on the response object.
    """

    def __init__(self, role: Role):
        self.role = role

    def invoke(self, messages):  # type: ignore[no-untyped-def]
        from langchain_core.messages import AIMessage

        return AIMessage(content=_MOCK_RESPONSES[self.role])


_MOCK_RESPONSES: dict[Role, str] = {
    "fundamentals": (
        "signal: bullish\nconfidence: 0.62\n"
        "thesis: NVDA's gross margin at 75.2% and operating margin at 61.2% reflect "
        "durable pricing power in accelerated computing. The 11.4% YoY revenue growth "
        "is moderating but still strong; forward P/E at 38.5 is rich but not unreasonable "
        "for the dominant data-center silicon vendor. Hyperscaler capex outlook is the "
        "key risk; partially offset by sovereign-fund diversification (Saudi deal). "
        "Earnings on 2026-05-21 is the next binary catalyst."
    ),
    "technical": (
        "signal: bullish\nconfidence: 0.68\n"
        "thesis: Above 50-MA (985.40) and 200-MA (902.15). RSI 62.3 is firm but not "
        "overbought. MACD bullish crossover 3 days ago. Watching support at 1010 and "
        "resistance at 1075. Volume today (45.2M) above 30-day avg (38.5M) confirms "
        "the move. Setup favors continuation on a clean break of 1075."
    ),
    "news": (
        "signal: neutral\nconfidence: 0.45\n"
        "thesis: Mixed news flow. Saudi sovereign-fund partnership is a positive "
        "long-tail catalyst but won't drive near-term numbers. Hyperscaler capex cuts "
        "at MSFT/META are the bigger near-term concern — directly affects ~88% of "
        "NVDA revenue. Foxconn ramp easing supply constraints is a small positive. Net: "
        "the bear case (capex) outweighs the bull cases (Saudi, supply) on a 30-day view."
    ),
    "sentiment": (
        "signal: bullish\nconfidence: 0.55\n"
        "thesis: Crowd is moderately bullish (X score +0.21, StockTwits 64% bull, WSB "
        "neutral). Mention volume elevated. Top topics dominated by Blackwell + Saudi "
        "deal — narratives that favor longs. Worth flagging: WSB sentiment near zero "
        "while X is positive suggests retail-sophisticate split."
    ),
    "bull": (
        "conviction: 0.55\n"
        "case: Three analysts lean bullish (fundamentals 0.62, technical 0.68, "
        "sentiment 0.55). Setup is clean: above key MAs, MACD recent crossover, RSI "
        "firm. Margin profile (75% GM, 61% OM) is the structural bull case. The Saudi "
        "deal is the kind of long-duration revenue diversification the bear capex "
        "narrative misses. Bear's capex point is real but: (a) it's already priced in "
        "(stock at -3.4% MoM), (b) NVDA's customer concentration is improving, (c) the "
        "5/21 earnings date gives a near-term re-rate catalyst. Position-size for asymmetry."
    ),
    "bear": (
        "conviction: 0.48\n"
        "case: News analyst is right — hyperscaler capex cuts at MSFT/META are the "
        "single most important data point and they're being underweighted by bull. "
        "~88% of NVDA revenue depends on these customers. Forward P/E 38.5 prices in "
        "continued growth that's mathematically harder when largest customers slow. "
        "Technical setup looks clean but is fragile — RSI 62.3 leaves limited room "
        "before overbought. Saudi deal is a 2-3 year revenue contributor at best, not "
        "a near-term offset. Risk-reward asymmetric to the downside if 5/21 earnings "
        "guide miss. Qualitative risk: governance — competitive AI silicon (AMD MI400, "
        "custom hyperscaler chips) is a 2026-2027 narrative shift the market hasn't priced."
    ),
    "trader": (
        '{"ticker": "NVDA", "direction": "long", "size_pct": 0.06, '
        '"entry_band": [1035, 1050], "target": 1095, "stop": 1015, '
        '"thesis": "Bull side wins on technical setup + earnings catalyst, but conviction is moderate; '
        "size at 6% of NAV (under the 15% cap) for asymmetric exposure with tight stop.\"}"
    ),
    "risk": (
        "decision: approve\n"
        "reasoning: Proposed 6% sizing well under the 15% single-position cap. "
        "Risk-reward = (1095-1042.50)/(1042.50-1015) = 52.50/27.50 = 1.91:1, just below "
        "the 2:1 floor — flagging but not vetoing given moderate conviction and no "
        "open NVDA exposure. Trailing drawdown is -1.8%, well within tolerance."
    ),
    "fund_manager": (
        "decision: approved\n"
        "final_size_pct: 0.06\n"
        "rationale: Trader proposal and risk verdict align; risk-reward marginal but acceptable given moderate conviction."
    ),
    "reflection": (
        "Reflection placeholder — invoked only after a position closes, "
        "outside the single-cycle prototype loop."
    ),
}


def get_mock_llm(role: Role) -> MockLLM:
    return MockLLM(role)
