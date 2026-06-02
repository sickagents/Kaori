"""Wallet management for LP agent."""

import os
from eth_account import Account


class WalletManager:
    """Manages wallet signing and address."""

    def __init__(self, w3, wallet_path: str = None, private_key: str = None):
        self.w3 = w3

        if private_key:
            self.private_key = private_key
        elif wallet_path:
            self.private_key = self._load_wallet(wallet_path)
        else:
            raise ValueError("Must provide wallet_path or private_key")

        self.account = Account.from_key(self.private_key)
        self.address = self.account.address
        self._nonce = None

    def _load_wallet(self, path: str) -> str:
        """Load private key from .env file or JSON."""
        path = os.path.expanduser(path)

        if path.endswith(".json"):
            import json
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, list):
                return data[0]["private_key"]
            return data["private_key"]

        # .env format
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("PRIVATE_KEY="):
                    return line.split("=", 1)[1].strip()

        raise ValueError(f"No private key found in {path}")

    def get_nonce(self) -> int:
        """Get next nonce (cached, increments on use)."""
        if self._nonce is None:
            self._nonce = self.w3.eth.get_transaction_count(self.address)
        nonce = self._nonce
        self._nonce += 1
        return nonce

    def reset_nonce(self):
        """Reset cached nonce."""
        self._nonce = None

    def sign_and_send(self, tx: dict) -> bytes:
        """Sign and send a transaction. Returns tx hash."""
        signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        return tx_hash

    def wait_for_receipt(self, tx_hash: bytes, timeout: int = 120):
        """Wait for transaction receipt."""
        return self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
