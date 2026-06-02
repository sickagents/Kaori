"""ERC-20 approval management."""

from web3 import Web3
from core.tokens import TokenResolver


class ApprovalManager:
    """Manages ERC-20 token approvals."""

    MAX_UINT256 = 2**256 - 1

    def __init__(self, w3, wallet):
        self.w3 = w3
        self.wallet = wallet
        self.resolver = TokenResolver(w3)

    def get_allowance(self, token_address: str, spender: str) -> int:
        return self.resolver.get_allowance(token_address, self.wallet.address, spender)

    def ensure_approval(self, token_address: str, spender: str, amount: int):
        current = self.get_allowance(token_address, spender)
        if current >= amount:
            return
        self.approve(token_address, spender, self.MAX_UINT256)

    def approve(self, token_address: str, spender: str, amount: int) -> bytes:
        from core.tokens import ERC20_ABI
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address), abi=ERC20_ABI
        )

        tx = contract.functions.approve(spender, amount).build_transaction({
            "from": self.wallet.address,
            "nonce": self.wallet.get_nonce(),
            "chainId": self.w3.eth.chain_id,
        })

        try:
            latest = self.w3.eth.get_block("latest")
            base_fee = latest.get("baseFeePerGas", 0)
            if base_fee > 0:
                priority = self.w3.eth.max_priority_fee
                tx["maxFeePerGas"] = int((base_fee + priority) * 1.2)
                tx["maxPriorityFeePerGas"] = priority
                tx["type"] = 2
            else:
                tx["gasPrice"] = int(self.w3.eth.gas_price * 1.2)
        except Exception:
            tx["gasPrice"] = int(self.w3.eth.gas_price * 1.2)

        tx["gas"] = 100_000

        tx_hash = self.wallet.sign_and_send(tx)
        receipt = self.wallet.wait_for_receipt(tx_hash)

        if receipt["status"] != 1:
            raise Exception(f"Approval failed: https://basescan.org/tx/0x{tx_hash.hex()}")

        return tx_hash
