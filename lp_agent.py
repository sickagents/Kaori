#!/usr/bin/env python3
"""
Kaori - Automated Liquidity Pool Agent for Base Network.

Supports Uniswap V3 and Aerodrome with auto/manual modes.
Mode is set in config.json: "auto" or "manual".
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import yaml
from web3 import Web3
from eth_account import Account

sys.path.insert(0, str(Path(__file__).parent))

from core.wallet import WalletManager
from core.tokens import TokenResolver
from core.gas import GasEstimator
from dex.uniswap_v3 import UniswapV3
from dex.aerodrome import Aerodrome
from utils.approvals import ApprovalManager
from utils.formatting import format_amount, parse_amount


CONFIG_FILE = Path(__file__).parent / "config.json"


def load_config() -> dict:
    """Load config from config.json."""
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(config: dict):
    """Save config to config.json."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_w3(config: dict) -> Web3:
    """Initialize Web3 connection."""
    w3 = Web3(Web3.HTTPProvider(config["rpc"]))
    if not w3.is_connected():
        raise ConnectionError(f"Failed to connect to RPC: {config['rpc']}")
    print(f"[+] Connected to Base (block: {w3.eth.block_number})")
    return w3


def resolve_token(w3: Web3, identifier: str) -> dict:
    """Resolve token by symbol or address - dynamically from chain."""
    resolver = TokenResolver(w3)

    # If it looks like an address
    if identifier.startswith("0x") and len(identifier) == 42:
        return resolver.resolve(identifier)

    # If it's a symbol, check base_tokens first for known addresses
    config = load_config()
    base_tokens = config.get("base_tokens", {})
    key = identifier.upper()
    if key in base_tokens:
        return resolver.resolve(base_tokens[key])

    # Unknown symbol - can't resolve without address
    raise ValueError(f"Unknown token symbol: {identifier}. Use full address (0x...) instead.")


def get_dex(config: dict, w3: Web3, gas: GasEstimator, dex_name: str):
    """Get DEX instance by name."""
    if dex_name == "uniswap":
        return UniswapV3(w3, config["dex"]["uniswap_v3"], gas)
    elif dex_name == "aerodrome":
        return Aerodrome(w3, config["dex"]["aerodrome"], gas)
    else:
        raise ValueError(f"Unknown DEX: {dex_name}")


def approve_tokens(w3, wallet, t0, t1, amount0, amount1, spender):
    """Approve both tokens for spender."""
    ApprovalManager(w3, wallet).ensure_approval(t0["address"], spender, amount0)
    ApprovalManager(w3, wallet).ensure_approval(t1["address"], spender, amount1)


def add_lp_uniswap(config, w3, wallet, gas, t0, t1, amount0, amount1, pair_cfg):
    """Add liquidity to Uniswap V3."""
    dex = UniswapV3(w3, config["dex"]["uniswap_v3"], gas)
    fee = pair_cfg.get("fee", config["manual"]["fee"] if "manual" in config else 500)
    tick_lower = pair_cfg.get("tick_lower", -config["auto"]["tick_range"] if "auto" in config else -887220)
    tick_upper = pair_cfg.get("tick_upper", config["auto"]["tick_range"] if "auto" in config else 887220)

    print(f"    DEX: Uniswap V3 | Fee: {fee / 10000}% | Range: [{tick_lower}, {tick_upper}]")

    approve_tokens(w3, wallet, t0, t1, amount0, amount1, config["dex"]["uniswap_v3"]["position_manager"])

    tx_hash = dex.add_liquidity(
        wallet=wallet, token0=t0["address"], token1=t1["address"],
        fee=fee, tick_lower=tick_lower, tick_upper=tick_upper,
        amount0_desired=amount0, amount1_desired=amount1,
        slippage=config["slippage"], deadline=config["deadline"],
    )
    return tx_hash


def add_lp_aerodrome(config, w3, wallet, gas, t0, t1, amount0, amount1, pair_cfg):
    """Add liquidity to Aerodrome."""
    dex = Aerodrome(w3, config["dex"]["aerodrome"], gas)
    stable = pair_cfg.get("stable", False)

    print(f"    DEX: Aerodrome | Stable: {stable}")

    approve_tokens(w3, wallet, t0, t1, amount0, amount1, config["dex"]["aerodrome"]["router"])

    tx_hash = dex.add_liquidity(
        wallet=wallet, token0=t0["address"], token1=t1["address"],
        amount0_desired=amount0, amount1_desired=amount1,
        stable=stable, slippage=config["slippage"], deadline=config["deadline"],
    )
    return tx_hash


def add_lp_for_pair(config, w3, wallet, gas, pair):
    """Add LP for a single pair. Auto-selects DEX or uses specified one."""
    t0 = resolve_token(w3, pair["token0"])
    t1 = resolve_token(w3, pair["token1"])
    amount0 = parse_amount(str(pair["amount0"]), t0["decimals"])
    amount1 = parse_amount(str(pair["amount1"]), t1["decimals"])

    print(f"\n[*] {pair['amount0']} {pair['token0']} + {pair['amount1']} {pair['token1']}")

    # Determine DEX
    dex_name = pair.get("dex", None)
    if not dex_name:
        dex_name = pair.get("prefer_dex", config.get("auto", {}).get("prefer_dex", "aerodrome"))

    # Auto-select: try Aerodrome first, fallback Uniswap
    if dex_name == "auto" or dex_name is None:
        aero = Aerodrome(w3, config["dex"]["aerodrome"], gas)
        pool = aero.find_pool(t0["address"], t1["address"])
        if pool:
            dex_name = "aerodrome"
            pair["stable"] = pool["stable"]
            print(f"    Auto-selected: Aerodrome (stable={pool['stable']})")
        else:
            dex_name = "uniswap"
            print(f"    Auto-selected: Uniswap V3 (no Aerodrome pool)")

    if dex_name in ("aerodrome", "aero"):
        tx_hash = add_lp_aerodrome(config, w3, wallet, gas, t0, t1, amount0, amount1, pair)
    else:
        tx_hash = add_lp_uniswap(config, w3, wallet, gas, t0, t1, amount0, amount1, pair)

    print(f"    TX: https://basescan.org/tx/0x{tx_hash.hex()}")
    return tx_hash


# ── COMMANDS ──

def cmd_run(args, config):
    """Run LP agent based on config mode (auto/manual)."""
    mode = config["mode"]
    print(f"[*] Mode: {mode.upper()}")

    w3 = get_w3(config)
    wallet_path = os.path.expanduser(config["wallets"]["single"])
    wallet = WalletManager(w3, wallet_path)
    gas = GasEstimator(w3, config["chain_id"], config["gas_multiplier"])

    print(f"[*] Wallet: {wallet.address}")

    if mode == "manual":
        # Manual mode: single pair from config
        m = config["manual"]
        pair = {
            "token0": m["token0"],
            "token1": m["token1"],
            "amount0": m["amount0"],
            "amount1": m["amount1"],
            "dex": m["dex"],
            "fee": m.get("fee", 500),
            "tick_lower": m.get("tick_lower", -887220),
            "tick_upper": m.get("tick_upper", 887220),
            "stable": m.get("stable", False),
        }
        add_lp_for_pair(config, w3, wallet, gas, pair)

    elif mode == "auto":
        # Auto mode: iterate pairs, optional loop
        pairs = config["auto"]["pairs"]
        interval = config["auto"].get("run_interval_seconds", 0)
        max_positions = config["auto"].get("max_positions", 5)

        while True:
            print(f"\n{'='*50}")
            print(f"[*] Running {len(pairs)} pairs (max positions: {max_positions})")

            for i, pair in enumerate(pairs):
                try:
                    pair_copy = dict(pair)
                    pair_copy.setdefault("dex", config["auto"].get("prefer_dex", "aerodrome"))
                    pair_copy.setdefault("stable", config["auto"].get("stable", False))
                    pair_copy.setdefault("fee", config["auto"].get("fee_tier", 500))
                    add_lp_for_pair(config, w3, wallet, gas, pair_copy)
                except Exception as e:
                    print(f"    ERROR: {e}")

                if i < len(pairs) - 1:
                    time.sleep(5)

            if interval <= 0:
                break

            print(f"\n[*] Sleeping {interval}s until next run...")
            time.sleep(interval)

    else:
        print(f"[-] Unknown mode: {mode}. Use 'auto' or 'manual' in config.json")
        sys.exit(1)

    print(f"\n[+] Done!")


def cmd_batch(args, config):
    """Batch LP across multiple wallets."""
    w3 = get_w3(config)
    gas = GasEstimator(w3, config["chain_id"], config["gas_multiplier"])

    wallets_path = Path(args.wallets or config["wallets"]["batch"]).expanduser()
    with open(wallets_path) as f:
        wallet_data = json.load(f)

    mode = config["mode"]

    if mode == "manual":
        pairs = [config["manual"]]
    else:
        pairs = config["auto"]["pairs"]

    print(f"[*] Batch LP: {len(wallet_data)} wallets x {len(pairs)} pairs")

    results = {"ok": 0, "error": 0, "errors": []}

    for i, wd in enumerate(wallet_data):
        wallet = WalletManager(w3, private_key=wd["private_key"])
        print(f"\n[{i + 1}/{len(wallet_data)}] {wallet.address[:10]}...")

        for pair in pairs:
            try:
                pair_copy = dict(pair)
                if mode == "auto":
                    pair_copy.setdefault("dex", config["auto"].get("prefer_dex", "aerodrome"))
                    pair_copy.setdefault("stable", config["auto"].get("stable", False))
                    pair_copy.setdefault("fee", config["auto"].get("fee_tier", 500))
                add_lp_for_pair(config, w3, wallet, gas, pair_copy)
                results["ok"] += 1
            except Exception as e:
                print(f"    ERROR: {e}")
                results["error"] += 1
                results["errors"].append({"index": i, "address": wd.get("address", ""), "error": str(e)})

        if i < len(wallet_data) - 1:
            time.sleep(2)

    print(f"\n[+] Batch complete: {results['ok']} ok, {results['error']} errors")
    if results["errors"]:
        with open("/tmp/kaori_batch_errors.json", "w") as f:
            json.dump(results["errors"], f, indent=2)
        print(f"    Errors saved to /tmp/kaori_batch_errors.json")


def cmd_positions(args, config):
    """Check LP positions."""
    w3 = get_w3(config)
    wallet_path = os.path.expanduser(config["wallets"]["single"])
    wallet = WalletManager(w3, wallet_path)
    gas = GasEstimator(w3, config["chain_id"], config["gas_multiplier"])

    print(f"[*] Positions for {wallet.address}\n")

    # Uniswap V3
    uni = UniswapV3(w3, config["dex"]["uniswap_v3"], gas)
    uni_positions = uni.get_positions(wallet.address)

    if uni_positions:
        print("[Uniswap V3]")
        for pos in uni_positions:
            print(f"  #{pos['id']}: {pos['token0'][:10]}.../{pos['token1'][:10]}... "
                  f"fee={pos['fee'] / 10000}% liquidity={pos['liquidity']}")
    else:
        print("[Uniswap V3] No positions")

    # Aerodrome
    print("\n[Aerodrome] Check manually: https://aerodrome.finance/liquidity")


def cmd_set_mode(args, config):
    """Switch mode in config.json."""
    mode = args.mode.lower()
    if mode not in ("auto", "manual"):
        print(f"[-] Invalid mode: {mode}. Use 'auto' or 'manual'")
        sys.exit(1)

    config["mode"] = mode
    save_config(config)
    print(f"[+] Mode set to: {mode.upper()}")


def cmd_show(args, config):
    """Show current config."""
    mode = config["mode"]
    print(f"Mode: {mode.upper()}\n")

    if mode == "manual":
        m = config["manual"]
        print(f"  DEX:     {m['dex']}")
        print(f"  Pair:    {m['token0']}/{m['token1']}")
        print(f"  Amounts: {m['amount0']} {m['token0']} + {m['amount1']} {m['token1']}")
        print(f"  Stable:  {m.get('stable', False)}")
        if m["dex"] == "uniswap":
            print(f"  Fee:     {m.get('fee', 500) / 10000}%")
    else:
        a = config["auto"]
        print(f"  Prefer DEX: {a['prefer_dex']}")
        print(f"  Interval:   {a['run_interval_seconds']}s")
        print(f"  Max Pos:    {a['max_positions']}")
        print(f"  Pairs:")
        for p in a["pairs"]:
            print(f"    - {p['amount0']} {p['token0']} + {p['amount1']} {p['token1']}")


def main():
    parser = argparse.ArgumentParser(description="Kaori - Base LP Agent")
    subparsers = parser.add_subparsers(dest="command")

    # run (default)
    subparsers.add_parser("run", help="Run LP agent (auto/manual based on config)")

    # batch
    batch_p = subparsers.add_parser("batch", help="Batch LP across wallets")
    batch_p.add_argument("--wallets", type=str, help="Wallet JSON file path")

    # positions
    subparsers.add_parser("positions", help="Check LP positions")

    # mode
    mode_p = subparsers.add_parser("mode", help="Set mode (auto/manual)")
    mode_p.add_argument("mode", choices=["auto", "manual"])

    # show
    subparsers.add_parser("show", help="Show current config")

    # discover
    disc_p = subparsers.add_parser("discover", help="Scan for new pools on Base")
    disc_p.add_argument("--blocks", type=int, default=500, help="How many blocks back to scan")

    # watch
    watch_p = subparsers.add_parser("watch", help="Watch for new pools and auto-add LP")
    watch_p.add_argument("--interval", type=int, default=30, help="Scan interval in seconds")
    watch_p.add_argument("--no-auto", action="store_true", help="Only detect, don't auto-add LP")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = load_config()

    # Import watcher/discoverer
    from core.pool_scanner import PoolScanner
    from core.watcher import run_watcher

    def cmd_discover(args, config):
        """Scan for new pools."""
        w3 = get_w3(config)
        scanner = PoolScanner(w3, config)
        current = w3.eth.block_number
        pools = scanner.scan_all(current - args.blocks, current)

        base_pools = scanner.filter_base_pools(pools)
        other_pools = [p for p in pools if not p.get("has_base_token")]

        print(f"\n{'='*60}")
        print(f"RESULTS: {len(pools)} total pools, {len(base_pools)} with Base tokens")
        print(f"{'='*60}")

        if base_pools:
            print(f"\n[Base Token Pools]")
            for p in base_pools:
                t0, t1 = p["token0"], p["token1"]
                fee_str = f" fee={p['fee']/10000}%" if p["dex"] == "uniswap_v3" else ""
                stable_str = " STABLE" if p.get("stable") else ""
                print(f"  [{p['dex']}] {t0['symbol']}/{t1['symbol']}{fee_str}{stable_str} | block={p['block']}")
                print(f"    Pool: {p['pool']}")

        if other_pools:
            print(f"\n[Other New Pools]")
            for p in other_pools[:10]:
                t0, t1 = p["token0"], p["token1"]
                print(f"  [{p['dex']}] {t0['symbol']}/{t1['symbol']} | block={p['block']}")

    def cmd_watch(args, config):
        """Watch for new pools and auto-add LP."""
        auto = not args.no_auto
        run_watcher(config, auto_add=auto, scan_interval=args.interval)

    commands = {
        "run": cmd_run,
        "batch": cmd_batch,
        "positions": cmd_positions,
        "mode": cmd_set_mode,
        "show": cmd_show,
        "discover": cmd_discover,
        "watch": cmd_watch,
    }

    commands[args.command](args, config)


if __name__ == "__main__":
    main()
