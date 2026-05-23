# A-share Phase 1 Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first shippable slice of A-share support so a market-only A-share run can preserve exchange-qualified tickers, resolve structured market metadata, use AkShare-backed market data, and compute reflection returns without hard-coded `yfinance` logic.

**Architecture:** This plan intentionally implements **Phase 1** from `docs/cn/09-a-share-extension-design.md`, not the full three-phase spec. The slice adds a new `tradingagents.market` boundary for instrument metadata and return resolution, extends `dataflows.interface` with market-aware vendor routing for `CN_A`, and wires CLI / prompt context so the graph can run a market-focused A-share path end-to-end while keeping non-China behavior unchanged.

**Tech Stack:** Python 3.10+, TypedDict state models, pandas, yfinance, akshare, stockstats, pytest, unittest

---

## Scope note

The approved design spans multiple subsystems. This implementation plan covers the first testable slice only:

1. Structured market metadata for A-share tickers
2. AkShare-backed `get_stock_data` / `get_indicators` routing for `CN_A`
3. Benchmark-aware return resolution without `TradingAgentsGraph._fetch_returns()` calling `yfinance` directly
4. CLI-safe A-share ticker normalization and prompt context

This plan does **not** include:

1. Tushare fundamentals
2. China-specific news / announcement normalization
3. Full holiday-aware CN calendar implementation
4. Auto-enabling all analysts for A-share symbols

Those belong in follow-up plans once this slice lands.

## File map

### Create

- `tradingagents/market/__init__.py` — exports the new market-layer helpers
- `tradingagents/market/instrument_profile.py` — resolves ticker → structured market metadata
- `tradingagents/market/return_resolver.py` — resolves benchmark tickers and fetches short-window returns
- `tradingagents/dataflows/akshare.py` — AkShare-backed A-share market data and indicator helpers
- `tests/test_a_share_instrument_profile.py` — unit tests for profile resolution and state initialization
- `tests/test_a_share_dataflows.py` — unit tests for market-aware vendor routing
- `tests/test_a_share_return_resolver.py` — unit tests for benchmark resolution and return calculation

### Modify

- `pyproject.toml` — add `akshare` dependency
- `tradingagents/agents/utils/agent_states.py:1-75` — add `InstrumentProfile` and `instrument_profile` state field
- `tradingagents/graph/propagation.py:18-60` — write `instrument_profile` into the initial state
- `tradingagents/default_config.py:93-121` — add `market_data_vendors` and A-share benchmark suffixes
- `tradingagents/dataflows/interface.py:1-162` — add market-aware vendor selection and AkShare method wiring
- `tradingagents/agents/utils/agent_utils.py:23-52` — add market-context prompt helper and widen suffix hints
- `tradingagents/graph/trading_graph.py:194-293` — replace `_fetch_returns()` internals with `return_resolver`
- `cli/utils.py:15-101` — support guarded expansion of six-digit A-share symbols
- `tests/test_ticker_symbol_handling.py:1-21` — extend ticker tests for `.SH` / `.SZ`

### Validation commands

- `python -m pytest tests/test_a_share_instrument_profile.py -v`
- `python -m pytest tests/test_a_share_dataflows.py -v`
- `python -m pytest tests/test_a_share_return_resolver.py -v`
- `python -m pytest tests/test_ticker_symbol_handling.py -v`
- `python -m pytest tests/ -v`

---

### Task 1: Add structured A-share instrument profiles to graph state

**Files:**
- Create: `tradingagents/market/__init__.py`
- Create: `tradingagents/market/instrument_profile.py`
- Modify: `tradingagents/agents/utils/agent_states.py:1-75`
- Modify: `tradingagents/graph/propagation.py:18-60`
- Test: `tests/test_a_share_instrument_profile.py`

- [ ] **Step 1: Write the failing instrument-profile tests**

```python
import unittest

import pytest

from tradingagents.graph.propagation import Propagator
from tradingagents.market.instrument_profile import resolve_instrument_profile


@pytest.mark.unit
class AShareInstrumentProfileTests(unittest.TestCase):
    def test_resolve_sse_main_board_profile(self):
        profile = resolve_instrument_profile("600519.SH")
        self.assertEqual(profile["market"], "CN_A")
        self.assertEqual(profile["exchange"], "SSE")
        self.assertEqual(profile["board"], "MAIN_BOARD")
        self.assertEqual(profile["currency"], "CNY")
        self.assertEqual(profile["default_benchmark"], "000300.SS")

    def test_resolve_szse_gem_profile(self):
        profile = resolve_instrument_profile("300750.SZ")
        self.assertEqual(profile["market"], "CN_A")
        self.assertEqual(profile["exchange"], "SZSE")
        self.assertEqual(profile["board"], "GEM")

    def test_propagator_includes_instrument_profile(self):
        state = Propagator().create_initial_state("600519.SH", "2026-01-15")
        self.assertIn("instrument_profile", state)
        self.assertEqual(state["instrument_profile"]["ticker"], "600519.SH")
        self.assertEqual(state["instrument_profile"]["market"], "CN_A")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_a_share_instrument_profile.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'tradingagents.market.instrument_profile'`

- [ ] **Step 3: Add the new market-layer module and state fields**

```python
# tradingagents/market/instrument_profile.py
from typing import TypedDict


class InstrumentProfile(TypedDict):
    ticker: str
    market: str
    exchange: str
    board: str
    currency: str
    timezone: str
    calendar: str
    default_benchmark: str
    lot_size: int
    price_limit_rule: str
    supports_fundamentals: bool
    supports_insider_data: str


_A_SHARE_SUFFIXES = {
    ".SH": ("CN_A", "SSE"),
    ".SS": ("CN_A", "SSE"),
    ".SZ": ("CN_A", "SZSE"),
    ".BJ": ("CN_A", "BSE"),
}


def _detect_board(ticker: str, exchange: str) -> str:
    code = ticker.split(".")[0]
    if exchange == "BSE":
        return "BSE"
    if code.startswith("688"):
        return "STAR"
    if code.startswith("300"):
        return "GEM"
    return "MAIN_BOARD"


def resolve_instrument_profile(ticker: str, asset_type: str = "stock") -> InstrumentProfile:
    normalized = ticker.strip().upper()
    for suffix, (market, exchange) in _A_SHARE_SUFFIXES.items():
        if normalized.endswith(suffix):
            board = _detect_board(normalized, exchange)
            return {
                "ticker": normalized,
                "market": market,
                "exchange": exchange,
                "board": board,
                "currency": "CNY",
                "timezone": "Asia/Shanghai",
                "calendar": "CN_BUSINESS_DAY",
                "default_benchmark": "000300.SS",
                "lot_size": 100,
                "price_limit_rule": "20%" if board in {"STAR", "GEM"} else "30%" if board == "BSE" else "10%",
                "supports_fundamentals": asset_type == "stock",
                "supports_insider_data": "partial",
            }

    return {
        "ticker": normalized,
        "market": "GLOBAL",
        "exchange": "",
        "board": "",
        "currency": "USD",
        "timezone": "America/New_York",
        "calendar": "US_BUSINESS_DAY",
        "default_benchmark": "SPY",
        "lot_size": 1,
        "price_limit_rule": "none",
        "supports_fundamentals": asset_type == "stock",
        "supports_insider_data": "partial",
    }
```

```python
# tradingagents/agents/utils/agent_states.py
class AgentState(MessagesState):
    company_of_interest: Annotated[str, "Company that we are interested in trading"]
    asset_type: Annotated[str, "Asset type under analysis such as stock or crypto"]
    trade_date: Annotated[str, "What date we are trading at"]
    instrument_profile: Annotated[dict, "Structured market metadata for the instrument under analysis"]
```

```python
# tradingagents/graph/propagation.py
from tradingagents.market.instrument_profile import resolve_instrument_profile


def create_initial_state(
    self,
    company_name: str,
    trade_date: str,
    asset_type: str = "stock",
    past_context: str = "",
) -> Dict[str, Any]:
    instrument_profile = resolve_instrument_profile(company_name, asset_type=asset_type)
    return {
        "messages": [("human", company_name)],
        "company_of_interest": company_name,
        "asset_type": asset_type,
        "trade_date": str(trade_date),
        "instrument_profile": instrument_profile,
        "past_context": past_context,
        "investment_debate_state": InvestDebateState(
            {
                "bull_history": "",
                "bear_history": "",
                "history": "",
                "current_response": "",
                "judge_decision": "",
                "count": 0,
            }
        ),
        "risk_debate_state": RiskDebateState(
            {
                "aggressive_history": "",
                "conservative_history": "",
                "neutral_history": "",
                "history": "",
                "latest_speaker": "",
                "current_aggressive_response": "",
                "current_conservative_response": "",
                "current_neutral_response": "",
                "judge_decision": "",
                "count": 0,
            }
        ),
        "market_report": "",
        "fundamentals_report": "",
        "sentiment_report": "",
        "news_report": "",
    }
```

- [ ] **Step 4: Export the market helpers**

```python
# tradingagents/market/__init__.py
from .instrument_profile import InstrumentProfile, resolve_instrument_profile

__all__ = ["InstrumentProfile", "resolve_instrument_profile"]
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/test_a_share_instrument_profile.py -v`

Expected: PASS with `3 passed`

- [ ] **Step 6: Commit**

```bash
git add \
  tradingagents/market/__init__.py \
  tradingagents/market/instrument_profile.py \
  tradingagents/agents/utils/agent_states.py \
  tradingagents/graph/propagation.py \
  tests/test_a_share_instrument_profile.py
git commit -m "feat: add A-share instrument profiles"
```

---

### Task 2: Add market-aware vendor routing and AkShare-backed A-share market data

**Files:**
- Modify: `pyproject.toml:11-33`
- Create: `tradingagents/dataflows/akshare.py`
- Modify: `tradingagents/default_config.py:93-121`
- Modify: `tradingagents/dataflows/interface.py:1-162`
- Test: `tests/test_a_share_dataflows.py`

- [ ] **Step 1: Write the failing market-vendor routing tests**

```python
import copy
import unittest
from unittest.mock import patch

import pytest

import tradingagents.default_config as default_config
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.interface import get_vendor, route_to_vendor


@pytest.mark.unit
class AShareVendorRoutingTests(unittest.TestCase):
    def setUp(self):
        cfg = copy.deepcopy(default_config.DEFAULT_CONFIG)
        cfg["market_data_vendors"] = {
            "CN_A": {
                "core_stock_apis": "akshare",
                "technical_indicators": "akshare",
            }
        }
        set_config(cfg)

    def test_cn_a_suffix_uses_market_override(self):
        vendor = get_vendor("core_stock_apis", "get_stock_data", symbol="600519.SH")
        self.assertEqual(vendor, "akshare")

    @patch("tradingagents.dataflows.interface.get_akshare_stock")
    def test_route_to_vendor_dispatches_cn_a_stock_data(self, mock_stock):
        mock_stock.return_value = "ok"
        result = route_to_vendor("get_stock_data", "600519.SH", "2026-01-01", "2026-01-15")
        self.assertEqual(result, "ok")
        mock_stock.assert_called_once()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_a_share_dataflows.py -v`

Expected: FAIL with `KeyError: 'market_data_vendors'` or `AttributeError` for missing AkShare helpers

- [ ] **Step 3: Add the AkShare dependency and new dataflow helper**

```toml
# pyproject.toml
"yfinance>=0.2.63",
"akshare>=1.16.0",
```

```python
# tradingagents/dataflows/akshare.py
from datetime import datetime

import akshare as ak
import pandas as pd
from stockstats import wrap


def _base_symbol(symbol: str) -> str:
    base = symbol.strip().upper().split(".")[0]
    if len(base) != 6 or not base.isdigit():
        raise ValueError(f"AkShare expects a 6-digit China equity code, got {symbol!r}")
    return base


def _load_hist(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    hist = ak.stock_zh_a_hist(
        symbol=_base_symbol(symbol),
        period="daily",
        start_date=start_date.replace("-", ""),
        end_date=end_date.replace("-", ""),
        adjust="qfq",
    )
    if hist.empty:
        return hist
    hist = hist.rename(
        columns={
            "日期": "Date",
            "开盘": "Open",
            "收盘": "Close",
            "最高": "High",
            "最低": "Low",
            "成交量": "Volume",
        }
    )
    hist["Date"] = pd.to_datetime(hist["Date"])
    return hist[["Date", "Open", "High", "Low", "Close", "Volume"]].sort_values("Date")


def get_akshare_stock(
    symbol: str,
    start_date: str,
    end_date: str,
):
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    hist = _load_hist(symbol, start_date, end_date)
    if hist.empty:
        return f"No data found for symbol '{symbol}' between {start_date} and {end_date}"
    return f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n\n" + hist.set_index("Date").round(2).to_csv()


def get_akshare_indicator(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int,
) -> str:
    start_date = (pd.Timestamp(curr_date) - pd.Timedelta(days=look_back_days * 2)).strftime("%Y-%m-%d")
    hist = _load_hist(symbol, start_date, curr_date)
    if hist.empty:
        return f"No data found for indicator '{indicator}' on '{symbol}'"
    stock = wrap(hist.rename(columns=str.lower).copy())
    if indicator not in stock.columns:
        raise ValueError(f"Indicator {indicator} is not available for {symbol}")
    series = stock[indicator].tail(look_back_days)
    return f"# Indicator {indicator} for {symbol}\n\n" + series.to_csv()
```

- [ ] **Step 4: Add market-aware vendor overrides**

```python
# tradingagents/default_config.py
"market_data_vendors": {
    "CN_A": {
        "core_stock_apis": "akshare",
        "technical_indicators": "akshare",
    }
},
"benchmark_map": {
    ".SH": "000300.SS",
    ".SS": "000300.SS",
    ".SZ": "000300.SS",
    ".BJ": "000300.SS",
    ".NS": "^NSEI",
    ".BO": "^BSESN",
    ".T": "^N225",
    ".HK": "^HSI",
    ".L": "^FTSE",
    ".TO": "^GSPTSE",
    ".AX": "^AXJO",
    "": "SPY",
}
```

```python
# tradingagents/dataflows/interface.py
from .akshare import get_akshare_indicator, get_akshare_stock


def detect_market(symbol: str | None) -> str | None:
    if not symbol:
        return None
    ticker = str(symbol).upper()
    if ticker.endswith((".SH", ".SS", ".SZ", ".BJ")):
        return "CN_A"
    return None


def get_vendor(category: str, method: str = None, symbol: str | None = None) -> str:
    config = get_config()
    market = detect_market(symbol)
    if market:
        market_overrides = config.get("market_data_vendors", {}).get(market, {})
        if method and method in config.get("tool_vendors", {}):
            return config["tool_vendors"][method]
        if category in market_overrides:
            return market_overrides[category]
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]
    return config.get("data_vendors", {}).get(category, "default")


VENDOR_LIST = [
    "yfinance",
    "alpha_vantage",
    "akshare",
]


VENDOR_METHODS = {
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
        "akshare": get_akshare_stock,
    },
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
        "akshare": get_akshare_indicator,
    },
    "get_fundamentals": {
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
    },
    "get_news": {
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
    },
    "get_global_news": {
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
    },
}


def route_to_vendor(method: str, *args, **kwargs):
    category = get_category_for_method(method)
    symbol = args[0] if args else kwargs.get("symbol")
    vendor_config = get_vendor(category, method, symbol=symbol)
    primary_vendors = [v.strip() for v in vendor_config.split(",")]
    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")
    all_available_vendors = list(VENDOR_METHODS[method].keys())
    fallback_vendors = primary_vendors.copy()
    for vendor in all_available_vendors:
        if vendor not in fallback_vendors:
            fallback_vendors.append(vendor)
    for vendor in fallback_vendors:
        if vendor not in VENDOR_METHODS[method]:
            continue
        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl
        try:
            return impl_func(*args, **kwargs)
        except AlphaVantageRateLimitError:
            continue
    raise RuntimeError(f"No available vendor for '{method}'")
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/test_a_share_dataflows.py -v`

Expected: PASS with `2 passed`

- [ ] **Step 6: Commit**

```bash
git add \
  pyproject.toml \
  tradingagents/dataflows/akshare.py \
  tradingagents/default_config.py \
  tradingagents/dataflows/interface.py \
  tests/test_a_share_dataflows.py
git commit -m "feat: add market-aware A-share dataflow routing"
```

---

### Task 3: Replace hard-coded `yfinance` return fetching with a reusable return resolver

**Files:**
- Create: `tradingagents/market/return_resolver.py`
- Modify: `tradingagents/graph/trading_graph.py:194-293`
- Test: `tests/test_a_share_return_resolver.py`

- [ ] **Step 1: Write the failing return-resolver tests**

```python
import unittest
from unittest.mock import patch

import pandas as pd
import pytest

from tradingagents.market.instrument_profile import resolve_instrument_profile
from tradingagents.market.return_resolver import (
    fetch_returns,
    resolve_benchmark_ticker,
)


@pytest.mark.unit
class AShareReturnResolverTests(unittest.TestCase):
    def test_resolve_benchmark_for_cn_a_profile(self):
        profile = resolve_instrument_profile("600519.SH")
        self.assertEqual(resolve_benchmark_ticker(profile, None), "000300.SS")

    @patch("tradingagents.market.return_resolver.fetch_close_series")
    def test_fetch_returns_uses_cn_profile_and_requested_holding_days(self, mock_series):
        mock_series.side_effect = [
            pd.Series([10.0, 10.5, 11.0], index=pd.to_datetime(["2026-01-15", "2026-01-16", "2026-01-19"])),
            pd.Series([4.0, 4.1, 4.2], index=pd.to_datetime(["2026-01-15", "2026-01-16", "2026-01-19"])),
        ]
        profile = resolve_instrument_profile("600519.SH")
        raw, alpha, days = fetch_returns(profile, "2026-01-15", holding_days=2)
        self.assertAlmostEqual(raw, 0.1)
        self.assertAlmostEqual(alpha, 0.05)
        self.assertEqual(days, 2)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_a_share_return_resolver.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'tradingagents.market.return_resolver'`

- [ ] **Step 3: Implement the reusable return resolver**

```python
# tradingagents/market/return_resolver.py
from datetime import datetime, timedelta
from typing import Optional, Tuple

import pandas as pd
import yfinance as yf

from tradingagents.dataflows.akshare import _load_hist


def resolve_benchmark_ticker(profile: dict, explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    return profile.get("default_benchmark", "SPY")


def fetch_close_series(ticker: str, start_date: str, end_date: str) -> pd.Series:
    if ticker.upper().endswith((".SH", ".SS", ".SZ", ".BJ")):
        hist = _load_hist(ticker, start_date, end_date)
        if hist.empty:
            return pd.Series(dtype=float)
        return hist.set_index("Date")["Close"].astype(float)

    series = yf.Ticker(ticker).history(start=start_date, end=end_date)["Close"]
    if series.empty:
        return pd.Series(dtype=float)
    if getattr(series.index, "tz", None) is not None:
        series.index = series.index.tz_localize(None)
    return series.astype(float)


def fetch_returns(
    profile: dict,
    trade_date: str,
    holding_days: int = 5,
    benchmark: Optional[str] = None,
) -> Tuple[Optional[float], Optional[float], Optional[int]]:
    start = datetime.strptime(trade_date, "%Y-%m-%d")
    end = (start + timedelta(days=holding_days + 10)).strftime("%Y-%m-%d")
    benchmark_ticker = resolve_benchmark_ticker(profile, benchmark)
    stock = fetch_close_series(profile["ticker"], trade_date, end)
    bench = fetch_close_series(benchmark_ticker, trade_date, end)
    if len(stock) < 2 or len(bench) < 2:
        return None, None, None
    actual_days = min(holding_days, len(stock) - 1, len(bench) - 1)
    raw = float((stock.iloc[actual_days] - stock.iloc[0]) / stock.iloc[0])
    bench_ret = float((bench.iloc[actual_days] - bench.iloc[0]) / bench.iloc[0])
    return raw, raw - bench_ret, actual_days
```

- [ ] **Step 4: Wire `TradingAgentsGraph` into the new resolver**

```python
# tradingagents/graph/trading_graph.py
from tradingagents.market.instrument_profile import resolve_instrument_profile
from tradingagents.market.return_resolver import fetch_returns, resolve_benchmark_ticker


def _resolve_benchmark(self, ticker: str) -> str:
    profile = resolve_instrument_profile(ticker)
    return resolve_benchmark_ticker(profile, self.config.get("benchmark_ticker"))


def _fetch_returns(
    self, ticker: str, trade_date: str, holding_days: int = 5,
    benchmark: str = "SPY",
) -> Tuple[Optional[float], Optional[float], Optional[int]]:
    profile = resolve_instrument_profile(ticker)
    return fetch_returns(profile, trade_date, holding_days=holding_days, benchmark=benchmark)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/test_a_share_return_resolver.py -v`

Expected: PASS with `2 passed`

- [ ] **Step 6: Commit**

```bash
git add \
  tradingagents/market/return_resolver.py \
  tradingagents/graph/trading_graph.py \
  tests/test_a_share_return_resolver.py
git commit -m "refactor: resolve A-share returns through market layer"
```

---

### Task 4: Guard A-share ticker input in the CLI and enrich agent context

**Files:**
- Modify: `cli/utils.py:15-101`
- Modify: `tradingagents/agents/utils/agent_utils.py:23-52`
- Modify: `tests/test_ticker_symbol_handling.py:1-21`
- Test: `tests/test_ticker_symbol_handling.py`

- [ ] **Step 1: Extend the failing ticker tests**

```python
import unittest

import pytest

from cli.utils import expand_a_share_ticker, normalize_ticker_symbol
from tradingagents.agents.utils.agent_utils import build_instrument_context, build_market_context
from tradingagents.market.instrument_profile import resolve_instrument_profile


@pytest.mark.unit
class TickerSymbolHandlingTests(unittest.TestCase):
    def test_normalize_ticker_symbol_preserves_exchange_suffix(self):
        self.assertEqual(normalize_ticker_symbol(" cnc.to "), "CNC.TO")

    def test_expand_a_share_ticker_requires_explicit_exchange(self):
        with self.assertRaises(ValueError):
            expand_a_share_ticker("600519")

    def test_expand_a_share_ticker_appends_requested_exchange(self):
        self.assertEqual(expand_a_share_ticker("600519", "SH"), "600519.SH")

    def test_build_market_context_mentions_cn_a_rules(self):
        profile = resolve_instrument_profile("600519.SH")
        context = build_market_context(profile)
        self.assertIn("China A-share market", context)
        self.assertIn("price limits", context)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_ticker_symbol_handling.py -v`

Expected: FAIL with `ImportError: cannot import name 'expand_a_share_ticker'`

- [ ] **Step 3: Add guarded ticker expansion to the CLI**

```python
# cli/utils.py
TICKER_INPUT_EXAMPLES = "Examples: SPY, CNC.TO, 7203.T, 0700.HK, 600519.SH, 000001.SZ"


def expand_a_share_ticker(ticker: str, exchange: str | None = None) -> str:
    normalized = normalize_ticker_symbol(ticker)
    if "." in normalized or len(normalized) != 6 or not normalized.isdigit():
        return normalized
    if exchange is None:
        raise ValueError("6-digit China tickers require an explicit exchange such as SH, SZ, or BJ")
    return f"{normalized}.{exchange.strip().upper()}"
```

- [ ] **Step 4: Add a shared market-context helper**

```python
# tradingagents/agents/utils/agent_utils.py
def build_market_context(profile: dict) -> str:
    if profile.get("market") != "CN_A":
        return ""
    return (
        " This instrument trades in the China A-share market. "
        "Use CNY as the reporting currency, preserve the exact exchange-qualified ticker, "
        "account for board-specific price limits, and do not assume US-style insider transaction datasets exist."
    )


def build_instrument_context(ticker: str, asset_type: str = "stock", instrument_profile: dict | None = None) -> str:
    instrument_label = "asset" if asset_type == "crypto" else "instrument"
    extra_hint = (
        " Treat it as a crypto asset rather than a company, and do not assume company fundamentals are available."
        if asset_type == "crypto"
        else ""
    )
    market_context = build_market_context(instrument_profile or {})
    return (
        f"The {instrument_label} to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`, `.SH`, `.SZ`, `-USD`)."
        + extra_hint
        + market_context
    )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/test_ticker_symbol_handling.py -v`

Expected: PASS with `4 passed`

- [ ] **Step 6: Commit**

```bash
git add \
  cli/utils.py \
  tradingagents/agents/utils/agent_utils.py \
  tests/test_ticker_symbol_handling.py
git commit -m "feat: guard A-share ticker input and market context"
```

---

### Task 5: Run the Phase 1 regression set and sync the docs

**Files:**
- Modify: `docs/cn/05-extension-guide.md`
- Modify: `docs/cn/09-a-share-extension-design.md`
- Test: `tests/test_a_share_instrument_profile.py`
- Test: `tests/test_a_share_dataflows.py`
- Test: `tests/test_a_share_return_resolver.py`
- Test: `tests/test_ticker_symbol_handling.py`

- [ ] **Step 1: Add the new developer guidance**

```markdown
## A 股 Phase 1 落地说明

当前仓库的 A 股第一阶段支持包含 4 个落点：

1. `tradingagents.market.instrument_profile` 负责把 `600519.SH` 这类 ticker 解析成结构化市场画像。
2. `dataflows.interface` 会对 `.SH/.SS/.SZ/.BJ` 走 `market_data_vendors["CN_A"]` 覆盖。
3. `tradingagents.market.return_resolver` 接管反思层的 benchmark 和收益解析。
4. CLI 只会在用户显式选择交易所时补全 6 位 A 股代码，不会静默猜后缀。
```

- [ ] **Step 2: Run the focused regression set**

Run:

```bash
python -m pytest \
  tests/test_a_share_instrument_profile.py \
  tests/test_a_share_dataflows.py \
  tests/test_a_share_return_resolver.py \
  tests/test_ticker_symbol_handling.py -v
```

Expected: PASS with all four files green

- [ ] **Step 3: Run the full repository test suite**

Run: `python -m pytest tests/ -v`

Expected: PASS with existing tests plus the new A-share coverage

- [ ] **Step 4: Commit**

```bash
git add \
  docs/cn/05-extension-guide.md \
  docs/cn/09-a-share-extension-design.md \
  tests/test_a_share_instrument_profile.py \
  tests/test_a_share_dataflows.py \
  tests/test_a_share_return_resolver.py \
  tests/test_ticker_symbol_handling.py
git commit -m "docs: document phase 1 A-share implementation"
```

---

## Self-review notes

### Spec coverage

- `instrument_profile` → Task 1
- AkShare A-share market path → Task 2
- benchmark / return resolver → Task 3
- CLI contract + prompt context → Task 4
- tests + docs sync → Task 5

### Placeholder scan

- No unfinished placeholder markers remain
- Each task names exact files and exact commands
- Each code step includes concrete code to write, not just descriptions

### Type / naming consistency

- The plan consistently uses `InstrumentProfile`, `resolve_instrument_profile`, `resolve_benchmark_ticker`, `fetch_returns`, `expand_a_share_ticker`, and `build_market_context`
- The plan scopes this slice to **Phase 1** so it does not claim to deliver Tushare fundamentals or holiday-accurate CN calendars yet
