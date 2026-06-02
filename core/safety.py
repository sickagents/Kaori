"""Safety checks before deploying LP positions.

Inspired by Meridian's executor.js - 14+ checks before any deploy.
"""

from web3 import Web3
from core.state import get_open_positions, is_on_cooldown


class SafetyError(Exception):
    """Raised when a safety check fails."""
    pass


def run_deploy_checks(config: dict, w3: Web3, wallet_address: str,
                      pool: dict, amount_wei: int, dex: str) -> list:
    """Run all safety checks before deploying. Returns list of warnings.
    Raises SafetyError on hard failures."""
    warnings = []
    risk = config.get("risk", {})
    mgmt = config.get("management", {})
    screening = config.get("screening", {})

    # 1. Max positions check
    max_positions = risk.get("max_positions", 5)
    open_pos = get_open_positions()
    if len(open_pos) >= max_positions:
        raise SafetyError(f"Max positions reached ({len(open_pos)}/{max_positions})")

    # 2. No duplicate pool
    for pos in open_pos:
        if pos.get("pool", "").lower() == pool.get("pool", "").lower():
            raise SafetyError(f"Already have position in pool {pool['pool'][:10]}...")

    # 3. No duplicate token (same non-base token in another pool)
    token1 = pool.get("token1", {}).get("address", "")
    if token1:
        for pos in open_pos:
            if pos.get("token1_address", "").lower() == token1.lower():
                raise SafetyError(f"Already have position with token {token1[:10]}...")

    # 4. Cooldown check
    if is_on_cooldown(pool.get("pool", "")):
        raise SafetyError(f"Pool {pool['pool'][:10]}... is on cooldown")

    if token1 and is_on_cooldown(token1):
        raise SafetyError(f"Token {token1[:10]}... is on cooldown")

    # 5. Amount checks
    if amount_wei <= 0:
        raise SafetyError("Amount must be > 0")

    min_amount = int(mgmt.get("min_deploy_eth", 0.001) * 1e18)
    if amount_wei < min_amount:
        raise SafetyError(f"Amount {amount_wei / 1e18:.4f} ETH below minimum {min_amount / 1e18:.4f}")

    max_amount = int(risk.get("max_deploy_eth", 1.0) * 1e18)
    if amount_wei > max_amount:
        raise SafetyError(f"Amount {amount_wei / 1e18:.4f} ETH above maximum {max_amount / 1e18:.4f}")

    # 6. Balance check
    balance = w3.eth.get_balance(wallet_address)
    gas_reserve = int(mgmt.get("gas_reserve_eth", 0.01) * 1e18)
    if balance < amount_wei + gas_reserve:
        raise SafetyError(
            f"Insufficient balance: {balance / 1e18:.4f} ETH, "
            f"need {amount_wei / 1e18:.4f} + {gas_reserve / 1e18:.4f} gas reserve"
        )

    if balance < amount_wei + gas_reserve * 2:
        warnings.append(f"Low balance after deploy: {(balance - amount_wei) / 1e18:.4f} ETH remaining")

    # 7. Pool TVL check (if available)
    min_tvl = screening.get("min_tvl", 0)
    pool_tvl = pool.get("tvl", 0)
    if min_tvl and pool_tvl and pool_tvl < min_tvl:
        warnings.append(f"Pool TVL ${pool_tvl:,.0f} below screening minimum ${min_tvl:,.0f}")

    # 8. Pool age check (if available)
    min_pool_age = screening.get("min_pool_age_blocks", 100)
    pool_block = pool.get("block", 0)
    current_block = w3.eth.block_number
    if pool_block and (current_block - pool_block) < min_pool_age:
        warnings.append(f"Pool is very new ({current_block - pool_block} blocks old)")

    # 9. Fee tier check
    fee = pool.get("fee", 0)
    min_fee = screening.get("min_fee", 100)
    max_fee = screening.get("max_fee", 10000)
    if fee and (fee < min_fee or fee > max_fee):
        warnings.append(f"Fee tier {fee / 10000}% outside screening range")

    return warnings
