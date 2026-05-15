"""Webull broker implementation for real options trading."""
import uuid
import logging
from typing import Optional

from src.broker import Broker, OrderResult, PositionInfo

logger = logging.getLogger(__name__)

try:
    from webull import webull
    _HAS_WEBULL = True
except ImportError:
    _HAS_WEBULL = False

# Map our option_type codes to Webull direction
_SIDE_MAP = {"C": "BUY", "P": "BUY"}
_WEBULL_ACTION = {"BUY": "BUY", "SELL": "SELL"}
_DIRECTION_MAP = {"C": "call", "P": "put"}


class WebullBroker(Broker):
    """Live broker via Webull API."""

    def __init__(self, app_key: str, app_secret: str, endpoint: str,
                 account_id: str, password: str = ""):
        if not _HAS_WEBULL:
            raise ImportError("webull SDK not installed")
        self._wb = webull()
        self._app_key = app_key
        self._app_secret = app_secret
        self._endpoint = endpoint
        self._account_id = account_id
        self._password = password
        self._connected = False

    def connect(self) -> bool:
        if not _HAS_WEBULL:
            logger.error("webull SDK not installed")
            return False

        if self._endpoint:
            self._wb.add_endpoint("us", self._endpoint)

        try:
            self._wb.api_login(
                access_token=self._app_key,
                refresh_token=self._app_secret,
                uuid=self._account_id,
            )
            if self._password:
                self._wb.get_trade_token(self._password)
            self._connected = True
            logger.info("Webull connected, account_id=%s", self._account_id)
            return True
        except Exception as e:
            logger.error("Webull connect failed: %s", e)
            return False

    def _find_option_id(self, ticker: str, option_type: str,
                         strike: float, expiration: str) -> Optional[str]:
        """Look up Webull option ID (tickerId) for a specific contract."""
        direction = _DIRECTION_MAP.get(option_type, "all")
        try:
            opts = self._wb.get_options_by_strike_and_expire_date(
                stock=ticker, expireDate=expiration,
                strike=str(strike), direction=direction,
            )
            for opt in opts:
                if opt.get("direction") == direction:
                    return str(opt.get("tickerId", opt.get("id", "")))
            # Fallback: return first match if direction filter didn't match
            if opts:
                return str(opts[0].get("tickerId", opts[0].get("id", "")))
        except Exception as e:
            logger.error("Option lookup failed for %s %s %s %s: %s",
                         ticker, option_type, strike, expiration, e)
        return None

    def _check_duplicate(self, ticker: str, option_type: str,
                         strike: float, expiration: str) -> bool:
        """Return True if position already exists for this contract."""
        try:
            positions = self.get_positions()
            for pos in positions:
                if (pos.ticker == ticker
                        and pos.option_type == option_type
                        and pos.strike == strike
                        and pos.expiration == expiration
                        and pos.quantity > 0):
                    return True
        except Exception:
            pass
        return False

    def buy_option(self, ticker, option_type, strike, expiration,
                    quantity=1, price_limit=None) -> OrderResult:
        if not self._connected:
            return OrderResult(success=False, error="not connected")

        if self._check_duplicate(ticker, option_type, strike, expiration):
            return OrderResult(success=False, error="position already exists")

        if price_limit is None:
            return OrderResult(success=False, error="LIMIT price required for options")

        option_id = self._find_option_id(ticker, option_type, strike, expiration)
        if not option_id:
            return OrderResult(success=False,
                               error=f"option not found: {ticker} {option_type} {strike} {expiration}")

        try:
            client_oid = str(uuid.uuid4())
            self._wb.place_order_option(
                optionId=option_id,
                lmtPrice=float(price_limit),
                action="BUY",
                orderType="LMT",
                enforce="GTC",
                quant=quantity,
            )
            return OrderResult(success=True, order_id=client_oid,
                               filled_price=float(price_limit))
        except Exception as e:
            return OrderResult(success=False, error=str(e))

    def sell_option(self, ticker, option_type, strike, expiration,
                    quantity=1, price_limit=None) -> OrderResult:
        if not self._connected:
            return OrderResult(success=False, error="not connected")

        if price_limit is None:
            return OrderResult(success=False, error="LIMIT price required for options")

        option_id = self._find_option_id(ticker, option_type, strike, expiration)
        if not option_id:
            return OrderResult(success=False,
                               error=f"option not found: {ticker} {option_type} {strike} {expiration}")

        try:
            client_oid = str(uuid.uuid4())
            self._wb.place_order_option(
                optionId=option_id,
                lmtPrice=float(price_limit),
                action="SELL",
                orderType="LMT",
                enforce="DAY",
                quant=quantity,
            )
            return OrderResult(success=True, order_id=client_oid,
                               filled_price=float(price_limit))
        except Exception as e:
            return OrderResult(success=False, error=str(e))

    def get_positions(self) -> list[PositionInfo]:
        if not self._connected:
            return []

        try:
            raw_positions = self._wb.get_positions()
        except Exception as e:
            logger.error("get_positions failed: %s", e)
            return []

        positions = []
        for p in raw_positions:
            # Filter to OPTION positions only
            if p.get("tickerType") != "OPTION":
                continue

            symbol = p.get("symbol", "")
            direction = p.get("direction", "")
            opt_type = "C" if direction.upper() == "CALL" else "P"

            try:
                strike = float(p.get("strikePrice", 0))
            except (ValueError, TypeError):
                strike = 0.0

            positions.append(PositionInfo(
                ticker=symbol,
                option_type=opt_type,
                strike=strike,
                expiration=p.get("expireDate", ""),
                quantity=int(p.get("quantity", 0)),
                avg_price=float(p.get("avgPrice", 0)),
                current_price=float(p.get("currentPrice", 0)),
                unrealized_pnl=float(p.get("unrealizedPnl", 0)),
                realized_pnl=float(p.get("realizedPnl", 0)),
            ))
        return positions

    def get_account_value(self) -> float:
        if not self._connected:
            return 0.0
        try:
            portfolio = self._wb.get_portfolio()
            return float(portfolio.get("totalAmt", 0))
        except Exception as e:
            logger.error("get_account_value failed: %s", e)
            return 0.0

    def get_buying_power(self) -> float:
        if not self._connected:
            return 0.0
        try:
            portfolio = self._wb.get_portfolio()
            return float(portfolio.get("cashBalance", 0))
        except Exception as e:
            logger.error("get_buying_power failed: %s", e)
            return 0.0
