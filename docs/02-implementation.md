# Phase B — Implementation Plan

> Source material for slides 6, 7, 8 of the Tilt submission deck.

## 1. Agentic framework

**Pick: LangGraph for orchestration + OpenClaw skill for Tilt execution.**

| Option | Verdict | Reason |
|---|---|---|
| **LangGraph** | ✅ Pick | Reference architecture (TradingAgents) is built on it; explicit state machine; PostgresSaver checkpointer; multi-LLM provider native |
| OpenClaw | Use as execution skill only | It's Tilt's own skill — fight it = friction |
| Claude Agents SDK | Reject | We use 6+ providers; SDK is single-provider |
| CrewAI | Reject | Faster prototyping, harder to debug at edges |
| AutoGen | Reject | Less mature checkpointing |
| Custom | Reject | 1–2 weeks of plumbing for no upside |

## 2. Infrastructure

**Hetzner Cloud CCX23 (4 dedicated vCPU, 16 GB RAM, 160 GB NVMe), all-in-one box.** ~€30/mo.

| Component | Where | Why |
|---|---|---|
| LangGraph orchestrator | Hetzner CCX23 | Long-running, CPU+IO-bound, steady load |
| Postgres (checkpoint + memory) | Same box | Single-tenant, low-write |
| Redis (cache) | Same box | Hot path only |
| ARQ workers (async tasks) | Same box | WhatsApp/Twitter posting, news polling |
| DNS + WAF | Cloudflare | Free tier sufficient |
| Logs | Better Stack | $10/mo |
| LLM traces | LangSmith Plus | $39/mo, non-negotiable for audit |
| Errors | Sentry | Free tier |

**Why not AWS:** ~$1500/mo equivalent — 18× more expensive for the same throughput. Junior submission move.
**Why not Railway/Render:** rate limits + cold starts conflict with our cadence.
**Why not Modal:** serverless is for bursty GPU; we have steady CPU.

## 3. Data sources

| Layer | Source | Cost | Role |
|---|---|---|---|
| OHLCV + technicals | Polygon.io Stocks Starter | $29/mo | Primary price feed |
| Fundamentals | Financial Modeling Prep Basic | $19/mo | Ratios, statements |
| Filings | SEC EDGAR | free | Raw 10-K, 10-Q, 8-K |
| News | Finnhub free + Polygon news | free | Press, headlines |
| Social sentiment | Apify X scraper + Reddit API | $30/mo | Crowd reads |
| On-chain | Robinhood Chain RPC + Tilt API | free | Trade execution + position state |
| Backup OHLCV | Tiingo | $10/mo | Polygon failover |
| **Total** | | **$88/mo** | |

## 4. LLM selection — 7 models

| # | Role | Model | $/M in/out | Empirical thesis |
|---|---|---|---|---|
| 1 | Trader | Qwen3 Max | $1.20 / $2.40 | AA S1 winner (+22.3%); disciplined low-freq execution |
| 2 | Technical Analyst | DeepSeek V4 | $0.30 / $0.50 | "Like a quant asset-manager" (AA S1 review); near-zero cost |
| 3 | Risk + Bull + Bear + Fund Mgr | Claude Sonnet 4.6 | $3 / $15 | Most cautious in AA (right for risk); strong role-play stability |
| 4 | Fundamentals Analyst | Gemini 2.5 Pro | $1.25 / $10 | 1M context = full 10-K in one shot |
| 5 | News Analyst | GPT-5.2 | $1.75 / $14 | Best text synthesis; lost as trader but reading ≠ acting |
| 6 | Sentiment Analyst | Claude Haiku 4.5 | $1 / $5 | Cheap + Apify scrape feed = controllable real-time |
| 7 | Reflection Agent | Llama 3.3 70B (Together) | $0.59 / $0.79 | Self-critique role; high volume; doesn't need frontier |

**Asymmetric assignment** is the differentiator — Sonnet 4.6 handles 4 distinct prompts (Bull/Bear/Risk/Fund) because role-play stability is its dominant strength.

## 5. Monthly cost — line items

Volume: 4 vaults × ~140 calls/day × 22 days = **~12,500 LLM calls/month**.

| Line | $/mo | Note |
|---|---|---|
| Claude Sonnet 4.6 (4 roles × 4 vaults, with caching) | $115 | Biggest line |
| GPT-5.2 News (full + intraday) | $34 | High intraday volume |
| Gemini 2.5 Pro Fundamentals | $12 | |
| Qwen3 Max Trader | $7 | |
| Haiku 4.5 Sentiment + Twitter content | $7 | |
| DeepSeek V4 Technical | $2 | |
| Llama 3.3 Reflection | $1 | |
| **LLM subtotal** | **$180** | |
| Hetzner CCX23 | $35 | |
| LangSmith Plus | $39 | |
| Better Stack logs | $10 | |
| Polygon.io | $29 | |
| FMP | $19 | |
| Apify | $30 | |
| Tiingo | $10 | |
| Cloudflare + domain + misc | $5 | |
| **Infra + data subtotal** | **$177** | |
| **Run-rate total** | **~$360/mo** | |
| Backtest infra + dev/eval LLM tokens | $200 | Re-running pipelines on historical data; A/B prompt tests |
| Buffer for evaluation cycles + spikes | $190 | First 3 months are lumpy |
| **Operational budget on the deck** | **$750/mo** | What we'd actually spend; honest, not padded for show |

## 6. Build timeline — 4 weeks (honest)

| Week | Output | Risk + mitigation |
|---|---|---|
| **W1 Foundations** | Repo, Hetzner provisioned, LangGraph skeleton, 1 analyst end-to-end with Claude, Tilt API mocked | Tilt access timing → mock layer |
| **W2 Orchestration** | 4 analysts, Bull/Bear debate with cap, Trader → Risk → Fund chain | Debate divergence → prompt test harness |
| **W3 Memory + multi-vault** | Working/episodic/reflective memory; 4 vault persona configs; Reflection agent | Memory bloat → retention policy |
| **W4 Hardening + GTM** | Observability, prompt caching, cost tracker, Twitter bot, daily auto-post, dry run | Rate limits → queue + backoff |

**+2 weeks stabilization before public launch** = ~6 weeks total to live battle.
