"""Agent node functions for the LangGraph pipeline.

Each function:
  1. Reads what it needs from state.
  2. Builds a prompt + invokes its LLM.
  3. Returns a partial state dict — LangGraph merges automatically.

CRITICAL: each function returns its trail contribution as a single-item list,
NOT the full updated trail. The Annotated[list, add] reducer on state.py
concatenates these. Returning the full list would clobber parallel writes.
"""
from __future__ import annotations

import json
import time

from langchain_core.messages import HumanMessage, SystemMessage

from .llms import Role, get_llm, get_mock_llm
from .prompts import (
    BEAR_SYSTEM,
    BULL_SYSTEM,
    FUND_MANAGER_SYSTEM,
    FUNDAMENTALS_SYSTEM,
    NEWS_SYSTEM,
    RISK_SYSTEM,
    SENTIMENT_SYSTEM,
    TECHNICAL_SYSTEM,
    TRADER_SYSTEM,
)
from .state import TradingState
from .tilt_client import MockTiltClient

# Module-level switch — flipped by run.py before the graph executes.
USE_MOCK_LLMS = False


def _llm_for(role: Role):
    return get_mock_llm(role) if USE_MOCK_LLMS else get_llm(role)


def _trail(role: str, output: str) -> list[dict]:
    """Single-item trail list — concatenated by the reducer."""
    return [{"role": role, "output": output, "timestamp": int(time.time())}]


# ---- Stage 1: Analyst Team (parallel) ---------------------------------------

def fundamentals_analyst(state: TradingState) -> dict:
    msg = HumanMessage(
        content=(
            f"Cycle date: {state['cycle_date']}\n"
            f"Ticker: {state['ticker']}\n\n"
            f"Fundamentals snapshot:\n"
            f"{json.dumps(state['market_data']['fundamentals'], indent=2)}"
        )
    )
    res = _llm_for("fundamentals").invoke(
        [SystemMessage(content=FUNDAMENTALS_SYSTEM), msg]
    )
    return {
        "fundamentals_report": res.content,
        "reasoning_trail": _trail("fundamentals_analyst", res.content),
    }


def technical_analyst(state: TradingState) -> dict:
    md = state["market_data"]
    msg = HumanMessage(
        content=(
            f"Cycle date: {state['cycle_date']}\n"
            f"Ticker: {state['ticker']}\n\n"
            f"OHLCV:\n{json.dumps(md['ohlcv'], indent=2)}\n\n"
            f"Technicals:\n{json.dumps(md['technicals'], indent=2)}"
        )
    )
    res = _llm_for("technical").invoke(
        [SystemMessage(content=TECHNICAL_SYSTEM), msg]
    )
    return {
        "technical_report": res.content,
        "reasoning_trail": _trail("technical_analyst", res.content),
    }


def news_analyst(state: TradingState) -> dict:
    msg = HumanMessage(
        content=(
            f"Cycle date: {state['cycle_date']}\n"
            f"Ticker: {state['ticker']}\n\n"
            f"Recent news:\n{json.dumps(state['market_data']['news'], indent=2)}"
        )
    )
    res = _llm_for("news").invoke([SystemMessage(content=NEWS_SYSTEM), msg])
    return {
        "news_report": res.content,
        "reasoning_trail": _trail("news_analyst", res.content),
    }


def sentiment_analyst(state: TradingState) -> dict:
    msg = HumanMessage(
        content=(
            f"Cycle date: {state['cycle_date']}\n"
            f"Ticker: {state['ticker']}\n\n"
            f"Sentiment data:\n{json.dumps(state['market_data']['sentiment'], indent=2)}"
        )
    )
    res = _llm_for("sentiment").invoke(
        [SystemMessage(content=SENTIMENT_SYSTEM), msg]
    )
    return {
        "sentiment_report": res.content,
        "reasoning_trail": _trail("sentiment_analyst", res.content),
    }


# ---- Stage 2: Bull/Bear debate ----------------------------------------------

def _all_analyst_reports(state: TradingState) -> str:
    return (
        f"=== Fundamentals ===\n{state.get('fundamentals_report', '')}\n\n"
        f"=== Technical ===\n{state.get('technical_report', '')}\n\n"
        f"=== News ===\n{state.get('news_report', '')}\n\n"
        f"=== Sentiment ===\n{state.get('sentiment_report', '')}"
    )


def bull_researcher(state: TradingState) -> dict:
    msg = HumanMessage(
        content=(
            f"Cycle date: {state['cycle_date']}\n"
            f"Ticker: {state['ticker']}\n\n"
            f"Analyst reports:\n{_all_analyst_reports(state)}\n\n"
            "Make the strongest honest case for going LONG. Address the strongest "
            "bear argument you can anticipate."
        )
    )
    res = _llm_for("bull").invoke([SystemMessage(content=BULL_SYSTEM), msg])
    return {
        "bull_argument": res.content,
        "reasoning_trail": _trail("bull_researcher", res.content),
    }


def bear_researcher(state: TradingState) -> dict:
    msg = HumanMessage(
        content=(
            f"Cycle date: {state['cycle_date']}\n"
            f"Ticker: {state['ticker']}\n\n"
            f"Analyst reports:\n{_all_analyst_reports(state)}\n\n"
            f"Bull's case to engage with:\n{state.get('bull_argument', '')}"
        )
    )
    res = _llm_for("bear").invoke([SystemMessage(content=BEAR_SYSTEM), msg])
    return {
        "bear_argument": res.content,
        "reasoning_trail": _trail("bear_researcher", res.content),
    }


# ---- Stage 3: Trader --------------------------------------------------------

def trader(state: TradingState) -> dict:
    msg = HumanMessage(
        content=(
            f"Cycle date: {state['cycle_date']}\n"
            f"Ticker: {state['ticker']}\n\n"
            f"Bull case:\n{state.get('bull_argument', '')}\n\n"
            f"Bear case:\n{state.get('bear_argument', '')}\n\n"
            f"Portfolio context:\n"
            f"{json.dumps(state['market_data']['portfolio_context'], indent=2)}\n\n"
            f"Recent OHLCV:\n{json.dumps(state['market_data']['ohlcv'], indent=2)}\n\n"
            "Output the trade proposal as a single JSON object. No prose."
        )
    )
    res = _llm_for("trader").invoke([SystemMessage(content=TRADER_SYSTEM), msg])

    # Parse the JSON. Trader is told to output ONLY JSON; if it slips into
    # prose, take the first {...} block.
    text = res.content
    proposal: dict
    try:
        proposal = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            proposal = {
                "ticker": state["ticker"],
                "direction": "hold",
                "size_pct": 0.0,
                "thesis": "parse failed",
            }
        else:
            try:
                proposal = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                proposal = {
                    "ticker": state["ticker"],
                    "direction": "hold",
                    "size_pct": 0.0,
                    "thesis": "parse failed",
                }

    return {
        "trade_proposal": proposal,
        "reasoning_trail": _trail("trader", json.dumps(proposal)),
    }


# ---- Stage 4: Risk Manager --------------------------------------------------

def risk_manager(state: TradingState) -> dict:
    msg = HumanMessage(
        content=(
            f"Trade proposal:\n{json.dumps(state['trade_proposal'], indent=2)}\n\n"
            f"Portfolio context:\n"
            f"{json.dumps(state['market_data']['portfolio_context'], indent=2)}\n\n"
            "Apply the constraints and return decision + reasoning."
        )
    )
    res = _llm_for("risk").invoke([SystemMessage(content=RISK_SYSTEM), msg])
    text = res.content

    # Parse decision robustly: prefer the "decision: <verb>" line; fall back
    # to whole-word match. Substring match on "veto" gets fooled by "vetoing".
    import re

    decision = "approve"
    explicit = re.search(r"decision\s*:\s*(approve|modify|veto)", text, re.IGNORECASE)
    if explicit:
        decision = explicit.group(1).lower()
    else:
        for keyword in ("veto", "modify", "approve"):
            if re.search(rf"\b{keyword}\b", text, re.IGNORECASE):
                decision = keyword
                break

    return {
        "risk_decision": decision,
        "risk_reasoning": text,
        "reasoning_trail": _trail("risk_manager", text),
    }


# ---- Stage 5: Fund Manager + execution --------------------------------------

def fund_manager(state: TradingState) -> dict:
    msg = HumanMessage(
        content=(
            f"Trade proposal:\n{json.dumps(state['trade_proposal'], indent=2)}\n\n"
            f"Risk verdict: {state.get('risk_decision', '')}\n"
            f"Risk reasoning:\n{state.get('risk_reasoning', '')}\n\n"
            "Make the final approve/reject call."
        )
    )
    res = _llm_for("fund_manager").invoke(
        [SystemMessage(content=FUND_MANAGER_SYSTEM), msg]
    )
    text = res.content

    decision = "rejected"
    # Match "decision: approved|rejected" line; fall back to word boundaries
    import re

    explicit = re.search(r"decision\s*:\s*(approved|rejected)", text, re.IGNORECASE)
    if explicit:
        decision = explicit.group(1).lower()
    elif re.search(r"\bapproved\b", text, re.IGNORECASE) and not re.search(
        r"\brejected\b", text, re.IGNORECASE
    ):
        decision = "approved"

    update: dict = {
        "fund_manager_decision": decision,
        "reasoning_trail": _trail("fund_manager", text),
    }

    if decision == "approved":
        client = MockTiltClient(vault_id="vault_quant_001")
        result = client.execute_trade(state["trade_proposal"])
        update["execution_result"] = result
        # Append the execution event to the trail too
        update["reasoning_trail"] = update["reasoning_trail"] + _trail(
            "tilt_execution", json.dumps(result)
        )

    return update
