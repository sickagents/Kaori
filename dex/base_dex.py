"""Abstract DEX interface."""

from abc import ABC, abstractmethod


class BaseDEX(ABC):
    """Base class for DEX implementations."""

    def __init__(self, w3, config: dict, gas_estimator):
        self.w3 = w3
        self.config = config
        self.gas = gas_estimator

    @abstractmethod
    def add_liquidity(self, wallet, **kwargs) -> bytes:
        """Add liquidity. Returns tx hash."""
        pass

    @abstractmethod
    def remove_liquidity(self, wallet, **kwargs) -> bytes:
        """Remove liquidity. Returns tx hash."""
        pass

    @abstractmethod
    def get_positions(self, address: str) -> list:
        """Get all LP positions for an address."""
        pass
