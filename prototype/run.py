"""CLI entry point.

Usage:
    python run.py                  # real LLM calls. Prefers OPENROUTER_API_KEY
                                   # (asymmetric architecture); falls back to
                                   # ANTHROPIC_API_KEY (Claude for every role).
    python run.py --mock           # offline demo with deterministic stub responses
    python run.py --ticker AAPL    # not wired; prototype only ships NVDA mock data

After the cycle completes, the full reasoning trail and execution result are
written to output/run_<timestamp>.json for audit / GitHub artifact upload.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from trading_agents import agents
from trading_agents.data import load_demo_data
from trading_agents.graph import build_graph

console = Console()


def _print_header(args: argparse.Namespace) -> None:
    import os

    if args.mock:
        mode = "mock (no API calls)"
    elif os.getenv("OPENROUTER_API_KEY"):
        mode = "live (OpenRouter — asymmetric architecture)"
    else:
        mode = "live (Anthropic — Claude-only fallback)"
    console.print()
    console.print(
        Panel.fit(
            "[bold]Tilt AI Trading Agents[/bold] — prototype run\n"
            f"Mode: {mode}\n"
            "Pipeline: 4 analysts → bull/bear → trader → risk → fund manager → on-chain",
            border_style="blue",
        )
    )


def _print_analyst_report(name: str, body: str) -> None:
    console.print(Rule(f"[bold]{name}[/bold]"))
    console.print(Markdown(body))


def _print_proposal(proposal: dict) -> None:
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(style="dim")
    table.add_column()
    for k, v in proposal.items():
        table.add_row(k, str(v))
    console.print(Panel(table, title="Trader proposal", border_style="cyan"))


def _print_risk_verdict(decision: str, reasoning: str) -> None:
    color = {"approve": "green", "modify": "yellow", "veto": "red"}.get(
        decision, "white"
    )
    console.print(
        Panel(
            f"[bold {color}]{decision.upper()}[/bold {color}]\n\n{reasoning}",
            title="Risk Manager",
            border_style=color,
        )
    )


def _print_fund_manager(decision: str, execution: dict | None) -> None:
    color = "green" if decision == "approved" else "red"
    body = f"[bold {color}]{decision.upper()}[/bold {color}]"
    if execution:
        body += (
            f"\n\nOn-chain execution:\n"
            f"  tx_hash: {execution['tx_hash'][:18]}...\n"
            f"  chain_id: {execution['chain_id']} (Robinhood Chain)\n"
            f"  block: {execution['block_number']}\n"
            f"  status: {execution['status']}"
        )
    console.print(Panel(body, title="Fund Manager + Tilt execution", border_style=color))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use deterministic stub LLMs (no API calls). Good for offline demos.",
    )
    parser.add_argument(
        "--ticker",
        default="NVDA",
        help="Ticker to analyze. Prototype only ships NVDA demo data.",
    )
    args = parser.parse_args()

    load_dotenv()

    # Flip the module-level switch in agents.py BEFORE compiling the graph
    # (the graph captures function references at compile time)
    agents.USE_MOCK_LLMS = args.mock

    if not args.mock:
        import os

        if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("ANTHROPIC_API_KEY")):
            console.print(
                "[red]No LLM provider key set.[/red] "
                "Set OPENROUTER_API_KEY (recommended — runs the full asymmetric "
                "architecture) or ANTHROPIC_API_KEY (Claude-only fallback) in .env, "
                "or run with --mock for an offline demo."
            )
            return 1

    _print_header(args)

    data = load_demo_data()
    if args.ticker != "NVDA":
        console.print(
            f"[yellow]Note: prototype ships only NVDA demo data; running NVDA "
            f"despite ticker={args.ticker}.[/yellow]"
        )

    initial_state = {
        "ticker": data["ticker"],
        "cycle_date": data["cycle_date"],
        "market_data": data,
        "reasoning_trail": [],
    }

    graph = build_graph()

    console.print(f"\n[dim]Running 5-stage pipeline for {data['ticker']} on "
                  f"{data['cycle_date']}...[/dim]\n")
    started = time.time()
    final_state = graph.invoke(initial_state)
    elapsed = time.time() - started

    # Pretty print
    _print_analyst_report("Fundamentals analyst", final_state["fundamentals_report"])
    _print_analyst_report("Technical analyst", final_state["technical_report"])
    _print_analyst_report("News analyst", final_state["news_report"])
    _print_analyst_report("Sentiment analyst", final_state["sentiment_report"])
    console.print(Rule("[bold]Bull researcher[/bold]"))
    console.print(Markdown(final_state["bull_argument"]))
    console.print(Rule("[bold]Bear researcher[/bold]"))
    console.print(Markdown(final_state["bear_argument"]))

    _print_proposal(final_state["trade_proposal"])
    _print_risk_verdict(
        final_state["risk_decision"], final_state["risk_reasoning"]
    )
    _print_fund_manager(
        final_state["fund_manager_decision"],
        final_state.get("execution_result"),
    )

    console.print(
        f"\n[dim]Cycle completed in {elapsed:.1f}s, "
        f"{len(final_state['reasoning_trail'])} reasoning steps logged.[/dim]"
    )

    # Write full state to disk for audit / sharing
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"run_{int(time.time())}.json"
    with out_path.open("w") as f:
        # Strip non-JSON-serializable fields if any (none in our state)
        json.dump(final_state, f, indent=2, default=str)
    console.print(f"[dim]Full state written to {out_path}[/dim]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
