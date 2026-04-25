# Tilt AI Trading Agents — prototype

Working multi-agent pipeline for trading tokenized equities on Tilt Protocol /
Robinhood Chain. Submitted as the prototype artifact for the Tilt AI Agents
Trading Battle challenge.

## What this is

A 5-stage hierarchical agent system, derived from the **TradingAgents** paper
([arXiv 2412.20138](https://arxiv.org/abs/2412.20138)) and adapted for tokenized
equities on Robinhood Chain (Chain ID 46630). Each cycle is a fan-out / fan-in
LangGraph computation:

```
                            ┌──────────────────┐
                            │  Cycle trigger   │
                            └────────┬─────────┘
                                     │ (fan-out)
              ┌──────────┬───────────┼───────────┬──────────┐
              ▼          ▼           ▼           ▼          ▼
       Fundamentals  Technical    News      Sentiment   (parallel)
              └──────────┴───────────┼───────────┴──────────┘
                                     ▼ (fan-in)
                          Bull researcher  ⇄  Bear researcher
                                     │
                                     ▼
                                  Trader (proposal)
                                     │
                                     ▼
                              Risk manager (veto / modify / approve)
                                     │
                                     ▼
                              Fund manager → Tilt smart contract
```

Full architectural rationale, including the empirical justification for each
LLM-to-role assignment and the equities-native multi-cycle design, is in
[`docs/01-architecture.md`](./docs/01-architecture.md).

## Quick start

```bash
# 1. Clone, then:
cd prototype
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Real asymmetric pipeline (recommended) — needs OPENROUTER_API_KEY.
#    Routes each role to its architecture-spec model: Qwen3 Max trader,
#    DeepSeek V4 technical, Gemini 2.5 Pro fundamentals, GPT-5.2 news,
#    Claude Sonnet 4.6 risk/bull/bear/fund-manager, Haiku 4.5 sentiment.
cp .env.example .env
# edit .env, add your OpenRouter key
python run.py

# 3. Offline demo — deterministic stub responses, no API keys needed
python run.py --mock

# 4. Anthropic-only fallback — set ANTHROPIC_API_KEY instead of OPENROUTER_API_KEY.
#    Simpler (Claude for every role) but doesn't exercise the asymmetric architecture.
python run.py
```

A successful run prints the full pipeline output to stdout (each agent's
report, the bull/bear debate, trader proposal, risk verdict, fund manager
decision, and a simulated on-chain transaction hash) and writes the entire
state — including the audit trail of every reasoning step — to
`output/run_<timestamp>.json`.

A reference mock run is checked in at
[`prototype/output/sample_run_NVDA.json`](./prototype/output/sample_run_NVDA.json).
A reference real-mode run produced via OpenRouter against the
architecture-spec asymmetric model assignment is at
[`prototype/output/sample_run_real_NVDA.json`](./prototype/output/sample_run_real_NVDA.json).
Nine more real runs (`prototype/output/run_real_NVDA_02.json` … `_10.json`)
plus a ten-run aggregate at
[`prototype/output/summary.json`](./prototype/output/summary.json) are
checked in too.

## Web UI (live demo for reviewers)

```bash
cd prototype
uvicorn web.app:app --host 0.0.0.0 --port 8000
# open http://localhost:8000
```

Browser UI with three tabs: **Run pipeline** (mock free / real capped at 10
runs per UTC day, agent outputs streamed live via SSE as each LangGraph node
completes), **Sample runs** (browse the 11 saved JSON outputs + summary),
**Architecture** (per-role model assignment table). Backed by FastAPI in
[`prototype/web/app.py`](./prototype/web/app.py); deploy instructions for
Fly.io (recommended), Render, and HuggingFace Spaces are in
[`prototype/web/DEPLOY.md`](./prototype/web/DEPLOY.md).

## Architecture in code

| File | What's in it |
|---|---|
| `trading_agents/state.py` | `TradingState` TypedDict. The `reasoning_trail` field uses `Annotated[list, add]` so the four parallel analysts can each contribute entries without clobbering. |
| `trading_agents/data.py` | Frozen NVDA market-data snapshot for the offline demo. In production, this is replaced by Polygon.io / FMP / Finnhub / Apify clients. |
| `trading_agents/tilt_client.py` | Mock Tilt Protocol client. Same interface as the production client. Returns deterministic tx_hash, chain_id 46630, block number. |
| `trading_agents/prompts.py` | All 9 system prompts, version-locked, with date guards forbidding look-ahead. |
| `trading_agents/llms.py` | LLM factory. Default path is `OPENROUTER_ROLE_MAP` — the asymmetric per-role assignment (Qwen3 → Trader, DeepSeek → Technical, Gemini → Fundamentals, GPT-5 → News, Claude Sonnet → Risk/Bull/Bear/FM, Haiku → Sentiment, Llama → Reflection) routed through OpenRouter on a single key. `ANTHROPIC_FALLBACK_ROLE_MAP` is a one-key Claude-only fallback. |
| `trading_agents/agents.py` | Each agent is a pure node function over state. Returns its trail entry as a single-item list — the reducer concatenates. |
| `trading_agents/graph.py` | LangGraph topology. Four `add_edge(START, …)` calls fan out the analysts; both researchers feed into the trader after sequential debate; trader → risk → fund_manager → END. |
| `run.py` | CLI entry point. `--mock` flag for offline demo; rich console output; writes full state to `output/`. |

## What this prototype demonstrates

1. **The 5-stage pipeline runs end-to-end.** From cycle trigger through
   on-chain execution stub, with every reasoning step persisted.
2. **Parallel fan-out works correctly.** All four analysts execute
   concurrently; the `Annotated[list, add]` reducer composes their audit
   contributions without conflict.
3. **The bull/bear debate is sequential and adversarial.** Bear sees Bull's
   case before responding; system prompts force engagement with the other
   side's evidence rather than parallel monologue.
4. **The trader output is structured JSON**, parsed and validated before
   reaching the risk manager. Defensive parsing handles slightly malformed
   model output without crashing.
5. **Risk decision is parsed robustly.** Word-boundary regex avoids the
   substring trap (e.g. matching "veto" inside the word "vetoing").
6. **Mock vs live LLM swap is a one-flag toggle.** `agents.USE_MOCK_LLMS`
   switches the entire graph between deterministic offline mode and live API
   calls. Live calls go to OpenRouter (asymmetric, default) or Anthropic
   (Claude-only fallback) depending on which key is set. Useful for CI and
   offline reviewer demos.
7. **The Tilt execution layer is mockable behind a clean interface.** The
   real production client and the mock share `execute_trade(proposal)` →
   `{tx_hash, chain_id, block_number, ...}`. Swap one for the other when
   testnet access lands.

## What this prototype is NOT

- It runs **one vault, one ticker, one cycle**. Production design is 4
  vaults × ~5 tickers × ~3 cycles/day. Multiplying out is straightforward —
  the graph and state are already vault-agnostic — but adds fixture data and
  scheduling that aren't useful for a reviewer's first read.
- Memory layer (working / episodic / reflective per Phase A) is **not**
  wired up here. Designed for it (each cycle's full state is persisted to
  disk; in production this becomes Postgres + pgvector). Adding it is ~half a
  day of work; deferred to keep the prototype scope honest.
- The Reflection Agent (Llama 3.3 70B) is configured in
  `llms.OPENROUTER_ROLE_MAP` but not invoked — it runs after a position
  closes, which is outside the single-cycle prototype loop.
- No real data-source integrations. NVDA snapshot is hand-curated for
  reproducibility.

## Why these specific choices

**LangGraph**, not CrewAI / AutoGen / Claude Agents SDK / custom: explicit
state machine, native checkpointing, deterministic replay (which we'll need
for trade audit), multi-LLM-provider support out of the box. The
[TradingAgents reference implementation](https://github.com/TauricResearch/TradingAgents)
also uses LangGraph, so the patterns transfer directly.

**Asymmetric LLM-to-role assignment** (`OPENROUTER_ROLE_MAP` in `llms.py`,
the default path when `OPENROUTER_API_KEY` is set): each LLM has a different
empirical personality under live trading pressure (Alpha Arena Season 1,
Oct–Nov 2025). Putting Qwen3 Max in the Trader seat (it won S1 with
disciplined low-frequency execution) and Claude Sonnet 4.6 as the Risk
Manager (most cautious in S1 — wrong personality for a trader, exactly right
for a risk officer) is intentional and now runs by default through
OpenRouter. See `docs/01-architecture.md` for the full justification.

**Mock-first for the demo.** A reviewer with no API keys can still run
`python run.py --mock` and see a complete realistic pipeline output. This is
deliberate: the prototype's value is in **showing the architecture works**,
not in burning your API budget.

## Costs (production estimates)

Run-rate ~$360/mo with prompt caching, $750/mo budget with safety margin and
backtest infrastructure. Full line-item breakdown in
[`docs/02-implementation.md`](./docs/02-implementation.md).

## License

MIT.
