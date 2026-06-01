"""
Upstox Python SDK — MCP Server
------------------------------
Exposes the Upstox trading API as MCP tools using the stdio transport.
Run with: python server.py

Requires the `mcp` package:  pip install mcp
Requires the upstox-official-python package:
    pip install upstox-python
or copy the upstox_client/ folder from the SDK into this directory.

Environment variables (set before running):
    UPSTOX_API_KEY      — your Upstox API key
    UPSTOX_API_SECRET   — your Upstox API secret
    UPSTOX_ACCESS_TOKEN — OAuth access token (alternative to api_key+secret)
    UPSTOX_SANDBOX      — 1 to use sandbox environment (default: 0)

Example config.yaml entry:
    mcp_servers:
      upstox:
        command: python
        args: ["/path/to/server.py"]
        env:
          UPSTOX_API_KEY: "your-key"
          UPSTOX_API_SECRET: "your-secret"
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
import time
from typing import Any

# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

_FASTMCP_AVAILABLE = False
try:
    from mcp.server.fastmcp import FastMCP
    _FASTMCP_AVAILABLE = True
except ImportError:
    FastMCP = None  # type: ignore[assignment,misc]

logger = logging.getLogger("upstox_mcp")


# ---------------------------------------------------------------------------
# SDK loader
# ---------------------------------------------------------------------------

def _load_upstox_client():
    """
    Import the upstox SDK.
    Priority:
      1. The `upstox` package (pip install upstox-python)
      2. The local upstox_client/ folder (same directory as this script)
    """
    try:
        import upstox
        return upstox
    except ImportError:
        pass

    # Try local upstox_client/
    local_path = os.path.join(os.path.dirname(__file__), "upstox_client")
    if os.path.isdir(local_path):
        sys.path.insert(0, os.path.dirname(__file__))
        try:
            import upstox_client
            return upstox_client
        except ImportError:
            pass

    raise ImportError(
        "Could not find the upstox SDK. Either install it with "
        "`pip install upstox-python` or place the upstox_client/ SDK "
        "folder next to server.py."
    )


# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

_upstox_client: Any = None
_api_key: str | None = None
_api_secret: str | None = None
_access_token: str | None = None
_sandbox: bool = False


def _get_client():
    global _upstox_client
    if _upstox_client is not None:
        return _upstox_client

    sdk = _load_upstox_client()

    global _api_key, _api_secret, _access_token, _sandbox
    _api_key = os.environ.get("UPSTOX_API_KEY", "")
    _api_secret = os.environ.get("UPSTOX_API_SECRET", "")
    _access_token = os.environ.get("UPSTOX_ACCESS_TOKEN", "")
    _sandbox = os.environ.get("UPSTOX_SANDBOX", "0") == "1"

    config = sdk.Configuration(sandbox=_sandbox)

    if _access_token:
        config.access_token = _access_token
    elif _api_key:
        config.api_key["apiKey"] = _api_key

    _upstox_client = sdk.ApiClient(config)
    return _upstox_client


# ---------------------------------------------------------------------------
# Result serialiser — convert SDK model objects to JSON-serialisable dicts
# ---------------------------------------------------------------------------

def _serialise(obj: Any) -> Any:
    """Recursively convert SDK model objects to plain dicts/lists."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode()
    if isinstance(obj, list):
        return [_serialise(item) for item in obj]
    if hasattr(obj, "__dict__"):
        out = {}
        for k, v in obj.__dict__.items():
            if not k.startswith("_"):
                out[k] = _serialise(v)
        return out
    return obj


def _call_api(api_method, **kwargs) -> dict:
    """
    Call an SDK API method, catch errors, and return a JSON-compatible result.
    Result shape: {"ok": true, "data": ...} or {"ok": false, "error": "..."}
    """
    try:
        result = api_method(**kwargs)
        return {"ok": True, "data": _serialise(result)}
    except Exception as exc:
        logger.error("API call failed: %s", exc)
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Build the MCP server
# ---------------------------------------------------------------------------

if not _FASTMCP_AVAILABLE:
    raise ImportError("`pip install mcp` is required to run this server.")

mcp = FastMCP("upstox")


# -------------------------------------------------------------------------
# AUTH / LOGIN
# -------------------------------------------------------------------------

@mcp.tool()
def get_authorization_url(client_id: str, redirect_uri: str, api_version: str = "v2",
                           state: str = "", scope: str = "") -> dict:
    """
    Build the Upstox OAuth authorisation URL.
    Open this URL in a browser to complete the login flow.
    After login, Upstox redirects to redirect_uri with an auth code.
    """
    sdk = _load_upstox_client()
    api = sdk.LoginApi(_get_client())
    return _call_api(api.authorize, client_id=client_id, redirect_uri=redirect_uri,
                     api_version=api_version, state=state, scope=scope)


@mcp.tool()
def exchange_token(authorization_code: str, client_id: str, client_secret: str,
                   redirect_uri: str, grant_type: str = "authorization_code",
                   api_version: str = "v2") -> dict:
    """
    Exchange an OAuth authorisation code for an access token.
    Use this after the user has authorised via get_authorization_url.
    """
    sdk = _load_upstox_client()
    api = sdk.LoginApi(_get_client())
    return _call_api(
        api.token, api_version=api_version, code=authorization_code,
        client_id=client_id, client_secret=client_secret,
        redirect_uri=redirect_uri, grant_type=grant_type
    )


@mcp.tool()
def init_indie_user_token(body: dict, client_id: str, api_version: str = "v3") -> dict:
    """
    Initialise a token request for an indie user.
    body: dict matching IndieUserTokenRequest fields (e.g. app_id, scope).
    """
    sdk = _load_upstox_client()
    api = sdk.LoginApi(_get_client())
    model_cls = sdk.IndieUserTokenRequest
    body_obj = model_cls(**body) if isinstance(body, dict) else body
    return _call_api(api.init_token_request_for_indie_user,
                     body=body_obj, client_id=client_id, api_version=api_version)


@mcp.tool()
def logout(api_version: str = "v2") -> dict:
    """Revoke the current session."""
    sdk = _load_upstox_client()
    api = sdk.LoginApi(_get_client())
    return _call_api(api.logout, api_version=api_version)


# -------------------------------------------------------------------------
# USER
# -------------------------------------------------------------------------

@mcp.tool()
def get_profile(api_version: str = "v2") -> dict:
    """Fetch the user's profile."""
    sdk = _load_upstox_client()
    api = sdk.UserApi(_get_client())
    return _call_api(api.get_profile, api_version=api_version)


@mcp.tool()
def get_fund_margin(api_version: str = "v2") -> dict:
    """Get available funds and margin details."""
    sdk = _load_upstox_client()
    api = sdk.UserApi(_get_client())
    return _call_api(api.get_user_fund_margin, api_version=api_version)


@mcp.tool()
def get_fund_margin_v3(api_version: str = "v3") -> dict:
    """Get available funds and margin (v3)."""
    sdk = _load_upstox_client()
    api = sdk.UserApi(_get_client())
    return _call_api(api.get_user_fund_margin_v3, api_version=api_version)


# -------------------------------------------------------------------------
# MARKET QUOTES
# -------------------------------------------------------------------------

@mcp.tool()
def get_ltp(instrument_key: str) -> dict:
    """
    Get Last-Traded Price for one or more instruments.
    instrument_key: comma-separated instrument keys, e.g. "NSE_INDEX::2885,NSE_FO::63756"
    """
    sdk = _load_upstox_client()
    api = sdk.MarketQuoteV3Api(_get_client())
    return _call_api(api.get_ltp, instrument_key=instrument_key)


@mcp.tool()
def get_ohlc(instrument_key: str, interval: str = "1minute") -> dict:
    """
    Get OHLC quotes for one or more instruments.
    instrument_key: comma-separated instrument keys.
    interval: one of 1minute, 5minute, 15minute, 30minute, 1hour, 1day.
    """
    sdk = _load_upstox_client()
    api = sdk.MarketQuoteV3Api(_get_client())
    return _call_api(api.get_market_quote_ohlc, interval=interval,
                     instrument_key=instrument_key)


@mcp.tool()
def get_option_greeks(instrument_key: str) -> dict:
    """Get option Greek data (delta, gamma, theta, vega, rho) for instruments."""
    sdk = _load_upstox_client()
    api = sdk.MarketQuoteV3Api(_get_client())
    return _call_api(api.get_market_quote_option_greek, instrument_key=instrument_key)


@mcp.tool()
def get_market_quote_full(instrument_key: str) -> dict:
    """Get full market quote (full depth orderbook) for an instrument."""
    sdk = _load_upstox_client()
    api = sdk.MarketQuoteApi(_get_client())
    return _call_api(api.get_full_market_quote, instrument_key=instrument_key)


@mcp.tool()
def get_market_status(api_version: str = "v2") -> dict:
    """Get current market status (open/closed/pre-open) for all exchanges."""
    sdk = _load_upstox_client()
    api = sdk.MarketApi(_get_client())
    return _call_api(api.get_market_status, api_version=api_version)


@mcp.tool()
def get_market_holidays(api_version: str = "v2") -> dict:
    """Get list of market holidays."""
    sdk = _load_upstox_client()
    api = sdk.MarketHolidaysAndTimingsApi(_get_client())
    return _call_api(api.get_exchange_timing, api_version=api_version)


# -------------------------------------------------------------------------
# INSTRUMENTS
# -------------------------------------------------------------------------

@mcp.tool()
def search_instruments(exchange: str, symbol: str, api_version: str = "v2") -> dict:
    """
    Search for instruments by symbol within an exchange.
    exchange: NSE, BSE, NFO, MCX, BFO, NSE_INDEX, BSE_INDEX
    """
    sdk = _load_upstox_client()
    api = sdk.InstrumentsApi(_get_client())
    return _call_api(api.search_instruments, exchange=exchange, symbol=symbol,
                     api_version=api_version)


@mcp.tool()
def get_instrument_symbol(exchange: str, symbol: str, instrument_type: str = "EQ",
                           expiry: str = "", strike_price: str = "",
                           api_version: str = "v2") -> dict:
    """Get instrument key for a given exchange + symbol combination."""
    sdk = _load_upstox_client()
    api = sdk.InstrumentsApi(_get_client())
    return _call_api(api.get_instrument_symbol, exchange=exchange, symbol=symbol,
                     instrument_type=instrument_type, expiry=expiry,
                     strike_price=strike_price, api_version=api_version)


# -------------------------------------------------------------------------
# OPTIONS
# -------------------------------------------------------------------------

@mcp.tool()
def get_option_chain(instrument_key: str, expiry_date: str = "",
                      strike_price: str = "", right: str = "", limit: int = 10,
                      api_version: str = "v2") -> dict:
    """
    Get option chain for an underlying.
    right: PUT or CALL (optional filter).
    limit: max results per side (default 10).
    """
    sdk = _load_upstox_client()
    api = sdk.OptionsApi(_get_client())
    return _call_api(api.get_option_chain, instrument_key=instrument_key,
                     expiry_date=expiry_date, strike_price=strike_price,
                     right=right, limit=limit, api_version=api_version)


@mcp.tool()
def get_expiries(instrument_key: str, api_version: str = "v2") -> dict:
    """Get available expiry dates for a derivative instrument."""
    sdk = _load_upstox_client()
    api = sdk.ExpiredInstrumentApi(_get_client())
    return _call_api(api.get_expired_futures_contract,
                     instrument_key=instrument_key, api_version=api_version)


# -------------------------------------------------------------------------
# HISTORICAL DATA
# -------------------------------------------------------------------------

@mcp.tool()
def get_historical_candles(instrument_key: str, interval: str, start_time: str,
                             end_time: str, api_version: str = "v3") -> dict:
    """
    Get historical OHLCV candles.
    interval: 1minute, 5minute, 15minute, 30minute, 1hour, 1day.
    start_time / end_time: RFC 3339 / ISO 8601 format, e.g. "2025-01-01T09:15:00Z"
    """
    sdk = _load_upstox_client()
    api = sdk.HistoryV3Api(_get_client())
    return _call_api(api.get_historical_candle, instrument_key=instrument_key,
                     interval=interval, start_time=start_time, end_time=end_time,
                     api_version=api_version)


@mcp.tool()
def get_intra_day_candles(instrument_key: str, interval: str = "1minute",
                           api_version: str = "v3") -> dict:
    """Get intra-day (live) candle data for today."""
    sdk = _load_upstox_client()
    api = sdk.HistoryV3Api(_get_client())
    return _call_api(api.get_intra_day_candle, instrument_key=instrument_key,
                     interval=interval, api_version=api_version)


# -------------------------------------------------------------------------
# ORDERS
# -------------------------------------------------------------------------

@mcp.tool()
def place_order(body: dict, api_version: str = "v2") -> dict:
    """
    Place a new order.
    body: dict with PlaceOrderRequest fields, e.g.:
        {
          "instrument_key": "NSE_FO::12345",
          "quantity": 1,
          "product": "D",
          "order_type": "LIMIT",
          "price": "150.0",
          "transaction_type": "BUY",
          "validity": "IOC",
          "trigger_price": "0"
        }
    """
    sdk = _load_upstox_client()
    api = sdk.OrderApi(_get_client())
    model_cls = sdk.PlaceOrderRequest
    body_obj = model_cls(**body) if isinstance(body, dict) else body
    return _call_api(api.place_order, body=body_obj, api_version=api_version)


@mcp.tool()
def place_order_v3(body: dict) -> dict:
    """Place order using the v3 order API."""
    sdk = _load_upstox_client()
    api = sdk.OrderApiV3(_get_client())
    model_cls = sdk.PlaceOrderV3Request
    body_obj = model_cls(**body) if isinstance(body, dict) else body
    return _call_api(api.place_order, body=body_obj)


@mcp.tool()
def cancel_order(order_id: str, api_version: str = "v2") -> dict:
    """Cancel an open order by order_id."""
    sdk = _load_upstox_client()
    api = sdk.OrderApi(_get_client())
    return _call_api(api.cancel_order, order_id=order_id, api_version=api_version)


@mcp.tool()
def modify_order(body: dict, api_version: str = "v2") -> dict:
    """
    Modify an existing order.
    body: dict with ModifyOrderRequest fields (must include order_id).
    """
    sdk = _load_upstox_client()
    api = sdk.OrderApi(_get_client())
    model_cls = sdk.ModifyOrderRequest
    body_obj = model_cls(**body) if isinstance(body, dict) else body
    return _call_api(api.modify_order, body=body_obj, api_version=api_version)


@mcp.tool()
def get_order_book(api_version: str = "v2") -> dict:
    """Get all orders (open, pending, filled) for today."""
    sdk = _load_upstox_client()
    api = sdk.OrderApi(_get_client())
    return _call_api(api.get_order_book, api_version=api_version)


@mcp.tool()
def get_order_details(order_id: str | None = None, tag: str | None = None,
                      api_version: str = "v2") -> dict:
    """
    Get order history and details.
    Pass order_id for a specific order, or tag to get all orders with that tag.
    """
    sdk = _load_upstox_client()
    api = sdk.OrderApi(_get_client())
    kwargs = {"api_version": api_version}
    if order_id:
        kwargs["order_id"] = order_id
    if tag:
        kwargs["tag"] = tag
    return _call_api(api.get_order_details, **kwargs)


@mcp.tool()
def get_trades(api_version: str = "v2") -> dict:
    """Get all trades executed today."""
    sdk = _load_upstox_client()
    api = sdk.OrderApi(_get_client())
    return _call_api(api.get_trade_history, api_version=api_version)


@mcp.tool()
def get_trades_by_order(order_id: str, api_version: str = "v2") -> dict:
    """Get trades for a specific order."""
    sdk = _load_upstox_client()
    api = sdk.OrderApi(_get_client())
    return _call_api(api.get_trades_by_order, order_id=order_id,
                     api_version=api_version)


# -------------------------------------------------------------------------
# PORTFOLIO
# -------------------------------------------------------------------------

@mcp.tool()
def get_holdings(api_version: str = "v2") -> dict:
    """Get equity holdings (delivery portfolio)."""
    sdk = _load_upstox_client()
    api = sdk.PortfolioApi(_get_client())
    return _call_api(api.get_holdings, api_version=api_version)


@mcp.tool()
def get_positions(api_version: str = "v2") -> dict:
    """Get all open positions (equity + derivatives)."""
    sdk = _load_upstox_client()
    api = sdk.PortfolioApi(_get_client())
    return _call_api(api.get_positions, api_version=api_version)


@mcp.tool()
def convert_position(body: dict, api_version: str = "v2") -> dict:
    """
    Convert a position (e.g. intraday to delivery or vice versa).
    body: dict with ConvertPositionRequest fields.
    """
    sdk = _load_upstox_client()
    api = sdk.PostTradeApi(_get_client())
    model_cls = sdk.ConvertPositionRequest
    body_obj = model_cls(**body) if isinstance(body, dict) else body
    return _call_api(api.convert_position, body=body_obj, api_version=api_version)


@mcp.tool()
def exit_all_positions(tag: str = "", segment: str = "", api_version: str = "v2") -> dict:
    """Square off all open positions."""
    sdk = _load_upstox_client()
    api = sdk.OrderApi(_get_client())
    return _call_api(api.exit_positions, tag=tag, segment=segment,
                     api_version=api_version)


# -------------------------------------------------------------------------
# GTT (Good Till Trigger) ORDERS
# -------------------------------------------------------------------------

@mcp.tool()
def place_gtt_order(body: dict, api_version: str = "v2") -> dict:
    """Place a GTT (trigger) order."""
    sdk = _load_upstox_client()
    api = sdk.OrderApi(_get_client())
    model_cls = sdk.GttPlaceOrderRequest
    body_obj = model_cls(**body) if isinstance(body, dict) else body
    return _call_api(api.place_gtt_order, body=body_obj, api_version=api_version)


@mcp.tool()
def cancel_gtt_order(order_id: str, api_version: str = "v2") -> dict:
    """Cancel a GTT order."""
    sdk = _load_upstox_client()
    api = sdk.OrderApi(_get_client())
    return _call_api(api.cancel_gtt_order, order_id=order_id, api_version=api_version)


@mcp.tool()
def get_gtt_orders(api_version: str = "v2") -> dict:
    """Get all GTT orders."""
    sdk = _load_upstox_client()
    api = sdk.OrderApi(_get_client())
    return _call_api(api.get_gtt_order, api_version=api_version)


# -------------------------------------------------------------------------
# MUTUAL FUNDS
# -------------------------------------------------------------------------

@mcp.tool()
def get_mf_holdings(api_version: str = "v2") -> dict:
    """Get mutual fund holdings."""
    sdk = _load_upstox_client()
    api = sdk.MutualFundApi(_get_client())
    return _call_api(api.get_holdings, api_version=api_version)


@mcp.tool()
def get_mf_orders(api_version: str = "v2") -> dict:
    """Get mutual fund orders."""
    sdk = _load_upstox_client()
    api = sdk.MutualFundApi(_get_client())
    return _call_api(api.get_orders, api_version=api_version)


@mcp.tool()
def get_mf_sips(api_version: str = "v2") -> dict:
    """Get mutual fund SIPs."""
    sdk = _load_upstox_client()
    api = sdk.MutualFundApi(_get_client())
    return _call_api(api.get_sips, api_version=api_version)


# -------------------------------------------------------------------------
# NEWS
# -------------------------------------------------------------------------

@mcp.tool()
def get_news(instrument_key: str = "", api_version: str = "v2") -> dict:
    """Get latest news for an instrument (or all news if instrument_key empty)."""
    sdk = _load_upstox_client()
    api = sdk.NewsApi(_get_client())
    return _call_api(api.get_news, instrument_key=instrument_key,
                     api_version=api_version)


# -------------------------------------------------------------------------
# FUNDAMENTALS
# -------------------------------------------------------------------------

@mcp.tool()
def get_company_profile(instrument_key: str, api_version: str = "v2") -> dict:
    """Get company profile and fundamental data for an instrument."""
    sdk = _load_upstox_client()
    api = sdk.FundamentalsApi(_get_client())
    return _call_api(api.get_company_profile, instrument_key=instrument_key,
                     api_version=api_version)


@mcp.tool()
def get_key_ratios(instrument_key: str, api_version: str = "v2") -> dict:
    """Get key financial ratios for an instrument."""
    sdk = _load_upstox_client()
    api = sdk.FundamentalsApi(_get_client())
    return _call_api(api.get_key_ratios, instrument_key=instrument_key,
                     api_version=api_version)


@mcp.tool()
def get_competitors(instrument_key: str, api_version: str = "v2") -> dict:
    """Get peer competitors for an instrument."""
    sdk = _load_upstox_client()
    api = sdk.FundamentalsApi(_get_client())
    return _call_api(api.get_competitors, instrument_key=instrument_key,
                     api_version=api_version)


# -------------------------------------------------------------------------
# BROKERAGE / CHARGES
# -------------------------------------------------------------------------

@mcp.tool()
def get_brokerage_charges(body: dict, api_version: str = "v2") -> dict:
    """
    Calculate brokerage, taxes, and charges for a proposed trade.
    body: dict matching PlaceOrderRequest fields.
    """
    sdk = _load_upstox_client()
    api = sdk.ChargeApi(_get_client())
    model_cls = sdk.PlaceOrderRequest
    body_obj = model_cls(**body) if isinstance(body, dict) else body
    return _call_api(api.get_brokerage, body=body_obj, api_version=api_version)


# -------------------------------------------------------------------------
# PROFIT & LOSS
# -------------------------------------------------------------------------

@mcp.tool()
def get_trade_profit_and_loss(trade_type: str = "true", api_version: str = "v2") -> dict:
    """Get trade-wise P&L report."""
    sdk = _load_upstox_client()
    api = sdk.TradeProfitAndLossApi(_get_client())
    return _call_api(api.get_trade_wise_profit_and_loss,
                     is_finished=trade_type == "true",
                     api_version=api_version)


@mcp.tool()
def get_pnl_charges(api_version: str = "v2") -> dict:
    """Get profit & loss breakdown including all charges."""
    sdk = _load_upstox_client()
    api = sdk.ChargeApi(_get_client())
    return _call_api(api.get_profit_and_loss_charges, api_version=api_version)


# -------------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    mcp.run()