# Upstox Python SDK — MCP Server

An official [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that wraps the Upstox Python SDK, exposing all trading and market-data APIs as MCP tools.

## Installation

```bash
pip install mcp
# The upstox_client/ SDK is already included in this repository
```

## Configuration

Set environment variables before running the server:

| Variable | Required | Description |
|---|---|---|
| `UPSTOX_API_KEY` | Yes* | Your Upstox API key |
| `UPSTOX_API_SECRET` | Yes* | Your Upstox API secret |
| `UPSTOX_ACCESS_TOKEN` | Alt | Pre-obtained OAuth access token |
| `UPSTOX_SANDBOX` | No | `1` to use sandbox |

## Hermes Agent

```yaml
mcp_servers:
  upstox:
    command: python
    args: ["/path/to/upstox-python/mcp/server.py"]
    env:
      UPSTOX_API_KEY: "your-key"
      UPSTOX_API_SECRET: "your-secret"
```

## Tools

| Category | Tools |
|---|---|
| Auth | `get_authorization_url`, `exchange_token`, `init_indie_user_token`, `logout` |
| User | `get_profile`, `get_fund_margin`, `get_fund_margin_v3` |
| Market Quotes | `get_ltp`, `get_ohlc`, `get_option_greeks`, `get_market_quote_full`, `get_market_status`, `get_market_holidays` |
| Instruments | `search_instruments`, `get_instrument_symbol` |
| Options | `get_option_chain`, `get_expiries` |
| Historical Data | `get_historical_candles`, `get_intra_day_candles` |
| Orders | `place_order`, `place_order_v3`, `cancel_order`, `modify_order`, `get_order_book`, `get_order_details`, `get_trades`, `get_trades_by_order` |
| Portfolio | `get_holdings`, `get_positions`, `convert_position`, `exit_all_positions` |
| GTT Orders | `place_gtt_order`, `cancel_gtt_order`, `get_gtt_orders` |
| Mutual Funds | `get_mf_holdings`, `get_mf_orders`, `get_mf_sips` |
| News | `get_news` |
| Fundamentals | `get_company_profile`, `get_key_ratios`, `get_competitors` |
| Charges | `get_brokerage_charges`, `get_pnl_charges`, `get_trade_profit_and_loss` |

## Quick Start

```bash
UPSTOX_API_KEY=*** UPSTOX_API_SECRET=*** python mcp/server.py
```
