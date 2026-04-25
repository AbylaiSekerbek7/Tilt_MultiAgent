"""FastAPI web UI for the Tilt AI Trading Agents prototype.

Exposes:
  GET  /                       static index.html
  GET  /api/architecture       per-role model assignments
  GET  /api/cap                today's real-run usage
  GET  /api/samples            list of saved JSON runs
  GET  /api/samples/{name}     one saved run
  GET  /api/run/{mock|real}    SSE stream of pipeline execution

Real-run cost guard: hard-cap of REAL_DAILY_LIMIT (default 10) successful real
runs per UTC day, persisted to output/.daily_cap.json.

A single global lock serialises pipeline runs because agents.USE_MOCK_LLMS is
a module-level switch — concurrent runs with different mock flags would race.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from trading_agents import agents
from trading_agents.data import load_demo_data
from trading_agents.graph import build_graph
from trading_agents.llms import (
    ANTHROPIC_FALLBACK_ROLE_MAP,
    OPENROUTER_ROLE_MAP,
)

load_dotenv()

REAL_DAILY_LIMIT = int(os.getenv("REAL_DAILY_LIMIT", "10"))

# Resolve project paths relative to this file so the app works regardless of
# the working directory the server is launched from.
WEB_DIR = Path(__file__).resolve().parent
PROTOTYPE_DIR = WEB_DIR.parent
STATIC_DIR = WEB_DIR / "static"
OUTPUT_DIR = PROTOTYPE_DIR / "output"
CAP_PATH = OUTPUT_DIR / ".daily_cap.json"

OUTPUT_DIR.mkdir(exist_ok=True)

GRAPH = build_graph()
RUN_LOCK = asyncio.Lock()

app = FastAPI(title="Tilt AI Trading Agents")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---- daily cap ----------------------------------------------------------

def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _read_cap() -> dict:
    today = _today()
    if CAP_PATH.exists():
        try:
            d = json.loads(CAP_PATH.read_text(encoding="utf-8"))
            if d.get("date") == today:
                return d
        except (json.JSONDecodeError, OSError):
            pass
    return {"date": today, "used": 0}


def _write_cap(d: dict) -> None:
    CAP_PATH.write_text(json.dumps(d), encoding="utf-8")


def _try_reserve_real_run() -> tuple[bool, int]:
    """Atomically reserve one real-run slot if available."""
    d = _read_cap()
    if d["used"] >= REAL_DAILY_LIMIT:
        return False, d["used"]
    d["used"] += 1
    _write_cap(d)
    return True, d["used"]


def _release_real_run() -> None:
    """Release a reserved slot — used if the run errored before any LLM cost."""
    d = _read_cap()
    if d["used"] > 0:
        d["used"] -= 1
        _write_cap(d)


# ---- HTTP routes --------------------------------------------------------

@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/architecture")
async def architecture() -> dict:
    has_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    return {
        "openrouter_role_map": OPENROUTER_ROLE_MAP,
        "anthropic_fallback_role_map": ANTHROPIC_FALLBACK_ROLE_MAP,
        "active_path": (
            "openrouter" if has_openrouter
            else "anthropic" if has_anthropic
            else "none"
        ),
        "real_runs_available": has_openrouter or has_anthropic,
    }


@app.get("/api/cap")
async def cap() -> dict:
    d = _read_cap()
    return {"used": d["used"], "limit": REAL_DAILY_LIMIT, "date": d["date"]}


@app.get("/api/samples")
async def list_samples() -> dict:
    files = sorted(
        p.name for p in OUTPUT_DIR.glob("*.json") if not p.name.startswith(".")
    )
    return {"files": files}


@app.get("/api/samples/{name}")
async def get_sample(name: str):
    if "/" in name or "\\" in name or not name.endswith(".json"):
        raise HTTPException(status_code=400, detail="invalid filename")
    path = OUTPUT_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="not found")
    return JSONResponse(json.loads(path.read_text(encoding="utf-8")))


# ---- SSE pipeline stream ------------------------------------------------

def _sse(event: str, payload: dict | list | str) -> str:
    body = json.dumps(payload, default=str)
    return f"event: {event}\ndata: {body}\n\n"


def _merge_update(state: dict, diff: dict) -> None:
    """Mirror the LangGraph reducer so we can rebuild the final state."""
    for k, v in diff.items():
        if k == "reasoning_trail":
            state.setdefault("reasoning_trail", []).extend(v)
        else:
            state[k] = v


async def _stream_pipeline(mock: bool) -> AsyncGenerator[str, None]:
    if RUN_LOCK.locked():
        yield _sse("queued", {"message": "another run is in progress, waiting"})

    async with RUN_LOCK:
        # Reserve a real-run slot before we touch any keys.
        if not mock:
            ok, used = _try_reserve_real_run()
            if not ok:
                yield _sse(
                    "error",
                    {
                        "code": "rate_limited",
                        "message": (
                            f"Daily real-run cap reached ({used}/{REAL_DAILY_LIMIT}). "
                            "Try mock mode or come back tomorrow (UTC)."
                        ),
                    },
                )
                return
            if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("ANTHROPIC_API_KEY")):
                _release_real_run()
                yield _sse(
                    "error",
                    {
                        "code": "no_key",
                        "message": "Server has no OPENROUTER_API_KEY or ANTHROPIC_API_KEY set.",
                    },
                )
                return

        agents.USE_MOCK_LLMS = mock

        data = load_demo_data()
        initial = {
            "ticker": data["ticker"],
            "cycle_date": data["cycle_date"],
            "market_data": data,
            "reasoning_trail": [],
        }

        active_path = (
            "mock" if mock
            else "openrouter" if os.getenv("OPENROUTER_API_KEY")
            else "anthropic"
        )

        yield _sse(
            "start",
            {
                "ticker": data["ticker"],
                "cycle_date": data["cycle_date"],
                "mock": mock,
                "active_path": active_path,
                "started_at": int(time.time()),
            },
        )

        # graph.stream is a sync generator. Pump it from a worker thread into
        # an asyncio.Queue so we can yield SSE events as they arrive.
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def producer() -> None:
            try:
                for upd in GRAPH.stream(initial, stream_mode="updates"):
                    loop.call_soon_threadsafe(queue.put_nowait, ("update", upd))
                loop.call_soon_threadsafe(queue.put_nowait, ("done", None))
            except Exception as exc:  # noqa: BLE001 — surface any error to the client
                loop.call_soon_threadsafe(
                    queue.put_nowait, ("error", f"{type(exc).__name__}: {exc}")
                )

        thread = threading.Thread(target=producer, daemon=True)
        thread.start()
        started = time.time()

        final_state: dict = dict(initial)
        had_error = False

        while True:
            kind, payload = await queue.get()
            if kind == "update":
                for node_name, diff in payload.items():
                    _merge_update(final_state, diff)
                    yield _sse(
                        "node",
                        {
                            "node": node_name,
                            "diff": diff,
                            "elapsed": round(time.time() - started, 2),
                        },
                    )
            elif kind == "done":
                break
            elif kind == "error":
                had_error = True
                # If the pipeline died before any real LLM call billed, refund
                # the slot. We can't tell precisely, so refund only on errors
                # that surface before any node emitted (best-effort).
                if not mock and not final_state.get("reasoning_trail"):
                    _release_real_run()
                yield _sse("error", {"message": payload})
                break

        if not had_error:
            yield _sse(
                "complete",
                {
                    "final_state": final_state,
                    "elapsed": round(time.time() - started, 2),
                },
            )


@app.get("/api/run/{mode}")
async def run_pipeline(mode: str, request: Request):
    if mode not in ("mock", "real"):
        raise HTTPException(status_code=400, detail="mode must be mock or real")
    mock = mode == "mock"

    async def event_source() -> AsyncGenerator[bytes, None]:
        try:
            async for chunk in _stream_pipeline(mock):
                if await request.is_disconnected():
                    break
                yield chunk.encode("utf-8")
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
