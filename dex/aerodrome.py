"""Aerodrome Finance router wrapper for Base."""

import time
from web3 import Web3
from dex.base_dex import BaseDEX

# Aerodrome Router ABI (key functions)
ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"},
            {"internalType": "bool", "name": "stable", "type": "bool"},
            {"internalType": "uint256", "name": "amountADesired", "type": "uint256"},
            {"internalType": "uint256", "name": "amountBDesired", "type": "uint256"},
            {"internalType": "uint256", "name": "amountAMin", "type": "uint256"},
            {"internalType": "uint256", "name": "amountBMin", "type": "uint256"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"},
        ],
        "name": "addLiquidity",
        "outputs": [
            {"internalType": "uint256", "name": "amountA", "type": "uint256"},
            {"internalType": "uint256", "name": "amountB", "type": "uint256"},
            {"internalType": "uint256", "name": "liquidity", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"},
            {"internalType": "bool", "name": "stable", "type": "bool"},
            {"internalType": "uint256", "name": "liquidity", "type": "uint256"},
            {"internalType": "uint256", "name": "amountAMin", "type": "uint256"},
            {"internalType": "uint256", "name": "amountBMin", "type": "uint256"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"},
        ],
        "name": "removeLiquidity",
        "outputs": [
            {"internalType": "uint256", "name": "amountA", "type": "uint256"},
            {"internalType": "uint256", "name": "amountB", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"},
            {"internalType": "bool", "name": "stable", "type": "bool"},
        ],
        "name": "getReserves",
        "outputs": [
            {"internalType": "uint256", "name": "reserveA", "type": "uint256"},
            {"internalType": "uint256", "name": "reserveB", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"},
            {"internalType": "bool", "name": "stable", "type": "bool"},
        ],
        "name": "pairFor",
        "outputs": [{"internalType": "address", "name": "pair", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# LP Token ABI
LP_TOKEN_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class Aerodrome(BaseDEX):
    """Aerodrome Finance DEX wrapper."""

    def __init__(self, w3, config: dict, gas_estimator):
        super().__init__(w3, config, gas_estimator)
        self.router = w3.eth.contract(
            address=Web3.to_checksum_address(config["router"]),
            abi=ROUTER_ABI,
        )
        self.factory_address = Web3.to_checksum_address(config["factory"])

    def find_pool(self, token0: str, token1: str, stable: bool = False) -> dict | None:
        """Find Aerodrome pool for token pair."""
        t0 = Web3.to_checksum_address(token0)
        t1 = Web3.to_checksum_address(token1)

        # Sort tokens
        if t0.lower() > t1.lower():
            t0, t1 = t1, t0
            stable = stable  # stable flag stays with the pair order

        try:
            pool_address = self.router.functions.pairFor(t0, t1, stable).call()
            if pool_address == "0x0000000000000000000000000000000000000000":
                # Try opposite stable
                if not stable:
                    pool_address = self.router.functions.pairFor(t0, t1, True).call()
                    if pool_address != "0x0000000000000000000000000000000000000000":
                        stable = True
                    else:
                        return None
                else:
                    return None

            return {
                "address": pool_address,
                "token0": t0,
                "token1": t1,
                "stable": stable,
            }
        except Exception:
            return None

    def add_liquidity(
        self,
        wallet,
        token0: str,
        token1: str,
        amount0_desired: int = 0,
        amount1_desired: int = 0,
        stable: bool = False,
        slippage: float = 0.5,
        deadline: int = 600,
    ) -> bytes:
        """Add liquidity to Aerodrome pool."""
        t0 = Web3.to_checksum_address(token0)
        t1 = Web3.to_checksum_address(token1)

        # Sort tokens
        if t0.lower() > t1.lower():
            t0, t1 = t1, t0
            amount0_desired, amount1_desired = amount1_desired, amount0_desired

        slippage_mult = 1 - (slippage / 100)
        amount0_min = int(amount0_desired * slippage_mult)
        amount1_min = int(amount1_desired * slippage_mult)

        deadline_ts = int(time.time()) + deadline

        # Build addLiquidity transaction
        add_tx = self.router.functions.addLiquidity(
            t0, t1, stable,
            amount0_desired, amount1_desired,
            amount0_min, amount1_min,
            wallet.address, deadline_ts,
        ).build_transaction({
            "from": wallet.address,
            "nonce": wallet.get_nonce(),
            **self.gas.get_gas_params(),
        })

        add_tx["gas"] = self.gas.estimate_gas(add_tx)

        tx_hash = wallet.sign_and_send(add_tx)
        receipt = wallet.wait_for_receipt(tx_hash)

        if receipt["status"] != 1:
            raise Exception(f"Transaction reverted: https://basescan.org/tx/0x{tx_hash.hex()}")

        return tx_hash

    def remove_liquidity(
        self,
        wallet,
        token0: str,
        token1: str,
        liquidity: int,
        stable: bool = False,
        slippage: float = 0.5,
        deadline: int = 600,
    ) -> bytes:
        """Remove liquidity from Aerodrome pool."""
        t0 = Web3.to_checksum_address(token0)
        t1 = Web3.to_checksum_address(token1)

        if t0.lower() > t1.lower():
            t0, t1 = t1, t0

        slippage_mult = 1 - (slippage / 100)
        # For remove, we set min amounts to 0 for simplicity (use slippage in production)
        deadline_ts = int(time.time()) + deadline

        remove_tx = self.router.functions.removeLiquidity(
            t0, t1, stable, liquidity, 0, 0, wallet.address, deadline_ts,
        ).build_transaction({
            "from": wallet.address,
            "nonce": wallet.get_nonce(),
            **self.gas.get_gas_params(),
        })

        remove_tx["gas"] = self.gas.estimate_gas(remove_tx)

        tx_hash = wallet.sign_and_send(remove_tx)
        receipt = wallet.wait_for_receipt(tx_hash)

        if receipt["status"] != 1:
            raise Exception(f"Transaction reverted: https://basescan.org/tx/0x{tx_hash.hex()}")

        return tx_hash

    def get_positions(self, address: str) -> list:
        """Get Aerodrome LP positions for an address."""
        # Aerodrome doesn't have a simple way to enumerate all LP positions
        # We'd need to track Transfer events or know the pool addresses
        # For now, return empty (user should track manually)
        return []
