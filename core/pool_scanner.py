"""Pool scanner - monitors on-chain events for new LP creation on Base."""

import time
import json
from web3 import Web3
from eth_account import Account


# Event signatures
# V3: PoolCreated(address indexed token0, address indexed token1, uint24 indexed fee, int24 tickSpacing, address pool)
V3_POOL_CREATED_TOPIC = "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118"

# Aerodrome: PoolCreated(address indexed token0, address indexed token1, bool indexed stable, address pool, uint)
# Different signature - we'll detect by scanning factory address

# Uniswap V4: Initialize(bytes32 indexed poolId, address indexed currency0, address indexed currency1, uint24 fee, int24 tickSpacing, address hooks)
V4_INITIALIZE_TOPIC = "0x3fd553db44f207b1f41348cfc4d251860814af9eadc470e8e7895e4d120511f4"


class PoolScanner:
    """Scans on-chain events for new pool creation."""

    def __init__(self, w3: Web3, config: dict):
        self.w3 = w3
        self.config = config
        self.v3_factory = Web3.to_checksum_address(config["dex"]["uniswap_v3"]["factory"])
        self.aero_factory = Web3.to_checksum_address(config["dex"]["aerodrome"]["factory"])
        self.tokens = config.get("tokens", {})
        self.token_addresses = set()

        # Build known token set
        for info in self.tokens.values():
            self.token_addresses.add(Web3.to_checksum_address(info["address"]))

    def _is_known_token(self, address: str) -> bool:
        """Check if a token address is in our known list."""
        return Web3.to_checksum_address(address) in self.token_addresses

    def _get_token_info(self, address: str) -> dict:
        """Get on-chain token info (symbol, decimals)."""
        address = Web3.to_checksum_address(address)

        # Check cache first
        for sym, info in self.tokens.items():
            if Web3.to_checksum_address(info["address"]) == address:
                return {"symbol": sym, "decimals": info["decimals"], "address": address}

        # Fetch from chain
        try:
            abi = [
                {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
                {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
            ]
            c = self.w3.eth.contract(address=address, abi=abi)
            sym = c.functions.symbol().call()
            dec = c.functions.decimals().call()
            return {"symbol": sym, "decimals": dec, "address": address}
        except Exception:
            return {"symbol": "UNKNOWN", "decimals": 18, "address": address}

    def scan_v3_new_pools(self, from_block: int, to_block: int) -> list:
        """Scan for new Uniswap V3 pools."""
        pools = []
        chunk_size = 50  # RPC limit

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

                    # Decode pool address from data
                    data = log["data"].hex() if isinstance(log["data"], bytes) else log["data"].hex()
                    pool_addr = "0x" + data[-40:]

                    t0_info = self._get_token_info(token0)
                    t1_info = self._get_token_info(token1)

                    pools.append({
                        "dex": "uniswap_v3",
                        "pool": Web3.to_checksum_address(pool_addr),
                        "token0": t0_info,
                        "token1": t1_info,
                        "fee": fee,
                        "block": log["blockNumber"],
                        "has_base_token": self._is_known_token(token0) or self._is_known_token(token1),
                    })

            except Exception as e:
                pass

            time.sleep(0.2)

        return pools

    def scan_aero_new_pools(self, from_block: int, to_block: int) -> list:
        """Scan for new Aerodrome pools by monitoring factory events."""
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
                        # Try to decode as PoolCreated
                        token0 = "0x" + topics[1].hex()[-40:] if len(topics) > 1 else None
                        token1 = "0x" + topics[2].hex()[-40:] if len(topics) > 2 else None

                        if token0 and token1:
                            t0_info = self._get_token_info(token0)
                            t1_info = self._get_token_info(token1)

                            # Decode pool address from data
                            data_hex = log["data"].hex() if isinstance(log["data"], bytes) else log["data"]
                            pool_addr = "0x" + data_hex[-40:] if len(data_hex) >= 40 else "0x0"

                            pools.append({
                                "dex": "aerodrome",
                                "pool": Web3.to_checksum_address(pool_addr) if pool_addr != "0x0" else "unknown",
                                "token0": t0_info,
                                "token1": t1_info,
                                "stable": len(topics) > 3 and int(topics[3].hex(), 16) == 1,
                                "block": log["blockNumber"],
                                "has_base_token": self._is_known_token(token0) or self._is_known_token(token1),
                            })

            except Exception as e:
                pass

            time.sleep(0.2)

        return pools

    def scan_v4_new_pools(self, from_block: int, to_block: int) -> list:
        """Scan for new Uniswap V4 pools (if deployed on Base)."""
        # V4 PoolManager not yet on Base - placeholder
        # When deployed, monitor Initialize events from the PoolManager address
        pools = []
        return pools

    def scan_all(self, from_block: int, to_block: int) -> list:
        """Scan all DEXs for new pools."""
        all_pools = []

        print(f"[*] Scanning blocks {from_block} -> {to_block} for new pools...")

        v3 = self.scan_v3_new_pools(from_block, to_block)
        all_pools.extend(v3)
        if v3:
            print(f"    Uniswap V3: {len(v3)} new pools")

        aero = self.scan_aero_new_pools(from_block, to_block)
        all_pools.extend(aero)
        if aero:
            print(f"    Aerodrome: {len(aero)} new pools")

        v4 = self.scan_v4_new_pools(from_block, to_block)
        all_pools.extend(v4)
        if v4:
            print(f"    Uniswap V4: {len(v4)} new pools")

        return all_pools

    def filter_base_pools(self, pools: list) -> list:
        """Filter pools that contain at least one known Base token."""
        return [p for p in pools if p.get("has_base_token", False)]
