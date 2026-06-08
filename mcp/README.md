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

## Swagger UI / API Reference

The Upstox API endpoints can be explored interactively via Swagger UI:

- **Market Data**: `https://api.upstox.com/v2/market-quote/ohlc`
- **Historical Candles**: `https://api.upstox.com/v3/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}`
- **Option Chain**: `https://api.upstox.com/v2/option/chain`

### Valid Parameter Values

| Parameter | Valid Values | Notes |
|---|---|---|
| OHLC `interval` | `1` (min), `5`, `15`, `30`, `60` (hour), `D` (day) | Numeric = minutes |
| Historical `interval` | `1`–`60` (minutes) or `1` with `unit=days` | Integer, not string |
| Historical `unit` | `"minutes"`, `"days"` | Separate from interval |
| Historical dates | `yyyy-mm-dd` | Not ISO 8601 — truncate before passing to SDK |
| Financial Year | `"2025-2026"` | Full 4-digit year format, NOT `"2025-26"` |

### Known Issues

These tools make correctly-formed API calls, but reject values that can only be determined from the Upstox API documentation:

- **`get_ohlc`**: Interval validation is server-side. Tried `"1"` through `"1min"` — all rejected with error code `UDAPI1028`. The correct interval format is undocumented in the SDK. Check the [Upstox API docs](https://upstox.com/developer/api-documentation) for valid values.
- **`get_pnl_charges`** / **`get_trade_profit_and_loss`**: Financial year validation is server-side. Tried `"2025-2026"`, `"FY2026"`, `"2025-26"` — all rejected with error code `UDAPI1074`. The correct format may depend on your account type or may require a specific FY identifier from the API.

- **OHLC interval**: Use V2 API. Valid values: `"1min"`, `"5min"`, `"15min"`, `"30min"`, `"1hour"`, `"1day"`. Numeric values like `"1"` or `"D"` are rejected by the API server.
- **Historical candles**: The SDK's `get_historical_candle_data1` takes `interval` as **int** (minutes), not a string like `"1day"`. Dates must be `yyyy-mm-dd` format (truncate ISO 8601).
- **Financial year**: The Upstox API is strict about format. Try `"2025-2026"` first; if that fails, try `"FY2026"` or `"2025"`. The exact format may depend on your account type.
- **Option chain**: `expiry_date` is required — pass a valid date from `get_expiries` first. Past expiries return empty data.
- **api_version**: Most SDK methods with `**kwargs` reject `api_version` as a keyword arg. The MCP server auto-strips it when the method doesn't explicitly declare it.
- **GTT orders**: Not supported in this SDK version (2.23.0). The tools return a helpful error message.
