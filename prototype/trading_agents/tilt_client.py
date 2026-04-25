"""Mock Tilt Protocol client.

In production this calls Tilt's REST API or the OpenClaw skill to execute
on-chain trades on Robinhood Chain. For the prototype we simulate the
request/response so the pipeline runs end-to-end without testnet access.

The real client would:
  1. Sign a transaction with the vault's session key.
  2. Submit to Tilt's relayer.
  3. Wait for chain inclusion and return tx_hash + execution price.
  4. Optionally pin the reasoning trail to IPFS for audit.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any


class MockTiltClient:
    """Drop-in stub of the production Tilt client. Same interface."""

    def __init__(self, vault_id: str = "vault_quant_001"):
        self.vault_id = vault_id
        self._executed_trades: list[dict[str, Any]] = []

    def execute_trade(self, proposal: dict[str, Any]) -> dict[str, Any]:
        """Execute a trade proposal.

        Args:
            proposal: {ticker, direction, size_pct, entry_band, target, stop, thesis}
        Returns:
            {tx_hash, status, executed_at, vault_id, executed_price, ...}
        """
        # In production: sign and submit on-chain transaction
        # Here: simulate the response with deterministic data
        payload = f"{self.vault_id}:{proposal['ticker']}:{time.time_ns()}"
        tx_hash = "0x" + hashlib.sha256(payload.encode()).hexdigest()

        result = {
            "tx_hash": tx_hash,
            "status": "confirmed",
            "executed_at": int(time.time()),
            "vault_id": self.vault_id,
            "ticker": proposal["ticker"],
            "direction": proposal["direction"],
            "size_pct": proposal["size_pct"],
            "executed_price": proposal.get("entry_band", [0, 0])[0]
            if proposal["direction"] != "hold"
            else None,
            "block_number": 18_400_000 + len(self._executed_trades),
            "chain_id": 46630,  # Robinhood Chain
        }
        self._executed_trades.append(result)
        return result

    def get_vault_state(self) -> dict[str, Any]:
        """Read current vault state from chain. Mock returns frozen snapshot."""
        return {
            "vault_id": self.vault_id,
            "nav_usd": 100_000,
            "positions": [],
            "fee_structure": {"management_pct": 0.02, "performance_pct": 0.20},
        }

    def pin_reasoning_to_ipfs(self, reasoning_trail: list[dict[str, Any]]) -> str:
        """Mock IPFS pin for audit trail. Returns a CID."""
        digest = hashlib.sha256(str(reasoning_trail).encode()).hexdigest()[:46]
        return f"Qm{digest}"
