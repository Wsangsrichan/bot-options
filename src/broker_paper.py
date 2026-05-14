"""Paper trading broker — wraps PositionManager for the Broker interface."""
from datetime import datetime

from src.broker import Broker, OrderResult, PositionInfo
from src.position_manager import PositionManager


class PaperBroker(Broker):
    """Paper trading broker that delegates to PositionManager."""

    def __init__(self, position_manager: PositionManager):
        self.pm = position_manager
        self._connected = True
        self._order_counter = 0

    def connect(self) -> bool:
        return self._connected

    def buy_option(self, ticker, option_type, strike, expiration,
                   quantity=1, price_limit=None) -> OrderResult:
        alert = {
            "ticker": ticker,
            "option_type": option_type,
            "strike": strike,
            "expiration": expiration,
            "bid": price_limit if price_limit else 0,
            "ask": price_limit if price_limit else 0,
            "delta": 0,
            "iv": 0,
        }
        # Need price for entry — use price_limit or default 0 (will be set by PM)
        if not price_limit:
            alert["bid"] = 1.0  # placeholder
            alert["ask"] = 1.0

        spot_price = 0  # placeholder
        pos_id = self.pm.open_position(alert, spot_price)
        if pos_id is None:
            return OrderResult(success=False, error="insufficient_funds_or_invalid_alert")

        self._order_counter += 1
        pos = next((p for p in self.pm.store.get_open_positions() if p["id"] == pos_id), None)
        filled = pos["entry_price"] if pos else 0
        return OrderResult(success=True, order_id=f"PAPER-{self._order_counter}", filled_price=filled)

    def sell_option(self, ticker, option_type, strike, expiration,
                    quantity=1, price_limit=None) -> OrderResult:
        positions = self.pm.store.get_open_positions()
        match = None
        for p in positions:
            if (p["ticker"] == ticker and p["option_type"] == option_type
                    and p["strike"] == strike and p["expiration"] == expiration):
                match = p
                break

        if match is None:
            return OrderResult(success=False, error="position_not_found")

        exit_price = price_limit if price_limit else match["entry_price"]
        pnl = self.pm.close_position(match["id"], exit_price, reason="manual_close")

        self._order_counter += 1
        return OrderResult(success=True, order_id=f"PAPER-{self._order_counter}",
                           filled_price=exit_price)

    def get_positions(self) -> list[PositionInfo]:
        positions = self.pm.store.get_open_positions()
        result = []
        for p in positions:
            unrealized = None  # Computed by caller (dashboard) via live pricing
            result.append(PositionInfo(
                ticker=p["ticker"],
                option_type=p["option_type"],
                strike=p["strike"],
                expiration=p["expiration"],
                quantity=p["contracts"],
                avg_price=p["entry_price"],
                current_price=p["entry_price"],
                unrealized_pnl=unrealized,
            ))
        return result

    def get_account_value(self) -> float:
        portfolio = self.pm.get_portfolio()
        return portfolio["initial_balance"] + portfolio["total_pnl"]

    def get_buying_power(self) -> float:
        portfolio = self.pm.get_portfolio()
        return portfolio["cash"]
