"""Dynamic token resolver - no hardcoded list, resolves any token on-chain."""

from web3 import Web3


# Minimal ERC-20 ABI
ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_amount", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
]


class TokenResolver:
    """Resolves any ERC-20 token on-chain. Caches results. No hardcoded list needed."""

    def __init__(self, w3: Web3):
        self.w3 = w3
        self._cache = {}  # address -> {symbol, decimals, name}

    def resolve(self, address: str) -> dict:
        """Resolve token info from on-chain. Caches after first call."""
        addr = Web3.to_checksum_address(address)

        if addr in self._cache:
            return self._cache[addr]

        try:
            contract = self.w3.eth.contract(address=addr, abi=ERC20_ABI)
            symbol = contract.functions.symbol().call()
            decimals = contract.functions.decimals().call()
            name = contract.functions.name().call()
        except Exception:
            symbol = "UNKNOWN"
            decimals = 18
            name = "Unknown Token"

        info = {
            "address": addr,
            "symbol": symbol,
            "decimals": decimals,
            "name": name,
        }
        self._cache[addr] = info
        return info

    def resolve_by_symbol(self, symbol: str) -> dict | None:
        """Look up cached token by symbol. Returns None if not found."""
        symbol = symbol.upper()
        for info in self._cache.values():
            if info["symbol"].upper() == symbol:
                return info
        return None

    def get_balance(self, token_address: str, wallet_address: str) -> int:
        """Get token balance for a wallet."""
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address), abi=ERC20_ABI
        )
        return contract.functions.balanceOf(wallet_address).call()

    def get_allowance(self, token_address: str, owner: str, spender: str) -> int:
        """Get token allowance."""
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address), abi=ERC20_ABI
        )
        return contract.functions.allowance(owner, spender).call()

    def cached_tokens(self) -> dict:
        """Return all cached tokens."""
        return dict(self._cache)
