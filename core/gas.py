"""EIP-1559 gas estimation for Base network."""

from web3 import Web3


class GasEstimator:
    """Estimates gas for transactions on Base."""

    def __init__(self, w3: Web3, chain_id: int = 8453, multiplier: float = 1.2):
        self.w3 = w3
        self.chain_id = chain_id
        self.multiplier = multiplier

    def get_gas_params(self) -> dict:
        """Get EIP-1559 gas parameters."""
        try:
            latest_block = self.w3.eth.get_block("latest")
            base_fee = latest_block.get("baseFeePerGas", 0)

            if base_fee > 0:
                max_priority = self.w3.eth.max_priority_fee
                max_fee = int((base_fee + max_priority) * self.multiplier)
                return {
                    "maxFeePerGas": max_fee,
                    "maxPriorityFeePerGas": max_priority,
                    "type": 2,
                }
        except Exception:
            pass

        # Fallback to legacy gas price
        gas_price = self.w3.eth.gas_price
        return {"gasPrice": int(gas_price * self.multiplier)}

    def estimate_gas(self, tx: dict) -> int:
        """Estimate gas limit for a transaction."""
        try:
            estimated = self.w3.eth.estimate_gas(tx)
            return int(estimated * 1.1)  # 10% buffer
        except Exception:
            return 500_000  # Safe default

    def build_tx(self, tx: dict, wallet_address: str, nonce: int) -> dict:
        """Build a complete transaction with gas params."""
        gas_params = self.get_gas_params()

        base_tx = {
            "from": wallet_address,
            "nonce": nonce,
            "chainId": self.chain_id,
            **gas_params,
        }

        # Merge with provided tx
        full_tx = {**base_tx, **tx}

        # Estimate gas if not provided
        if "gas" not in full_tx:
            full_tx["gas"] = self.estimate_gas(full_tx)

        return full_tx
