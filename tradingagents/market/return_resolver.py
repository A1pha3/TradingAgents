"""Market-layer return resolver for multi-vendor position return tracking.

This module provides reusable functions to:
1. Resolve benchmark tickers based on instrument profiles
2. Fetch close price series from the appropriate data vendor (yfinance or AkShare)
3. Calculate raw returns and alpha vs benchmark for a given holding period

Design:
- For A-share tickers (.SH/.SS/.SZ/.BJ), use AkShare via the existing _load_hist loader
- For non-A-share tickers, use yfinance
- Respect explicit benchmark overrides from config
- Return (None, None, None) for missing/unavailable data
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

import pandas as pd
import yfinance as yf

from tradingagents.market.instrument_profile import InstrumentProfile
from tradingagents.dataflows.akshare import _load_hist

logger = logging.getLogger(__name__)


def resolve_benchmark_ticker(
    profile: InstrumentProfile,
    explicit_benchmark: Optional[str],
) -> str:
    """Resolve the benchmark ticker for alpha calculation.

    Args:
        profile: The instrument profile containing default_benchmark
        explicit_benchmark: Optional explicit benchmark from config (overrides profile)

    Returns:
        The benchmark ticker symbol to use
    """
    if explicit_benchmark:
        return explicit_benchmark
    return profile["default_benchmark"]


def fetch_close_series(
    ticker: str,
    start_date: str,
    end_date: str,
) -> pd.Series:
    """Fetch close price series for a ticker from the appropriate vendor.

    Routes A-share tickers (.SH/.SS/.SZ/.BJ) to AkShare, others to yfinance.

    Args:
        ticker: Ticker symbol (normalized, e.g., "600519.SH" or "AAPL")
        start_date: Start date string in "YYYY-MM-DD" format
        end_date: End date string in "YYYY-MM-DD" format

    Returns:
        Series of close prices indexed by date, or empty Series on error
    """
    try:
        ticker_upper = ticker.upper()
        # Route A-share tickers to AkShare
        if any(ticker_upper.endswith(suffix) for suffix in [".SH", ".SS", ".SZ", ".BJ"]):
            hist = _load_hist(ticker, start_date, end_date)
            if hist.empty:
                return pd.Series()
            # _load_hist returns DataFrame with Date column; set as index
            return hist.set_index("Date")["Close"]
        else:
            # Route non-A-share tickers to yfinance
            hist = yf.Ticker(ticker).history(start=start_date, end=end_date)
            if hist.empty:
                return pd.Series()
            return hist["Close"]
    except Exception as e:
        logger.warning("Failed to fetch close series for %s: %s", ticker, e)
        return pd.Series()


def fetch_returns(
    profile: InstrumentProfile,
    trade_date: str,
    holding_days: int = 5,
    explicit_benchmark: Optional[str] = None,
) -> Tuple[Optional[float], Optional[float], Optional[int]]:
    """Fetch raw and alpha return for a ticker over holding_days from trade_date.

    This is the main entry point for return calculation. It:
    1. Resolves the benchmark ticker based on profile and config
    2. Fetches close series for both stock and benchmark
    3. Calculates raw return and alpha

    Args:
        profile: Instrument profile for the ticker
        trade_date: Trade entry date in "YYYY-MM-DD" format
        holding_days: Target holding period in days
        explicit_benchmark: Optional explicit benchmark from config

    Returns:
        Tuple of (raw_return, alpha_return, actual_holding_days) or (None, None, None)
        if data is unavailable
    """
    try:
        ticker = profile["ticker"]
        benchmark = resolve_benchmark_ticker(profile, explicit_benchmark)

        # Calculate end date with buffer for weekends/holidays
        start = datetime.strptime(trade_date, "%Y-%m-%d")
        end = start + timedelta(days=holding_days + 7)
        end_str = end.strftime("%Y-%m-%d")

        # Fetch close series
        stock_series = fetch_close_series(ticker, trade_date, end_str)
        bench_series = fetch_close_series(benchmark, trade_date, end_str)

        # Validate sufficient data
        if len(stock_series) < 2 or len(bench_series) < 2:
            return None, None, None

        # Calculate actual holding days (capped by available data)
        actual_days = min(holding_days, len(stock_series) - 1, len(bench_series) - 1)

        # Calculate returns
        raw_return = float(
            (stock_series.iloc[actual_days] - stock_series.iloc[0]) / stock_series.iloc[0]
        )
        bench_return = float(
            (bench_series.iloc[actual_days] - bench_series.iloc[0]) / bench_series.iloc[0]
        )
        alpha_return = raw_return - bench_return

        return raw_return, alpha_return, actual_days

    except Exception as e:
        logger.warning(
            "Could not resolve outcome for %s on %s vs %s: %s",
            profile["ticker"],
            trade_date,
            explicit_benchmark or profile["default_benchmark"],
            e,
        )
        return None, None, None
