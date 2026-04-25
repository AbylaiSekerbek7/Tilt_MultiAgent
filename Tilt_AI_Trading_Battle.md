# Tilt AI Agents Trading Battle

**End-to-end design for the Tilt Protocol on Robinhood Chain**

*Submission · Tilt Protocol · Robinhood Chain*

Three pillars:
- **Multi-agent** — 5-stage hierarchical pipeline
- **Equities-native** — Tokenized RWAs, not crypto perps
- **Character-driven** — 4 vault personas, not 6 black boxes

By Abylaikhan Sekerbek

---

# Alpha Arena set the template. Tilt is the equities version.

**Nof1's Alpha Arena (Oct–Nov 2025)** put 6 frontier LLMs on Hyperliquid with $10K each, real money, real perps.

Result: viral on Crypto Twitter. Mystery model won. GPT-5 lost 62%. Claude lost 31%. Qwen surprised everyone.

*Tilt's job is to be the equities version of this — but better, by design.*

## Alpha Arena S1 · Final results

| Model | Return |
|---|---|
| Qwen3 Max | **+22.3%** |
| DeepSeek V3.1 | **+4.9%** |
| Claude Sonnet 4.5 | **−30.8%** |
| Grok 4 | **−45.3%** |
| Gemini 2.5 Pro | **−56.7%** |
| GPT-5 | **−62.7%** |

> **Insight:** the surprise wasn't 'who won' — it was that prompt sensitivity flipped models from +22% to −62%. Architecture > model choice. We exploit this.

---

# 5-stage hierarchical pipeline

*TradingAgents-derived (arXiv 2412.20138)*

```
                     Cycle trigger
                          ↓
        ┌──────────┬──────┴──────┬──────────┐
        ↓          ↓             ↓          ↓
  Fundamentals  Technical      News     Sentiment      ← parallel analysts
  Gemini 2.5   DeepSeek V4   GPT-5.2   Haiku 4.5
        └──────────┴──────┬──────┴──────────┘
                          ↓
              Bull researcher  ⇄  Bear researcher    ← debate ×2
                  Sonnet 4.6        Sonnet 4.6
                          ↓
                       Trader
                      Qwen3 Max
                          ↓
                    Risk manager
                     Sonnet 4.6
                          ↓
              Fund manager → Tilt smart contract
                  (Chain ID 46630)
```

*Visual note for Gamma/Manus: render this as a top-down flowchart. Cycle trigger (gray) at top. Four cyan analyst boxes in parallel. Two purple researcher boxes side-by-side with a gold "debate ×2" arrow between. Then trader (gold), risk manager (red), fund manager (gold) descending vertically. Final node: on-chain execution.*

---

# Each role has a job, an input, and an LLM matched to it.

| # | Role | Reads | Writes | Why this LLM |
|---|---|---|---|---|
| 1 | **Fundamentals analyst** | 10-K, 10-Q, ratios | thesis · signal · confidence | Gemini 2.5 Pro — 1M context for full filings |
| 2 | **Technical analyst** | OHLCV, RSI, MACD | pattern read + levels | DeepSeek V4 — quant personality, near-zero cost |
| 3 | **News analyst** | press, 8-Ks | event summary + lean | GPT-5.2 — best text synthesis |
| 4 | **Sentiment analyst** | X, Reddit, StockTwits | crowd score + topics | Haiku 4.5 — cheap, controllable |
| 5 | **Bull / Bear researchers** | all 4 analyst reports | structured debate transcript | Sonnet 4.6 — role-play stability |
| 6 | **Trader** | debate + portfolio | JSON proposal {ticker, dir, size, target, stop} | Qwen3 Max — won AA S1 with discipline |
| 7 | **Risk manager** | proposal + constraints | approve / modify / veto | Sonnet 4.6 — most cautious in AA S1 = right for risk |
| 8 | **Fund manager** | proposal + risk verdict | execute call to Tilt | Sonnet 4.6 — reliable function-calling |

---

# Three contributions no prior submission has.

## 01 — Empirically-grounded asymmetric LLM assignment

Most submissions copy Alpha Arena: "pit Claude vs GPT vs Gemini." We use AA S1 as labeled data and assign each LLM to the role where it demonstrated empirical strength — Qwen3 to Trader (won S1), Sonnet to Risk Manager (most cautious — wrong for trader, right for risk).

**Validated live:** across 10 real cycles run April 25, 2026 via OpenRouter, Qwen3 Max chose `hold` in **6 of 10** runs — the same disciplined low-frequency pattern that won AA S1. Architecture thesis confirmed empirically, not just postulated.

## 02 — Equities-native multi-cycle architecture

AA runs 2-3 min loops — right for crypto perps, wrong for equities. We use 3 cycles:

- **Daily** (post-close) — full pipeline
- **Event-triggered** (earnings/M&A) — ticker-specific
- **Intraday risk monitor** (every 15 min) — risk + news only

Cuts inference cost ~10× and reduces context fatigue. Honest about how equity alpha actually decays.

## 03 — Memory + reflection layer (FinMem-derived)

Each agent has working / episodic / reflective memory in Postgres. After each closed position, an agent writes a self-critique that's injected into next cycle's system prompt.

**This is how agents learn within a season without retraining** — directly addresses AA S1's "same model, same mistake, every day" failure mode.

---

# Boring tools that work, not the shiniest stack in a VC deck.

### ORCHESTRATION → **LangGraph**

Reference impl (TradingAgents, 52K stars) is built on it. Explicit state machine, native PostgresSaver checkpointer, multi-provider native.

*Rejected:* CrewAI (less debuggable), Claude Agents SDK (single-provider), custom (1–2 wks of plumbing for no upside)

### EXECUTION → **Tilt OpenClaw skill**

It's Tilt's own skill — fight it = friction. We use it as the trade-execution tool, not the orchestration framework. Clean separation.

*Alt:* REST direct — works, but loses the skill's session-key signing benefits.

### INFRASTRUCTURE → **Hetzner CCX23 (€30/mo)**

4 dedicated vCPU, 16 GB RAM, 160 GB NVMe. Postgres + Redis + ARQ + LangGraph orchestrator all on-box. Cloudflare for DNS, Better Stack for logs, LangSmith for traces.

*Rejected:* AWS (~$1500/mo for same throughput, 18× tax). Railway/Render (rate limits). Modal (wrong shape — we have steady CPU not bursty GPU).

### DATA SOURCES → **Polygon + FMP + Apify + Tilt**

Polygon Stocks Starter ($29) for OHLCV. FMP Basic ($19) for fundamentals. Apify ($30) for X scrape. Finnhub free for news. SEC EDGAR free for filings. Tilt API free for participants.

*Alt considered:* Bloomberg ($2K+/mo), Refinitiv (similar). Killed for cost realism.

---

# 7 LLMs, each in its empirically-strongest role.

| Role | OpenRouter SKU | $/M (in/out) | Empirical thesis |
|---|---|---|---|
| **Trader** | `qwen/qwen3-max` | $1.20 / $2.40 | Won AA S1 (+22.3%) with disciplined low-frequency execution |
| **Risk + Bull + Bear + Fund Mgr** | `anthropic/claude-sonnet-4.6` | $3 / $15 | Most cautious in AA S1; strong reasoning + role-play stability |
| **Fundamentals** | `google/gemini-2.5-pro` | $1.25 / $10 | 1M context — handles full 10-K + transcripts in one shot |
| **News** | `openai/gpt-5.2` | $1.75 / $14 | Best text synthesis on the market; reading is not acting |
| **Technical** | `deepseek/deepseek-v4-pro` | $0.30 / $0.50 | Quant personality at frontier-grade reasoning, near-zero cost |
| **Sentiment** | `anthropic/claude-haiku-4.5` | $1 / $5 | Cheap + Apify scrape feed = controllable real-time |
| **Reflection agent** | `meta-llama/llama-3.3-70b-instruct` | $0.59 / $0.79 | Self-critique role; high volume; doesn't need frontier |

*All 7 SKUs live-tested via OpenRouter on April 25, 2026. No substitutions — full architecture-spec assignment running end-to-end.*

---

# 10 real runs through OpenRouter validated the architecture.

10 full pipeline cycles · NVDA · April 25, 2026 · all 7 production models live · $1.30 spent.

## The headline

> **Qwen3 Max chose `hold` in 6 of 10 cycles.**
>
> Same disciplined low-frequency behavior that won Alpha Arena S1 (43 trades / 17 days). Across 10 cold-start runs on identical input, the personality emerged consistently. **The architectural thesis isn't theoretical — it reproduces.**

## Trader behavior (Qwen3 Max)

| Decision | Count | Pattern |
|---|---|---|
| `hold` | **6** | Watch range typically [1010, 1075] — exact technical-analyst levels. Trader reads what other agents wrote. |
| `long` | 3 | When entering, always max-size 12% (under 15% cap). Targets clustered $1075–$1120. |
| `short` | 1 | Single bear-conviction cycle — aggressive target $875 (−16% from spot). |

When Qwen takes a position it goes full size, every time — high-conviction discipline. When it doesn't, it explicitly reads the technical analyst's S/R levels into its watch band.

## Risk Manager (Claude Sonnet 4.6)

| Decision | Count |
|---|---|
| approve | 9 |
| **modify** | **1** |
| veto | 0 |

The single `modify` came on the short with target $875 — Sonnet flagged the aggressive distance and asked for resizing. **This is the cautious-personality trait we picked Sonnet for, working as designed.** Risk isn't a rubber stamp; it's actively checking.

## Operational metrics

| Metric | Measured | Estimated |
|---|---|---|
| Cost per full cycle | **$0.13** | $0.13 |
| Latency per cycle | **63.7 sec** (median, 9 runs) | 30–60 sec |
| Trader JSON parse rate | **10/10** | — |
| Pipeline completion rate | **10/10** | — |
| Latency stdev | 5.0 sec | — |

Cost is pinned exactly to budget. Latency is honest — reasoning-heavy models + sequential bull/bear debate land at ~1 minute per cycle. For a daily-cycle architecture, this is a non-issue.

*Sample run with full reasoning trail: `output/sample_run_real_NVDA.json`*

---

# $750/mo to run, 4 weeks to testnet, +2 to public launch.

## Monthly operational budget

| Line | $ |
|---|---|
| LLM APIs (4 vaults, with caching) | $180 |
| Hetzner CCX23 + Postgres + Redis | $35 |
| LangSmith Plus (LLM trace audit) | $39 |
| Polygon.io + FMP + Apify + misc | $103 |
| Backtest infra + dev/eval tokens | $200 |
| Buffer (first 3 months are lumpy) | $190 |
| **Total budget** | **$747 / mo** |

*Per-cycle cost validated on real runs: **$0.13 measured** vs $0.13 estimated. 10-run test burned $1.30 — budget is grounded, not extrapolated.*

## Build timeline

| Week | Output |
|---|---|
| **W1 — Foundations** | Hetzner provisioned, LangGraph skeleton, 1 analyst end-to-end, Tilt API mocked |
| **W2 — Orchestration** | All 4 analysts, Bull/Bear debate with cap, Trader → Risk → Fund Mgr chain |
| **W3 — Memory + multi-vault** | Working/episodic/reflective memory; 4 vault configs; Reflection agent (Llama) |
| **W4 — Hardening + GTM** | Observability, prompt caching, Twitter bot, daily auto-post, dry run |
| **W5–6 — Stabilize + public** | Live testnet → bug bash → public launch with first vault personas |

---

# Personalities. Daily rhythm. Verifiable trades.

## What's already working in this space

| Stat | Context | Lesson |
|---|---|---|
| **460K** | AIXBT followers in 4 months | 31% accuracy. Personality > accuracy. |
| **$22M** | ai16z TVL by Dec '24 | Token holders = partners model |
| **−62.7%** | GPT-5 in Alpha Arena | Drama drives content. Losers viral. |

## Why Tilt's battle wins where copycats won't

1. **Equities, not perps** — TSLA, NVDA, AAPL — names retail recognizes. 10× relatable TAM.
2. **Characters, not boxes** — Quant, Value, Macro, Contrarian — each tweetable, followable.
3. **Smart-contract enforced 2/20** — Real funds with trustless fees. Not 'a chatbot with a meme coin'.
4. **Open architecture + on-chain trades** — Forkable harness, every claim verifiable. Credibility compounds.
5. **Robinhood Chain leverage** — Brand recognition, regulatory alignment, retail funnel. Long-term moat.

---

*Abylaikhan Sekerbek*
