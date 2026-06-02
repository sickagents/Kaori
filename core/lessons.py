"""Lessons engine - tracks LP performance and evolves thresholds.

Inspired by Meridian's lessons.js. Records closed position outcomes,
derives lessons, and adjusts screening thresholds based on winners vs losers.
"""

import json
import time
from pathlib import Path
from statistics import mean, median


LESSONS_FILE = Path("/tmp/kaori_lessons.json")


def load_lessons() -> dict:
    if LESSONS_FILE.exists():
        with open(LESSONS_FILE) as f:
            return json.load(f)
    return {"performances": [], "lessons": [], "thresholds": {}, "evolution_log": []}


def save_lessons(data: dict):
    with open(LESSONS_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def record_performance(position: dict):
    """Record closed position performance for learning."""
    data = load_lessons()

    pnl_pct = position.get("final_pnl_pct", 0)
    hold_min = position.get("hold_duration_min", 0)
    reason = position.get("close_reason", "unknown")
    dex = position.get("dex", "unknown")
    token0 = position.get("token0_symbol", "?")
    token1 = position.get("token1_symbol", "?")

    # Categorize outcome
    if pnl_pct >= 5:
        outcome = "good"
    elif pnl_pct >= 0:
        outcome = "neutral"
    elif pnl_pct >= -5:
        outcome = "poor"
    else:
        outcome = "bad"

    perf = {
        "time": int(time.time()),
        "pool": position.get("pool", ""),
        "dex": dex,
        "pair": f"{token0}/{token1}",
        "pnl_pct": round(pnl_pct, 2),
        "hold_min": round(hold_min, 1),
        "reason": reason,
        "outcome": outcome,
        "fee_tvl_ratio": position.get("fee_tvl_ratio"),
        "volatility": position.get("volatility"),
        "tvl": position.get("tvl"),
        "volume": position.get("volume"),
    }

    data["performances"].append(perf)

    # Keep last 200
    if len(data["performances"]) > 200:
        data["performances"] = data["performances"][-200:]

    # Derive lesson
    lesson = _derive_lesson(perf, data["performances"])
    if lesson:
        data["lessons"].append(lesson)
        if len(data["lessons"]) > 100:
            data["lessons"] = data["lessons"][-100:]

    save_lessons(data)
    return perf


def _derive_lesson(perf: dict, history: list) -> dict | None:
    """Derive a lesson from a closed position."""
    outcome = perf["outcome"]
    if outcome == "neutral":
        return None

    # Count evidence
    same_pair = [p for p in history if p["pair"] == perf["pair"]]
    same_dex = [p for p in history if p["dex"] == perf["dex"]]

    positive_evidence = len([p for p in same_pair if p["outcome"] == "good"]) >= 2
    negative_evidence = len([p for p in same_pair if p["outcome"] in ("poor", "bad")]) >= 2

    confidence = 0.35
    if outcome == "good":
        confidence = 0.82 if positive_evidence else 0.22
    elif outcome == "bad":
        confidence = 0.88 if negative_evidence else 0.45

    if confidence < 0.4:
        return None

    lesson = {
        "time": int(time.time()),
        "pair": perf["pair"],
        "dex": perf["dex"],
        "outcome": outcome,
        "confidence": round(confidence, 2),
        "pnl_pct": perf["pnl_pct"],
        "reason": perf["reason"],
    }

    # Generate text
    if outcome == "good":
        lesson["text"] = (
            f"{perf['pair']} on {perf['dex']} yielded {perf['pnl_pct']:+.1f}% "
            f"in {perf['hold_min']:.0f}min. Good candidate for similar pairs."
        )
    elif outcome == "bad":
        lesson["text"] = (
            f"{perf['pair']} on {perf['dex']} lost {perf['pnl_pct']:.1f}% "
            f"(exit: {perf['reason']}). Avoid similar conditions."
        )

    return lesson


def evolve_thresholds(config: dict, min_samples: int = 5) -> dict:
    """Evolve screening thresholds based on performance history.

    Adjusts max 20% per step to prevent oscillation.
    Returns updated config values.
    """
    data = load_lessons()
    perfs = data["performances"]

    if len(perfs) < min_samples:
        return config

    winners = [p for p in perfs if p["outcome"] == "good"]
    losers = [p for p in perfs if p["outcome"] in ("poor", "bad")]

    changes = {}
    screening = config.get("screening", {})

    def nudge(current, target, max_change_pct=0.20):
        """Adjust value by max percentage step."""
        if current is None or current == 0:
            return target
        delta = target - current
        max_delta = abs(current) * max_change_pct
        if abs(delta) <= max_delta:
            return target
        return current + (1 if delta > 0 else -1) * max_delta

    # 1. Max volatility - tighten if losers cluster at high vol
    if losers and winners:
        loser_vols = [p["volatility"] for p in losers if p.get("volatility")]
        winner_vols = [p["volatility"] for p in winners if p.get("volatility")]

        if loser_vols and winner_vols:
            loser_p25 = sorted(loser_vols)[len(loser_vols) // 4]
            winner_p75 = sorted(winner_vols)[len(winner_vols) * 3 // 4]

            current_max_vol = screening.get("max_volatility", 10)
            if loser_p25 < current_max_vol:
                new_max = nudge(current_max_vol, loser_p25)
                changes["max_volatility"] = {"old": current_max_vol, "new": round(new_max, 2)}
                screening["max_volatility"] = round(new_max, 2)

    # 2. Min fee/TVL ratio - raise based on winners
    if winners:
        winner_fee_tvls = [p["fee_tvl_ratio"] for p in winners if p.get("fee_tvl_ratio")]
        if winner_fee_tvls:
            min_winner_ftl = min(winner_fee_tvls)
            current_min_ftl = screening.get("min_fee_tvl_ratio", 0.05)
            if min_winner_ftl > current_min_ftl:
                new_min = nudge(current_min_ftl, min_winner_ftl)
                changes["min_fee_tvl_ratio"] = {"old": current_min_ftl, "new": round(new_min, 4)}
                screening["min_fee_tvl_ratio"] = round(new_min, 4)

    # 3. Win rate stats
    total = len(perfs)
    win_rate = len(winners) / total * 100 if total > 0 else 0
    avg_pnl = mean([p["pnl_pct"] for p in perfs]) if perfs else 0

    changes["stats"] = {
        "total": total,
        "win_rate": round(win_rate, 1),
        "avg_pnl_pct": round(avg_pnl, 2),
    }

    if changes:
        config["screening"] = screening
        data["evolution_log"].append({
            "time": int(time.time()),
            "changes": changes,
        })
        if len(data["evolution_log"]) > 50:
            data["evolution_log"] = data["evolution_log"][-50:]
        save_lessons(data)

    return config


def get_lessons_summary(limit: int = 10) -> str:
    """Get recent lessons as text for logging/display."""
    data = load_lessons()
    lessons = data.get("lessons", [])[-limit:]
    perfs = data.get("performances", [])

    if not perfs:
        return "No performance data yet."

    total = len(perfs)
    winners = len([p for p in perfs if p["outcome"] == "good"])
    losers = len([p for p in perfs if p["outcome"] in ("poor", "bad")])
    avg_pnl = mean([p["pnl_pct"] for p in perfs])

    lines = [
        f"Performance: {total} positions, {winners} wins, {losers} losses",
        f"Win rate: {winners / total * 100:.1f}%",
        f"Avg PnL: {avg_pnl:+.2f}%",
        "",
    ]

    if lessons:
        lines.append("Recent lessons:")
        for l in lessons[-5:]:
            lines.append(f"  [{l['outcome']}] {l.get('text', l.get('pair', '?'))}")

    return "\n".join(lines)
