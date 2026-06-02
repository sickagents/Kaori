#!/usr/bin/env python3
"""
Base LP Agent - Automated Liquidity Pool management on Base network.

Supports Uniswap V3 (concentrated liquidity) and Aerodrome (stable/volatile pools).
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

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.wallet import WalletManager
from core.tokens import TokenRegistry
from core.gas import GasEstimator
from dex.uniswap_v3 import UniswapV3
from dex.aerodrome import Aerodrome
from utils.approvals import ApprovalManager
from utils.formatting import format_amount, parse_amount


def load_config(config_path: str = None) -> dict:
    """Load config from YAML file."""
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_w3(rpc: str) -> Web3:
    """Initialize Web3 connection."""
    w3 = Web3(Web3.HTTPProvider(rpc))
    if not w3.is_connected():
        raise ConnectionError(f"Failed to connect to RPC: {rpc}")
    print(f"[+] Connected to Base (block: {w3.eth.block_number})")
    return w3


def cmd_add(args, config):
    """Add liquidity to a pool."""
    w3 = get_w3(config["rpc"])
    wallet = WalletManager(w3, args.wallet or os.path.expanduser("~/.hermes/credentials/wallet-keys-evm.env"))
    tokens = TokenRegistry(config["tokens"])
    gas = GasEstimator(w3, config["chain_id"], config["gas_multiplier"])

    # Resolve token addresses
    t0 = tokens.resolve(args.token0)
    t1 = tokens.resolve(args.token1)
    amount0 = parse_amount(args.amount0, t0["decimals"])
    amount1 = parse_amount(args.amount1, t1["decimals"])

    dex_name = args.dex.lower()

    if dex_name == "uniswap":
        dex = UniswapV3(w3, config["dex"]["uniswap_v3"], gas)
        fee = int(args.fee) if args.fee else 500
        tick_lower = int(args.tick_lower) if args.tick_lower else -887220
        tick_upper = int(args.tick_upper) if args.tick_upper else 887220

        print(f"[*] Adding Uniswap V3 LP: {args.amount0} {args.token0} + {args.amount1} {args.token1}")
        print(f"    Fee tier: {fee / 10000}%, Tick range: [{tick_lower}, {tick_upper}]")

        # Approve tokens
        ApprovalManager(w3, wallet).ensure_approval(
            t0["address"], config["dex"]["uniswap_v3"]["position_manager"], amount0
        )
        ApprovalManager(w3, wallet).ensure_approval(
            t1["address"], config["dex"]["uniswap_v3"]["position_manager"], amount1
        )

        # Add liquidity
        tx_hash = dex.add_liquidity(
            wallet=wallet,
            token0=t0["address"],
            token1=t1["address"],
            fee=fee,
            tick_lower=tick_lower,
            tick_upper=tick_upper,
            amount0_desired=amount0,
            amount1_desired=amount1,
            slippage=config["slippage"],
            deadline=config["deadline"],
        )
        print(f"[+] Liquidity added! TX: https://basescan.org/tx/0x{tx_hash.hex()}")

    elif dex_name == "aerodrome":
        dex = Aerodrome(w3, config["dex"]["aerodrome"], gas)
        stable = args.stable.lower() == "true" if args.stable else False

        print(f"[*] Adding Aerodrome LP: {args.amount0} {args.token0} + {args.amount1} {args.token1}")
        print(f"    Stable: {stable}")

        # Approve tokens
        ApprovalManager(w3, wallet).ensure_approval(
            t0["address"], config["dex"]["aerodrome"]["router"], amount0
        )
        ApprovalManager(w3, wallet).ensure_approval(
            t1["address"], config["dex"]["aerodrome"]["router"], amount1
        )

        # Add liquidity
        tx_hash = dex.add_liquidity(
            wallet=wallet,
            token0=t0["address"],
            token1=t1["address"],
            amount0_desired=amount0,
            amount1_desired=amount1,
            stable=stable,
            slippage=config["slippage"],
            deadline=config["deadline"],
        )
        print(f"[+] Liquidity added! TX: https://basescan.org/tx/0x{tx_hash.hex()}")

    else:
        print(f"[-] Unknown DEX: {dex_name}. Use 'uniswap' or 'aerodrome'")
        sys.exit(1)


def cmd_auto(args, config):
    """Auto-find best pool and add liquidity."""
    w3 = get_w3(config["rpc"])
    tokens = TokenRegistry(config["tokens"])
    t0 = tokens.resolve(args.token0)
    t1 = tokens.resolve(args.token1)

    print(f"[*] Finding best pool for {args.token0}/{args.token1}...")

    # Check Aerodrome first (usually better rewards on Base)
    aero = Aerodrome(w3, config["dex"]["aerodrome"], GasEstimator(w3, config["chain_id"], config["gas_multiplier"]))
    aero_pool = aero.find_pool(t0["address"], t1["address"])

    # Check Uniswap V3
    uni = UniswapV3(w3, config["dex"]["uniswap_v3"], GasEstimator(w3, config["chain_id"], config["gas_multiplier"]))
    uni_pools = uni.find_pools(t0["address"], t1["address"])

    print(f"\n[+] Found pools:")
    if aero_pool:
        print(f"    Aerodrome: {aero_pool['address']} (stable: {aero_pool['stable']})")
    for p in uni_pools:
        print(f"    Uniswap V3: {p['address']} (fee: {p['fee'] / 10000}%)")

    # Default: use Aerodrome if available, else Uniswap V3 0.3%
    if aero_pool:
        print(f"\n[*] Using Aerodrome pool")
        args.dex = "aerodrome"
        args.stable = str(aero_pool["stable"])
    elif uni_pools:
        best = uni_pools[0]
        print(f"\n[*] Using Uniswap V3 pool (fee: {best['fee'] / 10000}%)")
        args.dex = "uniswap"
        args.fee = str(best["fee"])
    else:
        print("[-] No pools found for this pair")
        sys.exit(1)

    cmd_add(args, config)


def cmd_positions(args, config):
    """Check LP positions."""
    w3 = get_w3(config["rpc"])
    wallet = WalletManager(w3, args.wallet or os.path.expanduser("~/.hermes/credentials/wallet-keys-evm.env"))
    gas = GasEstimator(w3, config["chain_id"], config["gas_multiplier"])

    print(f"[*] Checking positions for {wallet.address}...")

    # Uniswap V3 positions
    uni = UniswapV3(w3, config["dex"]["uniswap_v3"], gas)
    uni_positions = uni.get_positions(wallet.address)

    if uni_positions:
        print(f"\n[Uniswap V3 Positions]")
        for pos in uni_positions:
            print(f"  #{pos['id']}: {pos['token0']}/{pos['token1']} "
                  f"fee={pos['fee'] / 10000}% | "
                  f"liquidity={pos['liquidity']} | "
                  f"range=[{pos['tick_lower']}, {pos['tick_upper']}]")
    else:
        print("\n[Uniswap V3] No positions found")

    # Aerodrome LP tokens
    aero = Aerodrome(w3, config["dex"]["aerodrome"], gas)
    aero_positions = aero.get_positions(wallet.address)

    if aero_positions:
        print(f"\n[Aerodrome Positions]")
        for pos in aero_positions:
            print(f"  Pool: {pos['pool']} | "
                  f"Balance: {pos['balance']} | "
                  f"Token0: {pos['token0']} | Token1: {pos['token1']}")
    else:
        print("\n[Aerodrome] No positions found")


def cmd_remove(args, config):
    """Remove liquidity from a position."""
    w3 = get_w3(config["rpc"])
    wallet = WalletManager(w3, args.wallet or os.path.expanduser("~/.hermes/credentials/wallet-keys-evm.env"))
    gas = GasEstimator(w3, config["chain_id"], config["gas_multiplier"])

    position_id = int(args.position_id)
    percent = int(args.percent)

    print(f"[*] Removing {percent}% liquidity from position #{position_id}")

    uni = UniswapV3(w3, config["dex"]["uniswap_v3"], gas)
    tx_hash = uni.remove_liquidity(
        wallet=wallet,
        position_id=position_id,
        percent=percent,
        slippage=config["slippage"],
        deadline=config["deadline"],
    )
    print(f"[+] Liquidity removed! TX: https://basescan.org/tx/0x{tx_hash.hex()}")


def cmd_batch(args, config):
    """Batch LP across multiple wallets."""
    w3 = get_w3(config["rpc"])
    tokens = TokenRegistry(config["tokens"])
    t0 = tokens.resolve(args.token0)
    t1 = tokens.resolve(args.token1)

    # Load wallets
    wallets_path = Path(args.wallets).expanduser()
    with open(wallets_path) as f:
        wallet_data = json.load(f)

    print(f"[*] Batch LP: {len(wallet_data)} wallets, {args.amount0} {args.token0} + {args.amount1} {args.token1}")

    gas = GasEstimator(w3, config["chain_id"], config["gas_multiplier"])
    amount0 = parse_amount(args.amount0, t0["decimals"])
    amount1 = parse_amount(args.amount1, t1["decimals"])

    results = {"ok": 0, "error": 0, "errors": []}

    for i, wd in enumerate(wallet_data):
        try:
            wallet = WalletManager(w3, private_key=wd["private_key"])
            print(f"\n[{i + 1}/{len(wallet_data)}] {wallet.address[:10]}...")

            dex_name = args.dex.lower()

            if dex_name == "aerodrome":
                dex = Aerodrome(w3, config["dex"]["aerodrome"], gas)
                stable = args.stable.lower() == "true" if args.stable else False

                ApprovalManager(w3, wallet).ensure_approval(
                    t0["address"], config["dex"]["aerodrome"]["router"], amount0
                )
                ApprovalManager(w3, wallet).ensure_approval(
                    t1["address"], config["dex"]["aerodrome"]["router"], amount1
                )

                tx_hash = dex.add_liquidity(
                    wallet=wallet, token0=t0["address"], token1=t1["address"],
                    amount0_desired=amount0, amount1_desired=amount1,
                    stable=stable, slippage=config["slippage"], deadline=config["deadline"],
                )
            else:
                dex = UniswapV3(w3, config["dex"]["uniswap_v3"], gas)
                fee = int(args.fee) if args.fee else 500

                ApprovalManager(w3, wallet).ensure_approval(
                    t0["address"], config["dex"]["uniswap_v3"]["position_manager"], amount0
                )
                ApprovalManager(w3, wallet).ensure_approval(
                    t1["address"], config["dex"]["uniswap_v3"]["position_manager"], amount1
                )

                tx_hash = dex.add_liquidity(
                    wallet=wallet, token0=t0["address"], token1=t1["address"],
                    fee=fee, tick_lower=-887220, tick_upper=887220,
                    amount0_desired=amount0, amount1_desired=amount1,
                    slippage=config["slippage"], deadline=config["deadline"],
                )

            print(f"    TX: https://basescan.org/tx/0x{tx_hash.hex()}")
            results["ok"] += 1

        except Exception as e:
            print(f"    ERROR: {e}")
            results["error"] += 1
            results["errors"].append({"index": i, "address": wd.get("address", "unknown"), "error": str(e)})

        # Small delay between wallets
        if i < len(wallet_data) - 1:
            time.sleep(2)

    print(f"\n[+] Batch complete: {results['ok']} ok, {results['error']} errors")
    if results["errors"]:
        with open("/tmp/lp_batch_errors.json", "w") as f:
            json.dump(results["errors"], f, indent=2)
        print(f"    Errors saved to /tmp/lp_batch_errors.json")


def main():
    parser = argparse.ArgumentParser(description="Base LP Agent - Automated Liquidity Pool Management")
    parser.add_argument("--config", type=str, help="Config file path")
    parser.add_argument("--wallet", type=str, help="Wallet file path (.env format)")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # add command
    add_parser = subparsers.add_parser("add", help="Add liquidity to a pool")
    add_parser.add_argument("--dex", required=True, choices=["uniswap", "aerodrome"], help="DEX to use")
    add_parser.add_argument("--token0", required=True, help="Token0 address or symbol")
    add_parser.add_argument("--token1", required=True, help="Token1 address or symbol")
    add_parser.add_argument("--amount0", required=True, help="Amount of token0")
    add_parser.add_argument("--amount1", required=True, help="Amount of token1")
    add_parser.add_argument("--fee", type=str, help="Fee tier (Uniswap: 100, 500, 3000, 10000)")
    add_parser.add_argument("--tick-lower", type=str, help="Lower tick (Uniswap)")
    add_parser.add_argument("--tick-upper", type=str, help="Upper tick (Uniswap)")
    add_parser.add_argument("--stable", type=str, help="Stable pool (Aerodrome: true/false)")

    # auto command
    auto_parser = subparsers.add_parser("auto", help="Auto-find best pool and add liquidity")
    auto_parser.add_argument("--token0", required=True, help="Token0 address or symbol")
    auto_parser.add_argument("--token1", required=True, help="Token1 address or symbol")
    auto_parser.add_argument("--amount0", required=True, help="Amount of token0")
    auto_parser.add_argument("--amount1", required=True, help="Amount of token1")
    auto_parser.add_argument("--fee", type=str, help="Fee tier override (Uniswap)")
    auto_parser.add_argument("--stable", type=str, help="Stable pool override (Aerodrome)")

    # positions command
    pos_parser = subparsers.add_parser("positions", help="Check LP positions")

    # remove command
    rm_parser = subparsers.add_parser("remove", help="Remove liquidity")
    rm_parser.add_argument("--position-id", required=True, help="Position NFT ID")
    rm_parser.add_argument("--percent", default="100", help="Percentage to remove (1-100)")

    # batch command
    batch_parser = subparsers.add_parser("batch", help="Batch LP across multiple wallets")
    batch_parser.add_argument("--wallets", required=True, help="Wallet JSON file path")
    batch_parser.add_argument("--dex", required=True, choices=["uniswap", "aerodrome"], help="DEX to use")
    batch_parser.add_argument("--token0", required=True, help="Token0 address or symbol")
    batch_parser.add_argument("--token1", required=True, help="Token1 address or symbol")
    batch_parser.add_argument("--amount0", required=True, help="Amount of token0 per wallet")
    batch_parser.add_argument("--amount1", required=True, help="Amount of token1 per wallet")
    batch_parser.add_argument("--fee", type=str, help="Fee tier (Uniswap)")
    batch_parser.add_argument("--stable", type=str, help="Stable pool (Aerodrome)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = load_config(args.config)

    commands = {
        "add": cmd_add,
        "auto": cmd_auto,
        "positions": cmd_positions,
        "remove": cmd_remove,
        "batch": cmd_batch,
    }

    commands[args.command](args, config)


if __name__ == "__main__":
    main()
