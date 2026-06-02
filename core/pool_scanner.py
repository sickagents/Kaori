"""Pool scanner - monitors on-chain events for ANY token on Base.

Scans Uniswap V3 Factory and Aerodrome Factory for new pool creation.
No hardcoded token list - resolves all tokens on-chain dynamically.
"""

import time
from web3 import Web3
from core.tokens import TokenResolver


# Event signatures
V3_POOL_CREATED_TOPIC = "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118"

# Known stable/base tokens for pair detection
BASE_TOKENS = {
    "0x4200000000000000000000000000000000000006",  # WETH
    "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC
    "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA",  # USDbC
    "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",  # DAI
    "0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22",  # cbETH
    "0x940181a94A35A4569E4529A3CDfB74e38FD98631",  # AERO
}


class PoolScanner:
    """Scans on-chain events for new pool creation. Works with ANY token."""

    def __init__(self, w3: Web3, config: dict):
        self.w3 = w3
        self.config = config
        self.v3_factory = Web3.to_checksum_address(config["dex"]["uniswap_v3"]["factory"])
        self.aero_factory = Web3.to_checksum_address(config["dex"]["aerodrome"]["factory"])
        self.resolver = TokenResolver(w3)

    def _has_base_token(self, token0: str, token1: str) -> bool:
        """Check if pair has at least one base/stable token."""
        t0 = Web3.to_checksum_address(token0)
        t1 = Web3.to_checksum_address(token1)
        return t0 in BASE_TOKENS or t1 in BASE_TOKENS

    def _get_other_token(self, token0: str, token1: str) -> str:
        """Get the non-base token address."""
        t0 = Web3.to_checksum_address(token0)
        t1 = Web3.to_checksum_address(token1)
        if t0 in BASE_TOKENS:
            return t1
        return t0

    def scan_v3_new_pools(self, from_block: int, to_block: int) -> list:
        """Scan for new Uniswap V3 pools."""
        pools = []
        chunk_size = 50

        for start in range(from_block, to_block + 1, chunk_size):
            end = min(start + chunk_size - 1, to_block)
            try:
                logs = self.w3.eth.get_logs({
                    "fromBlock": start,
                    "toBlock": end,
                    "address": self.v3_factory,
                    "topics": [V3_POOL_CREATED_TOPIC],
                })

                for log in logs:
                    token0 = "0x" + log["topics"][1].hex()[-40:]
                    token1 = "0x" + log["topics"][2].hex()[-40:]
                    fee = int(log["topics"][3].hex(), 16)

                    data = log["data"].hex() if isinstance(log["data"], bytes) else log["data"]
                    pool_addr = "0x" + data[-40:]

                    # Resolve both tokens on-chain
                    t0_info = self.resolver.resolve(token0)
                    t1_info = self.resolver.resolve(token1)

                    pools.append({
                        "dex": "uniswap_v3",
                        "pool": Web3.to_checksum_address(pool_addr),
                        "token0": t0_info,
                        "token1": t1_info,
                        "fee": fee,
                        "block": log["blockNumber"],
                        "has_base_token": self._has_base_token(token0, token1),
                    })

            except Exception:
                pass

            time.sleep(0.15)

        return pools

    def scan_aero_new_pools(self, from_block: int, to_block: int) -> list:
        """Scan for new Aerodrome pools."""
        pools = []
        chunk_size = 50

        for start in range(from_block, to_block + 1, chunk_size):
            end = min(start + chunk_size - 1, to_block)
            try:
                logs = self.w3.eth.get_logs({
                    "fromBlock": start,
                    "toBlock": end,
                    "address": self.aero_factory,
                })

                for log in logs:
                    topics = log["topics"]
                    if len(topics) >= 3:
                        token0 = "0x" + topics[1].hex()[-40:]
                        token1 = "0x" + topics[2].hex()[-40:]

                        t0_info = self.resolver.resolve(token0)
                        t1_info = self.resolver.resolve(token1)

                        data_hex = log["data"].hex() if isinstance(log["data"], bytes) else log["data"]
                        pool_addr = "0x" + data_hex[-40:] if len(data_hex) >= 40 else "0x0"

                        pools.append({
                            "dex": "aerodrome",
                            "pool": Web3.to_checksum_address(pool_addr) if pool_addr != "0x0" else "unknown",
                            "token0": t0_info,
                            "token1": t1_info,
                            "stable": len(topics) > 3 and int(topics[3].hex(), 16) == 1,
                            "block": log["blockNumber"],
                            "has_base_token": self._has_base_token(token0, token1),
                        })

            except Exception:
                pass

            time.sleep(0.15)

        return pools

    def scan_v4_new_pools(self, from_block: int, to_block: int) -> list:
        """Scan for new Uniswap V4 pools (placeholder for Base deployment)."""
        return []

    def scan_all(self, from_block: int, to_block: int) -> list:
        """Scan all DEXs for new pools."""
        all_pools = []

        print(f"[*] Scanning blocks {from_block} -> {to_block}...")

        v3 = self.scan_v3_new_pools(from_block, to_block)
        all_pools.extend(v3)
        if v3:
            print(f"    V3: {len(v3)} new pools")

        aero = self.scan_aero_new_pools(from_block, to_block)
        all_pools.extend(aero)
        if aero:
            print(f"    Aerodrome: {len(aero)} new pools")

        v4 = self.scan_v4_new_pools(from_block, to_block)
        all_pools.extend(v4)
        if v4:
            print(f"    V4: {len(v4)} new pools")

        return all_pools

    def filter_base_pools(self, pools: list) -> list:
        """Filter pools that have at least one base/stable token."""
        return [p for p in pools if p.get("has_base_token", False)]

    def filter_new_token_pools(self, pools: list) -> list:
        """Filter pools where at least one token is NOT in the base set.
        These are 'new token' pools - the interesting ones for early LP."""
        result = []
        for p in pools:
            t0_addr = p["token0"]["address"]
            t1_addr = p["token1"]["address"]
            # At least one token is NOT a base token = new/unknown token
            if t0_addr not in BASE_TOKENS or t1_addr not in BASE_TOKENS:
                result.append(p)
        return result
