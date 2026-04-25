"""Pipeline state — what each node reads and writes.

Using TypedDict (LangGraph's canonical pattern) rather than Pydantic so that
graph reducers compose cleanly. Fields are populated as the cycle progresses;
unset fields are absent from the dict, not None.

The four analyst nodes run in PARALLEL, so any field they all write to must
have a reducer. We mark `reasoning_trail` with `Annotated[list, add]` so each
analyst's appended entries concatenate cleanly instead of clobbering.
"""
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict


class TradingState(TypedDict, total=False):
    # Inputs (set by cycle trigger)
    ticker: str
    cycle_date: str
    market_data: dict[str, Any]

    # Stage 1 — Analyst reports
    fundamentals_report: str
    technical_report: str
    news_report: str
    sentiment_report: str

    # Stage 2 — Bull/Bear debate
    bull_argument: str
    bear_argument: str
    debate_round: int

    # Stage 3 — Trader proposal
    trade_proposal: dict[str, Any]

    # Stage 4 — Risk decision
    risk_decision: str
    risk_reasoning: str

    # Stage 5 — Fund Manager + execution
    fund_manager_decision: str
    execution_result: dict[str, Any]

    # Audit trail — list concatenation reducer for parallel writes
    reasoning_trail: Annotated[list[dict[str, Any]], add]
