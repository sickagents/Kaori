"""New pool watcher - monitors for ANY new LP creation and auto-adds liquidity.

Works with all tokens on Base - no hardcoded list needed.
Tokens are resolved on-chain when a new pool is detected.
"""

import time
import json
from pathlib import Path
from web3 import Web3

from core.pool_scanner import PoolScanner, BASE_TOKENS
from core.tokens import TokenResolver
from core.wallet import WalletManager
from core.gas import GasEstimator
from utils.approvals import ApprovalManager


SEEN_FILE = Path("/tmp/kaori_seen_pools.json")
RESULTS_FILE = Path("/tmp/kaori_discovered_pools.json")


def load_seen() -> set:
    if SEEN_FILE.exists():
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def save_results(pools: list):
    """Save discovered pools for analysis."""
    existing = []
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE) as f:
            existing = json.load(f)

    existing.extend(pools)

    # Keep last 5000 entries
    if len(existing) > 5000:
        existing = existing[-5000:]

    with open(RESULTS_FILE, "w") as f:
        json.dump(existing, f, indent=2, default=str)


def auto_lp_new_pool(config: dict, w3: Web3, pool: dict, wallet, gas) -> bool:
    """Automatically add LP to a newly discovered pool."""
    dex_name = pool["dex"]
    t0 = pool["token0"]
    t1 = pool["token1"]

    print(f"    Auto-LP: {t0['symbol']}/{t1['symbol']} on {dex_name}")

    if pool.get("pool") == "unknown" or pool["pool"] == "0x0000000000000000000000000000000000000000":
        print(f"    SKIP: Unknown pool address")
        return False

    try:
        eth_balance = w3.eth.get_balance(wallet.address)
        eth_amount = min(eth_balance * 0.05, int(0.005 * 1e18))  # 5% balance or 0.005 ETH

        if eth_amount < int(0.0005 * 1e18):
            print(f"    SKIP: Insufficient ETH ({eth_balance / 1e18:.4f})")
            return False

        WETH = "0x4200000000000000000000000000000000000006"
        is_weth = t0["address"].lower() == WETH.lower() or t1["address"].lower() == WETH.lower()
        is_base = t0["address"] in BASE_TOKENS or t1["address"] in BASE_TOKENS

        if not is_base:
            print(f"    SKIP: No base token in pair")
            return False

        # Determine amounts
        if is_weth:
            amount0 = eth_amount
            amount1 = eth_amount
        else:
            # For USDC/AERO pairs, use small amount
            amount0 = eth_amount
            amount1 = eth_amount

        if dex_name == "aerodrome":
            from dex.aerodrome import Aerodrome
            dex = Aerodrome(w3, config["dex"]["aerodrome"], gas)

            other = t1 if t0["address"] in BASE_TOKENS else t0
            if other["address"] != WETH:
                ApprovalManager(w3, wallet).ensure_approval(
                    other["address"], config["dex"]["aerodrome"]["router"], amount1
                )

            tx_hash = dex.add_liquidity(
                wallet=wallet,
                token0=t0["address"],
                token1=t1["address"],
                amount0_desired=amount0,
                amount1_desired=amount1,
                stable=pool.get("stable", False),
                slippage=config["slippage"],
                deadline=config["deadline"],
            )

        elif dex_name == "uniswap_v3":
            from dex.uniswap_v3 import UniswapV3
            dex = UniswapV3(w3, config["dex"]["uniswap_v3"], gas)
            fee = pool.get("fee", 3000)

            other = t1 if t0["address"] in BASE_TOKENS else t0
            if other["address"] != WETH:
                ApprovalManager(w3, wallet).ensure_approval(
                    other["address"], config["dex"]["uniswap_v3"]["position_manager"], amount1
                )

            tx_hash = dex.add_liquidity(
                wallet=wallet,
                token0=t0["address"],
                token1=t1["address"],
                fee=fee,
                tick_lower=-887220,
                tick_upper=887220,
                amount0_desired=amount0,
                amount1_desired=amount1,
                slippage=config["slippage"],
                deadline=config["deadline"],
            )
        else:
            print(f"    SKIP: Unknown DEX {dex_name}")
            return False

        print(f"    TX: https://basescan.org/tx/0x{tx_hash.hex()}")
        return True

    except Exception as e:
        print(f"    ERROR: {e}")
        return False


def run_watcher(config: dict, auto_add: bool = True, scan_interval: int = 30):
    """Run the new pool watcher. Works with ALL tokens on Base."""
    w3 = Web3(Web3.HTTPProvider(config["rpc"]))
    if not w3.is_connected():
        raise ConnectionError(f"Failed to connect: {config['rpc']}")

    print(f"[+] Connected to Base (block: {w3.eth.block_number})")

    wallet = WalletManager(w3, config["wallets"]["single"])
    gas = GasEstimator(w3, config["chain_id"], config["gas_multiplier"])
    scanner = PoolScanner(w3, config)

    seen = load_seen()
    print(f"[*] Mode: {'auto-LP' if auto_add else 'detect only'}")
    print(f"[*] Wallet: {wallet.address}")
    print(f"[*] Interval: {scan_interval}s")
    print(f"[*] Tracking ALL tokens on Base (no hardcoded list)")
    print(f"[*] Seen pools: {len(seen)}")

    last_block = w3.eth.block_number

    while True:
        try:
            current_block = w3.eth.block_number
            if current_block <= last_block:
                time.sleep(scan_interval)
                continue

            pools = scanner.scan_all(last_block + 1, current_block)
            new_pools = [p for p in pools if p["pool"] not in seen]

            if new_pools:
                print(f"\n[!] {len(new_pools)} NEW POOLS!")

                # Save all discovered pools
                save_results([{**p, "token0": p["token0"]["address"], "token1": p["token1"]["address"],
                               "token0_sym": p["token0"]["symbol"], "token1_sym": p["token1"]["symbol"]}
                              for p in new_pools])

                for pool in new_pools:
                    seen.add(pool["pool"])
                    t0 = pool["token0"]
                    t1 = pool["token1"]
                    base = "BASE" if pool.get("has_base_token") else "OTHER"

                    print(f"\n  [{pool['dex'].upper()}] [{base}] {t0['symbol']}/{t1['symbol']}")
                    print(f"    Pool: {pool['pool']}")
                    print(f"    Token0: {t0['symbol']} ({t0['address'][:10]}...)")
                    print(f"    Token1: {t1['symbol']} ({t1['address'][:10]}...)")
                    if pool["dex"] == "uniswap_v3":
                        print(f"    Fee: {pool['fee'] / 10000}%")

                    if auto_add and pool.get("has_base_token"):
                        success = auto_lp_new_pool(config, w3, pool, wallet, gas)
                        if success:
                            print(f"    [+] LP ADDED!")

            save_seen(seen)
            last_block = current_block

        except Exception as e:
            print(f"[!] Error: {e}")
            time.sleep(scan_interval)

        time.sleep(scan_interval)
