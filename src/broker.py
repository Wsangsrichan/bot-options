"""Abstract broker interface for option trading."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str] = None
    filled_price: Optional[float] = None
    error: Optional[str] = None


@dataclass
class PositionInfo:
    ticker: str
    option_type: str
    strike: float
    expiration: str
    quantity: int
    avg_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


class Broker(ABC):
    """Abstract broker interface for option trading."""

    @abstractmethod
    def connect(self) -> bool:
        """Connect to broker API. Returns True if successful."""

    @abstractmethod
    def buy_option(self, ticker, option_type, strike, expiration,
                   quantity=1, price_limit=None) -> OrderResult:
        """Buy an option contract."""

    @abstractmethod
    def sell_option(self, ticker, option_type, strike, expiration,
                    quantity=1, price_limit=None) -> OrderResult:
        """Sell (close) an option contract."""

    @abstractmethod
    def get_positions(self) -> list[PositionInfo]:
        """Get current option positions."""

    @abstractmethod
    def get_account_value(self) -> float:
        """Get total account value."""

    @abstractmethod
    def get_buying_power(self) -> float:
        """Get available buying power."""
