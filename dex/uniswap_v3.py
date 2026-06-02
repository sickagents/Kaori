"""Uniswap V3 NonfungiblePositionManager wrapper for Base."""

import time
from web3 import Web3
from dex.base_dex import BaseDEX

# NonfungiblePositionManager ABI (key functions only)
POSITION_MANAGER_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "token0", "type": "address"},
            {"internalType": "address", "name": "token1", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"},
            {"internalType": "int24", "name": "tickLower", "type": "int24"},
            {"internalType": "int24", "name": "tickUpper", "type": "int24"},
            {"internalType": "uint256", "name": "amount0Desired", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1Desired", "type": "uint256"},
            {"internalType": "uint256", "name": "amount0Min", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1Min", "type": "uint256"},
            {"internalType": "address", "name": "recipient", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"},
        ],
        "name": "mint",
        "outputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
            {"internalType": "uint256", "name": "amount0", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1", "type": "uint256"},
        ],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
            {"internalType": "uint256", "name": "amount0Min", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1Min", "type": "uint256"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"},
        ],
        "name": "decreaseLiquidity",
        "outputs": [
            {"internalType": "uint256", "name": "amount0", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "uint256", "name": "amount0Desired", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1Desired", "type": "uint256"},
            {"internalType": "uint256", "name": "amount0Min", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1Min", "type": "uint256"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"},
        ],
        "name": "increaseLiquidity",
        "outputs": [
            {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
            {"internalType": "uint256", "name": "amount0", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1", "type": "uint256"},
        ],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
            {"internalType": "bytes", "name": "data", "type": "bytes"},
        ],
        "name": "collect",
        "outputs": [
            {"internalType": "uint256", "name": "amount0", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1", "type": "uint256"},
        ],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "positions",
        "outputs": [
            {"internalType": "uint96", "name": "nonce", "type": "uint96"},
            {"internalType": "address", "name": "operator", "type": "address"},
            {"internalType": "address", "name": "token0", "type": "address"},
            {"internalType": "address", "name": "token1", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"},
            {"internalType": "int24", "name": "tickLower", "type": "int24"},
            {"internalType": "int24", "name": "tickUpper", "type": "int24"},
            {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
            {"internalType": "uint256", "name": "feeGrowthInside0LastX128", "type": "uint256"},
            {"internalType": "uint256", "name": "feeGrowthInside1LastX128", "type": "uint256"},
            {"internalType": "uint128", "name": "tokensOwed0", "type": "uint128"},
            {"internalType": "uint128", "name": "tokensOwed1", "type": "uint128"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "uint256", "name": "index", "type": "uint256"},
        ],
        "name": "tokenOfOwnerByIndex",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "recipient", "type": "address"},
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
            {"internalType": "uint256", "name": "amount0Max", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1Max", "type": "uint256"},
        ],
        "name": "burn",
        "outputs": [
            {"internalType": "uint256", "name": "amount0", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1", "type": "uint256"},
        ],
        "stateMutability": "payable",
        "type": "function",
    },
]

# Factory ABI for pool lookup
FACTORY_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"},
        ],
        "name": "getPool",
        "outputs": [{"internalType": "address", "name": "pool", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class UniswapV3(BaseDEX):
    """Uniswap V3 concentrated liquidity manager."""

    FEE_TIERS = [100, 500, 3000, 10000]  # 0.01%, 0.05%, 0.3%, 1%

    def __init__(self, w3, config: dict, gas_estimator):
        super().__init__(w3, config, gas_estimator)
        self.position_manager = w3.eth.contract(
            address=Web3.to_checksum_address(config["position_manager"]),
            abi=POSITION_MANAGER_ABI,
        )
        self.factory = w3.eth.contract(
            address=Web3.to_checksum_address(config["factory"]),
            abi=FACTORY_ABI,
        )

    def find_pools(self, token0: str, token1: str) -> list:
        """Find all Uniswap V3 pools for a token pair."""
        pools = []
        t0 = Web3.to_checksum_address(token0)
        t1 = Web3.to_checksum_address(token1)

        for fee in self.FEE_TIERS:
            try:
                pool = self.factory.functions.getPool(t0, t1, fee).call()
                if pool != "0x0000000000000000000000000000000000000000":
                    # Check if pool has liquidity
                    liquidity = self._get_pool_liquidity(pool)
                    pools.append({
                        "address": pool,
                        "fee": fee,
                        "liquidity": liquidity,
                    })
            except Exception:
                continue

        # Sort by liquidity (highest first)
        pools.sort(key=lambda p: p["liquidity"], reverse=True)
        return pools

    def _get_pool_liquidity(self, pool_address: str) -> int:
        """Get pool liquidity (slot0 + liquidity)."""
        pool_abi = [
            {
                "inputs": [],
                "name": "liquidity",
                "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
                "stateMutability": "view",
                "type": "function",
            },
        ]
        pool = self.w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=pool_abi)
        try:
            return pool.functions.liquidity().call()
        except Exception:
            return 0

    def add_liquidity(
        self,
        wallet,
        token0: str,
        token1: str,
        fee: int = 500,
        tick_lower: int = -887220,
        tick_upper: int = 887220,
        amount0_desired: int = 0,
        amount1_desired: int = 0,
        slippage: float = 0.5,
        deadline: int = 600,
    ) -> bytes:
        """Add concentrated liquidity position."""
        # Sort tokens (Uniswap requires token0 < token1)
        t0 = Web3.to_checksum_address(token0)
        t1 = Web3.to_checksum_address(token1)
        if t0.lower() > t1.lower():
            t0, t1 = t1, t0
            amount0_desired, amount1_desired = amount1_desired, amount0_desired

        # Calculate min amounts with slippage
        slippage_mult = 1 - (slippage / 100)
        amount0_min = int(amount0_desired * slippage_mult)
        amount1_min = int(amount1_desired * slippage_mult)

        deadline_ts = int(time.time()) + deadline

        # Build mint transaction
        mint_tx = self.position_manager.functions.mint(
            t0, t1, fee, tick_lower, tick_upper,
            amount0_desired, amount1_desired,
            amount0_min, amount1_min,
            wallet.address, deadline_ts,
        ).build_transaction({
            "from": wallet.address,
            "value": 0,
            "nonce": wallet.get_nonce(),
            **self.gas.get_gas_params(),
        })

        # Estimate gas
        mint_tx["gas"] = self.gas.estimate_gas(mint_tx)

        # Sign and send
        tx_hash = wallet.sign_and_send(mint_tx)
        receipt = wallet.wait_for_receipt(tx_hash)

        if receipt["status"] != 1:
            raise Exception(f"Transaction reverted: https://basescan.org/tx/0x{tx_hash.hex()}")

        return tx_hash

    def remove_liquidity(
        self,
        wallet,
        position_id: int,
        percent: int = 100,
        slippage: float = 0.5,
        deadline: int = 600,
    ) -> bytes:
        """Remove liquidity from a position."""
        # Get position details
        pos = self.position_manager.functions.positions(position_id).call()
        liquidity = pos[7]  # liquidity field

        liquidity_to_remove = liquidity * percent // 100

        if liquidity_to_remove == 0:
            raise Exception("No liquidity to remove")

        deadline_ts = int(time.time()) + deadline

        # Decrease liquidity
        decrease_tx = self.position_manager.functions.decreaseLiquidity(
            position_id, liquidity_to_remove, 0, 0, deadline_ts,
        ).build_transaction({
            "from": wallet.address,
            "nonce": wallet.get_nonce(),
            **self.gas.get_gas_params(),
        })
        decrease_tx["gas"] = self.gas.estimate_gas(decrease_tx)

        tx_hash = wallet.sign_and_send(decrease_tx)
        receipt = wallet.wait_for_receipt(tx_hash)

        if receipt["status"] != 1:
            raise Exception(f"Decrease liquidity failed: https://basescan.org/tx/0x{tx_hash.hex()}")

        # Collect tokens
        collect_tx = self.position_manager.functions.collect(
            wallet.address, position_id, 2**128 - 1, 2**128 - 1,
        ).build_transaction({
            "from": wallet.address,
            "nonce": wallet.get_nonce(),
            **self.gas.get_gas_params(),
        })
        collect_tx["gas"] = self.gas.estimate_gas(collect_tx)

        tx_hash2 = wallet.sign_and_send(collect_tx)
        receipt2 = wallet.wait_for_receipt(tx_hash2)

        if receipt2["status"] != 1:
            raise Exception(f"Collect failed: https://basescan.org/tx/0x{tx_hash2.hex()}")

        return tx_hash2

    def get_positions(self, address: str) -> list:
        """Get all Uniswap V3 positions for an address."""
        positions = []
        try:
            balance = self.position_manager.functions.balanceOf(address).call()
            for i in range(balance):
                try:
                    token_id = self.position_manager.functions.tokenOfOwnerByIndex(address, i).call()
                    pos = self.position_manager.functions.positions(token_id).call()
                    positions.append({
                        "id": token_id,
                        "token0": pos[2],
                        "token1": pos[3],
                        "fee": pos[4],
                        "tick_lower": pos[5],
                        "tick_upper": pos[6],
                        "liquidity": pos[7],
                    })
                except Exception:
                    continue
        except Exception:
            pass
        return positions
