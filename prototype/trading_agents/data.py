"""Mock market data for the prototype demo.

In production, market_data is populated by the data-source layer:
- OHLCV + technicals from Polygon.io
- Fundamentals from Financial Modeling Prep + SEC EDGAR
- News from Finnhub + Polygon News
- Sentiment from Apify-scraped X + Reddit API

For the prototype we ship a frozen NVDA snapshot so anyone can run the demo
without paid data subscriptions.
"""
from __future__ import annotations

from typing import Any

NVDA_DEMO_DATA: dict[str, Any] = {
    "ticker": "NVDA",
    "cycle_date": "2026-04-25",
    "ohlcv": {
        "last_close": 1042.50,
        "prev_close": 1018.20,
        "day_change_pct": 2.39,
        "week_change_pct": 5.81,
        "month_change_pct": -3.42,
        "ytd_return_pct": 12.4,
        "volume_today": 45_200_000,
        "avg_volume_30d": 38_500_000,
    },
    "technicals": {
        "rsi_14": 62.3,
        "macd_signal": "bullish_crossover_3d_ago",
        "ma_50": 985.40,
        "ma_200": 902.15,
        "above_200ma": True,
        "support": 1010.0,
        "resistance": 1075.0,
    },
    "fundamentals": {
        "pe_ratio": 71.2,
        "forward_pe": 38.5,
        "ps_ratio": 32.4,
        "revenue_growth_yoy": 0.114,
        "gross_margin": 0.752,
        "operating_margin": 0.612,
        "fcf_margin": 0.484,
        "next_earnings_date": "2026-05-21",
        "summary_10k": (
            "NVIDIA is the market leader in accelerated computing, with data center "
            "revenue making up ~88% of total. Recent 10-Q noted moderating "
            "hyperscaler capex growth and inventory normalization. Management "
            "guided next-Q revenue at the midpoint of consensus."
        ),
    },
    "news": [
        {
            "date": "2026-04-24",
            "headline": "NVIDIA announces partnership with major Saudi sovereign fund for AI infrastructure",
            "source": "Reuters",
            "sentiment": "positive",
        },
        {
            "date": "2026-04-23",
            "headline": "Hyperscaler capex outlook cut at Microsoft and Meta — NVDA shares dip pre-market",
            "source": "Bloomberg",
            "sentiment": "negative",
        },
        {
            "date": "2026-04-22",
            "headline": "Blackwell B200 supply constraints easing, Foxconn ramp ahead of schedule",
            "source": "DigiTimes",
            "sentiment": "positive",
        },
    ],
    "sentiment": {
        "x_24h_mention_count": 18_400,
        "x_24h_sentiment_score": 0.21,  # -1 (bearish) to +1 (bullish)
        "x_top_topics": ["Blackwell", "AI infra", "Saudi deal", "hyperscaler capex"],
        "reddit_wsb_mentions_24h": 412,
        "reddit_wsb_sentiment": 0.05,
        "stocktwits_bullish_pct": 64,
    },
    "portfolio_context": {
        "vault": "The Quant",
        "current_nav_usd": 100_000,
        "open_positions": [
            {"ticker": "NVDA", "size_pct": 0.0, "unrealized_pnl_pct": 0.0},
            {"ticker": "TSLA", "size_pct": 0.08, "unrealized_pnl_pct": 0.034},
        ],
        "max_single_position_pct": 0.15,
        "trailing_drawdown_pct": -0.018,
    },
}


def load_demo_data() -> dict[str, Any]:
    """Return a deep-copy-safe snapshot of the demo dataset."""
    import copy

    return copy.deepcopy(NVDA_DEMO_DATA)
