"""Position state tracking - inspired by Meridian's state.js.

Tracks all LP positions with PnL, exit conditions, and lifecycle management.
Persists to kaori_state.json for crash recovery.
"""

import json
import time
from pathlib import Path
from web3 import Web3


STATE_FILE = Path("/tmp/kaori_state.json")


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"positions": [], "closed": [], "cooldowns": {}}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def track_position(position: dict):
    """Add a new position to state."""
    state = load_state()
    position["opened_at"] = int(time.time())
    position["status"] = "open"
    position["peak_pnl_pct"] = 0.0
    position["pnl_history"] = []
    position["oor_since"] = None  # out-of-range timestamp
    position["notes"] = []
    state["positions"].append(position)
    save_state(state)
    return position


def close_position(pool_address: str, pnl_pct: float, reason: str):
    """Move position from open to closed."""
    state = load_state()
    pos = None
    for i, p in enumerate(state["positions"]):
        if p.get("pool", "").lower() == pool_address.lower():
            pos = state["positions"].pop(i)
            break

    if not pos:
        return None

    pos["status"] = "closed"
    pos["closed_at"] = int(time.time())
    pos["close_reason"] = reason
    pos["final_pnl_pct"] = pnl_pct
    pos["hold_duration_min"] = (pos["closed_at"] - pos["opened_at"]) / 60
    state["closed"].append(pos)

    # Add cooldown
    state["cooldowns"][pool_address.lower()] = int(time.time()) + 3600  # 1hr cooldown
    if pos.get("token1_address"):
        state["cooldowns"][pos["token1_address"].lower()] = int(time.time()) + 1800  # 30min

    save_state(state)
    return pos


def is_on_cooldown(address: str) -> bool:
    """Check if a pool or token is on cooldown."""
    state = load_state()
    addr = address.lower()
    if addr in state["cooldowns"]:
        if time.time() < state["cooldowns"][addr]:
            return True
        else:
            del state["cooldowns"][addr]
            save_state(state)
    return False


def get_open_positions() -> list:
    state = load_state()
    return [p for p in state["positions"] if p["status"] == "open"]


def get_closed_positions(limit: int = 50) -> list:
    state = load_state()
    return state["closed"][-limit:]


def update_position_pnl(pool_address: str, pnl_pct: float, in_range: bool):
    """Update PnL and check exit conditions."""
    state = load_state()
    for pos in state["positions"]:
        if pos.get("pool", "").lower() == pool_address.lower():
            # Update peak PnL
            if pnl_pct > pos.get("peak_pnl_pct", 0):
                pos["peak_pnl_pct"] = pnl_pct

            # Track PnL history
            pos["pnl_history"].append({
                "time": int(time.time()),
                "pnl_pct": pnl_pct,
                "in_range": in_range,
            })
            # Keep last 100 entries
            if len(pos["pnl_history"]) > 100:
                pos["pnl_history"] = pos["pnl_history"][-100:]

            # OOR tracking
            if not in_range:
                if pos.get("oor_since") is None:
                    pos["oor_since"] = int(time.time())
            else:
                pos["oor_since"] = None

            pos["current_pnl_pct"] = pnl_pct
            save_state(state)
            return pos

    return None


def check_exit_conditions(pool_address: str, config: dict) -> dict | None:
    """Check if position should be closed. Returns reason or None."""
    state = load_state()
    mgmt = config.get("management", {})
    risk = config.get("risk", {})

    for pos in state["positions"]:
        if pos.get("pool", "").lower() != pool_address.lower():
            continue

        pnl = pos.get("current_pnl_pct", 0)
        peak = pos.get("peak_pnl_pct", 0)
        oor_since = pos.get("oor_since")
        opened_at = pos.get("opened_at", 0)
        age_min = (time.time() - opened_at) / 60

        # 1. Stop loss
        stop_loss = risk.get("stop_loss_pct", -15)
        if pnl <= stop_loss:
            return {"reason": "stop_loss", "pnl": pnl, "threshold": stop_loss}

        # 2. Trailing take profit
        trailing_tp = mgmt.get("trailing_tp_pct", 10)
        trailing_drop = mgmt.get("trailing_drop_pct", 3)
        if peak >= trailing_tp and (peak - pnl) >= trailing_drop:
            return {"reason": "trailing_tp", "pnl": pnl, "peak": peak, "drop": peak - pnl}

        # 3. Out-of-range timeout
        oor_timeout = mgmt.get("oor_timeout_min", 30)
        if oor_since and (time.time() - oor_since) / 60 >= oor_timeout:
            return {"reason": "oor_timeout", "oor_min": (time.time() - oor_since) / 60}

        # 4. Low yield (after minimum age)
        min_age = mgmt.get("min_age_for_yield_check_min", 60)
        min_yield = mgmt.get("min_fee_yield_pct", 1)
        if age_min >= min_age and pnl < min_yield:
            return {"reason": "low_yield", "pnl": pnl, "min": min_yield, "age_min": age_min}

        return None

    return None
