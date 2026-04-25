# Phase A — Architecture & Strategic Positioning

> Source material for slides 3, 4, 5 of the Tilt submission deck.

## The backbone: 5-stage TradingAgents-derived pipeline

Inspired by **TradingAgents** (Xiao et al., arXiv [2412.20138](https://arxiv.org/abs/2412.20138), 52K GitHub stars, June 2025), with FinMem (arXiv 2311.13743) memory layer and FinCon (arXiv 2407.06567) reflection ideas. Adapted for tokenized equities on Robinhood Chain.

### Stage 1 — Analyst Team (parallel, fan-out)

Four analyst agents fire in parallel each cycle. Each writes a structured report (thesis + signal + confidence) to the shared workspace.

| Agent | Inputs | Output |
|---|---|---|
| Fundamentals Analyst | 10-K / 10-Q, earnings transcripts, financial ratios | Long-form thesis on intrinsic value |
| Technical Analyst | OHLCV, RSI, MACD, MA, volume profile | Pattern read + signal strength |
| News Analyst | Press releases, news APIs (Polygon / Finnhub), 8-K filings | Event summary + directional lean |
| Sentiment Analyst | X / Twitter, Reddit, StockTwits | Crowd sentiment score + dominant topics |

### Stage 2 — Research Team (sequential debate)

Bull and Bear researchers consume all 4 analyst reports and **debate over 2 structured rounds**. Each round, the researcher must (a) cite ≥1 piece of analyst evidence, (b) respond to the other's prior argument, (c) submit a confidence score. Transcript becomes input to the Trader.

### Stage 3 — Trader

Synthesizes the debate transcript + current portfolio context + episodic memory of similar past setups into a concrete proposal:
```
{ ticker, direction, size_pct, entry_band, target, stop, thesis }
```

### Stage 4 — Risk Manager

Evaluates proposal against vault constraints:
- Max single-position size (e.g. 15% of NAV)
- Sector concentration cap
- Trailing drawdown threshold
- Open-position correlation

Outputs: `approve` / `modify` / `veto` with reasoning.

### Stage 5 — Fund Manager

Final approval. On approve → calls Tilt OpenClaw skill → on-chain trade settles in seconds. Logs the full reasoning trail (analyst reports + debate + trader proposal + risk decision) to IPFS for audit.

---

## Three original contributions (where we win Pillar 1)

### 1. Empirically-grounded asymmetric LLM assignment

The lazy submission: "we run Claude vs GPT vs Gemini head-to-head." That's Alpha Arena from October 2025 — already done.

Our move: use Alpha Arena Season 1 results as labelled data on each model's behavioral personality, then assign each LLM to the *role* where it demonstrated empirical strength.

| Role | Model | Justification |
|---|---|---|
| Trader (decision) | Qwen3 Max | Won AA S1 (+22.3%, 43 trades / 17d, disciplined low-freq) |
| Technical Analyst | DeepSeek V3.1 | "Behaved like a quant asset-manager" (IWeaver). Peaked +125% mid-season |
| Risk Manager | Claude Sonnet 4.5 | Most cautious in AA S1 — wrong for trader, right for risk officer |
| Fundamentals Analyst | Gemini 2.5 Pro | 1M context — handles full 10-Ks |
| News Analyst | GPT-5 | Lost as trader (–62%) but text synthesis is unmatched |
| Sentiment Analyst | Claude Haiku 4.5 | Cheap, reliable; X/Reddit data fed via Apify scrape (more controllable than Grok API) |
| Bull / Bear Researchers | Claude Sonnet 4.5 (separate prompts) | Strong reasoning, role-play stability |

### 2. Equities-native cycle architecture

Alpha Arena runs every 2–3 minutes. Right for crypto perps, wrong for equities. Equities are not 24/7 perpetuals — they move on earnings, macro, sector flows, on slower timescales.

Three cycles:
- **Daily cycle** — full pipeline at 4 PM ET close → next-day positions
- **Event cycle** — triggered by earnings / M&A / FDA / 8-K → ticker-specific re-analysis
- **Intraday risk monitor** — every 15 min during market hours → Risk Manager + News Analyst only → catches stop-loss triggers and breaking news

Net effect: ~10× lower inference cost vs AA-style loop, dramatically reduced context fatigue, more honest about equity alpha decay.

### 3. Memory + reflection layer (FinMem-inspired)

Each agent has three memory tiers in Postgres:
- **Working** — current cycle inputs
- **Episodic** — past trades, vector-indexed by market regime / setup similarity
- **Reflective** — written self-critique after each closed position; appended to system prompt next cycle

This is how agents learn within a season without retraining. Direct response to AA S1's most-cited failure mode: same model, same mistake, every day, 17 days running.

---

## Battle format (sets up Pillar 3 / GTM)

Four vault personas with different agent compositions:

- **The Quant** — Technical-heavy, daily cycle, never holds >3 days
- **The Value Investor** — Fundamentals-heavy, slow cycles, 1–4 week holds
- **The Macro Trader** — News + Sentiment dominant, sector rotations
- **The Contrarian** — Bear researcher gets 2× weight in debate

Each vault becomes a tweetable character with its own handle. *Personalities, not just numbers.*

---

## Trade-offs (Pillar 1 self-awareness)

| Choice | Sacrifice | Justification |
|---|---|---|
| Multi-agent over single-agent | Higher cost, more orchestration | Robustness; AA exposed brittleness of single-agent |
| LangGraph over CrewAI/AutoGen | More boilerplate | Explicit control flow, deterministic execution, checkpointing |
| Daily cycle over real-time | Possible missed momentum alpha | 10× cost reduction; equities don't reward 2-min loops |
| Asymmetric LLM roles | Less pure "Claude vs GPT" battle framing | Better performance, *more interesting* GTM story |

## Failure modes & mitigations

1. **Look-ahead bias** — Hard-coded date filter on data sources; prompt explicitly states current date and forbids referencing future events.
2. **Prompt sensitivity** (AA lesson) — Lock prompts at season start; document any changes; A/B test before deploy.
3. **Debate divergence / pathological agreement** — Cap debate at 2 rounds; force orthogonal evidence (Bull = ≥1 quantitative; Bear = ≥1 qualitative risk).
4. **Cost runaway** — Anthropic prompt caching native; result caching for analyst outputs; cycle gating.
5. **Tilt API rate limits** — Queue with backoff; graceful degradation to "hold" if execution fails.
6. **Hallucinated tickers / sizes** — Hard validation layer between Fund Manager and execution; reject malformed JSON; reject sizes outside vault constraints.

## References

- Xiao et al., 2025. *TradingAgents: Multi-Agents LLM Financial Trading Framework.* arXiv:2412.20138
- Yu et al., 2023. *FinMem: Performance-Enhanced LLM Trading Agent with Layered Memory.* arXiv:2311.13743
- Yu et al., 2024. *FinCon: Synthesized LLM Multi-Agent System with Conceptual Verbal Reinforcement.* arXiv:2407.06567
- Nof1.ai, 2025. *Alpha Arena Season 1.* alphaarena.xyz (results: Qwen3 +22.3%, DeepSeek +4.9%, Claude –30.8%, Grok –45.3%, Gemini –56.7%, GPT-5 –62.7%)
- Trading-R1, 2025. *Financial Trading with LLM Reasoning via Reinforcement Learning.* arXiv:2509.11420
