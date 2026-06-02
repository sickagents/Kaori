"""New pool watcher - monitors for new LP creation and auto-adds liquidity."""

import time
import json
from pathlib import Path
from web3 import Web3

from core.pool_scanner import PoolScanner
from core.wallet import WalletManager
from core.gas import GasEstimator
from utils.approvals import ApprovalManager


SEEN_FILE = Path("/tmp/kaori_seen_pools.json")


def load_seen() -> set:
    """Load seen pool addresses."""
    if SEEN_FILE.exists():
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    """Save seen pool addresses."""
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def auto_lp_new_pool(config: dict, w3: Web3, pool: dict, wallet, gas) -> bool:
    """Automatically add LP to a newly discovered pool."""
    dex_name = pool["dex"]
    t0 = pool["token0"]
    t1 = pool["token1"]

    print(f"    Auto-LP: {t0['symbol']}/{t1['symbol']} on {dex_name}")

    # Skip if pool address is unknown
    if pool.get("pool") == "unknown" or pool["pool"] == "0x0000000000000000000000000000000000000000":
        print(f"    SKIP: Unknown pool address")
        return False

    # Calculate amounts based on available balance
    try:
        # Check ETH balance
        eth_balance = w3.eth.get_balance(wallet.address)
        eth_amount = min(eth_balance * 0.1, int(0.005 * 1e18))  # Use 10% of balance or 0.005 ETH max

        if eth_amount < int(0.001 * 1e18):
            print(f"    SKIP: Insufficient ETH balance ({eth_balance / 1e18:.4f} ETH)")
            return False

        # For WETH pairs, wrap ETH
        WETH = "0x4200000000000000000000000000000000000006"
        is_weth_pair = t0["address"].lower() == WETH.lower() or t1["address"].lower() == WETH.lower()

        if dex_name == "aerodrome":
            from dex.aerodrome import Aerodrome
            dex = Aerodrome(w3, config["dex"]["aerodrome"], gas)

            if is_weth_pair:
                # Pair with WETH
                if t0["address"].lower() == WETH.lower():
                    amount0 = eth_amount
                    amount1 = eth_amount  # 1:1 for simplicity, adjust with price oracle
                else:
                    amount0 = eth_amount
                    amount1 = eth_amount

                # Approve non-WETH token
                other_token = t1 if t0["address"].lower() == WETH.lower() else t0
                ApprovalManager(w3, wallet).ensure_approval(
                    other_token["address"], config["dex"]["aerodrome"]["router"], amount1
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
            else:
                print(f"    SKIP: Non-WETH pair not supported for auto-LP yet")
                return False

        elif dex_name == "uniswap_v3":
            from dex.uniswap_v3 import UniswapV3
            dex = UniswapV3(w3, config["dex"]["uniswap_v3"], gas)
            fee = pool.get("fee", 3000)

            if is_weth_pair:
                amount0 = eth_amount
                amount1 = eth_amount

                other_token = t1 if t0["address"].lower() == WETH.lower() else t0
                ApprovalManager(w3, wallet).ensure_approval(
                    other_token["address"], config["dex"]["uniswap_v3"]["position_manager"], amount1
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
                print(f"    SKIP: Non-WETH pair not supported for auto-LP yet")
                return False
        else:
            print(f"    SKIP: Unknown DEX {dex_name}")
            return False

        print(f"    TX: https://basescan.org/tx/0x{tx_hash.hex()}")
        return True

    except Exception as e:
        print(f"    ERROR: {e}")
        return False


def run_watcher(config: dict, auto_add: bool = True, scan_interval: int = 30):
    """Run the new pool watcher."""
    w3 = Web3(Web3.HTTPProvider(config["rpc"]))
    if not w3.is_connected():
        raise ConnectionError(f"Failed to connect: {config['rpc']}")

    print(f"[+] Connected to Base (block: {w3.eth.block_number})")

    wallet_path = config["wallets"]["single"]
    wallet = WalletManager(w3, wallet_path)
    gas = GasEstimator(w3, config["chain_id"], config["gas_multiplier"])
    scanner = PoolScanner(w3, config)

    seen = load_seen()
    print(f"[*] Watching for new pools (auto-add: {auto_add})")
    print(f"[*] Wallet: {wallet.address}")
    print(f"[*] Scan interval: {scan_interval}s")
    print(f"[*] Seen pools: {len(seen)}")

    last_block = w3.eth.block_number

    while True:
        try:
            current_block = w3.eth.block_number

            if current_block <= last_block:
                time.sleep(scan_interval)
                continue

            # Scan for new pools
            pools = scanner.scan_all(last_block + 1, current_block)
            new_pools = [p for p in pools if p["pool"] not in seen]

            if new_pools:
                print(f"\n[!] {len(new_pools)} NEW POOLS DETECTED!")

                for pool in new_pools:
                    seen.add(pool["pool"])
                    t0 = pool["token0"]
                    t1 = pool["token1"]

                    print(f"\n  [{pool['dex'].upper()}] {t0['symbol']}/{t1['symbol']}")
                    print(f"    Pool: {pool['pool']}")
                    print(f"    Block: {pool['block']}")
                    if pool["dex"] == "uniswap_v3":
                        print(f"    Fee: {pool['fee'] / 10000}%")
                    print(f"    Base token: {pool.get('has_base_token', False)}")

                    # Auto-add LP if enabled and pool has a base token
                    if auto_add and pool.get("has_base_token"):
                        success = auto_lp_new_pool(config, w3, pool, wallet, gas)
                        if success:
                            print(f"    [+] LP added successfully!")
                        else:
                            print(f"    [-] Auto-LP skipped or failed")

            # Save state
            save_seen(seen)
            last_block = current_block

        except Exception as e:
            print(f"[!] Error: {e}")
            time.sleep(scan_interval)

        time.sleep(scan_interval)
