"""AkShare-backed data providers for China A-share markets."""

import pandas as pd
from datetime import datetime


def get_stock_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Retrieve OHLCV stock data for A-share tickers using AkShare.

    Args:
        ticker: Stock symbol with exchange suffix (e.g., "600519.SH", "300750.SZ")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        DataFrame with columns: Date, Open, High, Low, Close, Volume
    """
    try:
        import akshare as ak
    except ImportError as e:
        raise ImportError(
            "AkShare is not installed. Install it with: pip install akshare"
        ) from e

    # Remove exchange suffix for AkShare (expects raw ticker like "600519")
    symbol = ticker.split(".")[0]

    try:
        # AkShare stock_zh_a_hist returns daily historical data
        # symbol: stock code (e.g., "600519")
        # period: "daily" for daily data
        # start_date/end_date: YYYYMMDD format
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",  # qfq = forward-adjusted for dividends/splits
        )

        if df is None or df.empty:
            return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])

        # AkShare columns (Chinese): 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
        # Map to English column names matching interface expectation
        df = df.rename(columns={
            "日期": "Date",
            "开盘": "Open",
            "收盘": "Close",
            "最高": "High",
            "最低": "Low",
            "成交量": "Volume",
        })

        # Select only needed columns
        df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]

        # Ensure Date is datetime
        df["Date"] = pd.to_datetime(df["Date"])

        return df

    except Exception as e:
        raise RuntimeError(f"Failed to fetch A-share data for {ticker}: {e}") from e


def get_indicators(ticker: str, start_date: str, end_date: str, indicator: str) -> pd.DataFrame:
    """
    Retrieve technical indicators for A-share tickers.

    For A-shares, we compute indicators from raw OHLCV data using stockstats.

    Args:
        ticker: Stock symbol with exchange suffix
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        indicator: Indicator name (e.g., "rsi", "macd", "boll")

    Returns:
        DataFrame with date index and indicator columns
    """
    # Fetch OHLCV data first
    df = get_stock_data(ticker, start_date, end_date)

    if df.empty:
        return pd.DataFrame()

    # Use stockstats_utils to compute indicators (same as yfinance backend)
    from .stockstats_utils import add_stockstats_indicators

    df_with_indicators = add_stockstats_indicators(df, [indicator])

    return df_with_indicators
