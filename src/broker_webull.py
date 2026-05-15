"""Webull broker using official webull-openapi-python-sdk."""
import uuid
import logging
from typing import Optional

from src.broker import Broker, OrderResult, PositionInfo

logger = logging.getLogger(__name__)

try:
    from webull.core.client import ApiClient
    from webull.trade.trade_client import TradeClient
    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False

_OPT_TYPE_MAP = {"C": "CALL", "P": "PUT"}


class WebullBroker(Broker):
    """Live broker via official Webull OpenAPI SDK."""

    def __init__(self, app_key: str, app_secret: str, endpoint: str,
                 account_id: str, password: str = ""):
        if not _HAS_SDK:
            raise ImportError(
                "webull-openapi-python-sdk not installed. "
                "Install with: pip install webull-openapi-python-sdk"
            )
        self._app_key = app_key
        self._app_secret = app_secret
        self._endpoint = endpoint
        self._account_id = account_id
        self._api = None
        self._trade = None
        self._connected = False

    def connect(self) -> bool:
        try:
            self._api = ApiClient(self._app_key, self._app_secret, "us")
            if self._endpoint:
                self._api.add_endpoint("us", self._endpoint)
            self._trade = TradeClient(self._api)
            res = self._trade.account_v2.get_account_list()
            data = res.json() if hasattr(res, 'json') else res
            if isinstance(data, dict) and data.get("code") == 0:
                self._connected = True
                logger.info("Webull connected, account_id=%s", self._account_id)
                return True
            logger.error("Webull connect unexpected response: %s", data)
            return False
        except Exception as e:
            logger.error("Webull connect failed: %s", e)
            return False

    def _check_duplicate(self, ticker: str, option_type: str,
                         strike: float, expiration: str) -> bool:
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

    def _build_option_order(self, ticker, option_type, strike, expiration,
                            quantity, price_limit, side) -> dict:
        return {
            "client_order_id": str(uuid.uuid4()),
            "combo_type": "NORMAL",
            "order_type": "LIMIT",
            "limit_price": str(price_limit),
            "quantity": str(quantity),
            "option_strategy": "SINGLE",
            "side": side,
            "time_in_force": "GTC" if side == "BUY" else "DAY",
            "entrust_type": "QTY",
            "instrument_type": "OPTION",
            "market": "US",
            "symbol": ticker,
            "legs": [{
                "side": side,
                "quantity": str(quantity),
                "symbol": ticker,
                "strike_price": f"{float(strike):.2f}",
                "option_expire_date": str(expiration),
                "instrument_type": "OPTION",
                "option_type": _OPT_TYPE_MAP.get(option_type, "CALL"),
                "market": "US",
            }],
        }

    def buy_option(self, ticker, option_type, strike, expiration,
                   quantity=1, price_limit=None) -> OrderResult:
        if not self._connected:
            return OrderResult(success=False, error="not connected")

        if self._check_duplicate(ticker, option_type, strike, expiration):
            return OrderResult(success=False, error="position already exists")

        if price_limit is None:
            return OrderResult(success=False,
                               error="LIMIT price required for options")

        order = self._build_option_order(
            ticker, option_type, strike, expiration,
            quantity, price_limit, "BUY"
        )
        client_oid = order["client_order_id"]

        try:
            res = self._trade.order_v2.place_option(self._account_id, [order])
            data = res.json() if hasattr(res, 'json') else res
            if isinstance(data, dict) and data.get("code") == 0:
                return OrderResult(success=True, order_id=client_oid,
                                   filled_price=float(price_limit))
            error_msg = str(data.get("msg", data))
            return OrderResult(success=False, error=error_msg)
        except Exception as e:
            return OrderResult(success=False, error=str(e))

    def sell_option(self, ticker, option_type, strike, expiration,
                    quantity=1, price_limit=None) -> OrderResult:
        if not self._connected:
            return OrderResult(success=False, error="not connected")

        if price_limit is None:
            return OrderResult(success=False,
                               error="LIMIT price required for options")

        order = self._build_option_order(
            ticker, option_type, strike, expiration,
            quantity, price_limit, "SELL"
        )
        client_oid = order["client_order_id"]

        try:
            res = self._trade.order_v2.place_option(self._account_id, [order])
            data = res.json() if hasattr(res, 'json') else res
            if isinstance(data, dict) and data.get("code") == 0:
                return OrderResult(success=True, order_id=client_oid,
                                   filled_price=float(price_limit))
            error_msg = str(data.get("msg", data))
            return OrderResult(success=False, error=error_msg)
        except Exception as e:
            return OrderResult(success=False, error=str(e))

    def get_positions(self) -> list[PositionInfo]:
        if not self._connected:
            return []
        try:
            res = self._trade.account_v2.get_account_position(self._account_id)
            data = res.json() if hasattr(res, 'json') else res
            if not isinstance(data, dict):
                return []
            positions_data = data.get("data", [])
            if not isinstance(positions_data, list):
                positions_data = [positions_data]
        except Exception as e:
            logger.error("get_positions failed: %s", e)
            return []

        positions = []
        for p in positions_data:
            if not isinstance(p, dict):
                continue
            symbol = p.get("symbol", "")
            opt_type_raw = p.get("option_type", p.get("direction", ""))
            if isinstance(opt_type_raw, str) and opt_type_raw.upper() == "PUT":
                opt_type = "P"
            else:
                opt_type = "C"

            try:
                strike = float(p.get("strike_price", 0))
            except (ValueError, TypeError):
                strike = 0.0

            try:
                qty = abs(int(p.get("quantity", p.get("position", 0))))
            except (ValueError, TypeError):
                qty = 0

            positions.append(PositionInfo(
                ticker=symbol,
                option_type=opt_type,
                strike=strike,
                expiration=p.get("option_expire_date",
                                 p.get("expire_date", "")),
                quantity=qty,
                avg_price=float(p.get("avg_price",
                                      p.get("average_cost", 0))),
                current_price=float(p.get("current_price",
                                          p.get("market_value", 0))),
                unrealized_pnl=float(p.get("unrealized_pnl",
                                           p.get("unrealized_pl", 0))),
                realized_pnl=float(p.get("realized_pnl",
                                         p.get("realized_pl", 0))),
            ))
        return positions

    def get_account_value(self) -> float:
        if not self._connected:
            return 0.0
        try:
            res = self._trade.account_v2.get_account_balance(self._account_id)
            data = res.json() if hasattr(res, 'json') else res
            if isinstance(data, dict):
                balance = data.get("data", data)
                return float(balance.get("total_assets",
                                         balance.get("net_liquidation", 0)))
        except Exception as e:
            logger.error("get_account_value failed: %s", e)
        return 0.0

    def get_buying_power(self) -> float:
        if not self._connected:
            return 0.0
        try:
            res = self._trade.account_v2.get_account_balance(self._account_id)
            data = res.json() if hasattr(res, 'json') else res
            if isinstance(data, dict):
                balance = data.get("data", data)
                return float(balance.get("available_cash",
                                         balance.get("buying_power", 0)))
        except Exception as e:
            logger.error("get_buying_power failed: %s", e)
        return 0.0
