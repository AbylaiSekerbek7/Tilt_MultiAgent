"""LangGraph topology for the 5-stage trading pipeline.

Layout:

    START
      |
      +-> fundamentals_analyst ---+
      +-> technical_analyst   ----+--> bull_researcher --> bear_researcher
      +-> news_analyst        ----+                                |
      +-> sentiment_analyst   ----+                                v
                                                                trader
                                                                  |
                                                                  v
                                                              risk_manager
                                                                  |
                                                                  v
                                                              fund_manager
                                                                  |
                                                                  v
                                                                 END

The four analysts run in parallel because LangGraph fans out automatically
when multiple nodes have START as their predecessor with no order constraint.
The bull/bear sequence is deliberate — bear must respond to bull's case.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .agents import (
    bear_researcher,
    bull_researcher,
    fund_manager,
    fundamentals_analyst,
    news_analyst,
    risk_manager,
    sentiment_analyst,
    technical_analyst,
    trader,
)
from .state import TradingState


def build_graph():
    g = StateGraph(TradingState)

    # Stage 1 — Analyst Team (parallel)
    g.add_node("fundamentals", fundamentals_analyst)
    g.add_node("technical", technical_analyst)
    g.add_node("news", news_analyst)
    g.add_node("sentiment", sentiment_analyst)

    # Stage 2 — Research Team (sequential debate)
    g.add_node("bull", bull_researcher)
    g.add_node("bear", bear_researcher)

    # Stages 3/4/5
    g.add_node("trader", trader)
    g.add_node("risk", risk_manager)
    g.add_node("fund_manager", fund_manager)

    # Wiring: 4 analysts fan out from START
    g.add_edge(START, "fundamentals")
    g.add_edge(START, "technical")
    g.add_edge(START, "news")
    g.add_edge(START, "sentiment")

    # All 4 analysts feed into bull (LangGraph waits for all upstream nodes)
    g.add_edge("fundamentals", "bull")
    g.add_edge("technical", "bull")
    g.add_edge("news", "bull")
    g.add_edge("sentiment", "bull")

    # Bull -> bear (sequential debate)
    g.add_edge("bull", "bear")

    # Bear -> trader -> risk -> fund_manager -> END
    g.add_edge("bear", "trader")
    g.add_edge("trader", "risk")
    g.add_edge("risk", "fund_manager")
    g.add_edge("fund_manager", END)

    return g.compile()
