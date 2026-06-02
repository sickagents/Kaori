"""Token registry and ERC-20 helpers."""

from web3 import Web3


# Minimal ERC-20 ABI
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_amount", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
]


class TokenRegistry:
    """Registry of known tokens with resolution from symbol or address."""

    def __init__(self, tokens_config: dict):
        self.tokens = {}
        for symbol, info in tokens_config.items():
            self.tokens[symbol.upper()] = {
                "address": Web3.to_checksum_address(info["address"]),
                "decimals": info["decimals"],
                "symbol": symbol.upper(),
            }

    def resolve(self, identifier: str) -> dict:
        """Resolve token by symbol or address."""
        key = identifier.upper()
        if key in self.tokens:
            return self.tokens[key]

        # Try as address
        try:
            addr = Web3.to_checksum_address(identifier)
            # Look up in registry
            for t in self.tokens.values():
                if t["address"].lower() == addr.lower():
                    return t
            # Unknown token, return defaults
            return {"address": addr, "decimals": 18, "symbol": "UNKNOWN"}
        except Exception:
            raise ValueError(f"Unknown token: {identifier}")

    @staticmethod
    def get_contract(w3: Web3, address: str):
        """Get ERC-20 contract instance."""
        return w3.eth.contract(address=Web3.to_checksum_address(address), abi=ERC20_ABI)

    @staticmethod
    def get_balance(w3: Web3, token_address: str, wallet_address: str) -> int:
        """Get token balance."""
        contract = w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)
        return contract.functions.balanceOf(wallet_address).call()

    @staticmethod
    def get_allowance(w3: Web3, token_address: str, owner: str, spender: str) -> int:
        """Get token allowance."""
        contract = w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)
        return contract.functions.allowance(owner, spender).call()
