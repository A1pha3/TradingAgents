"""AkShare-backed data providers for China A-share markets."""

from datetime import datetime

import pandas as pd
from stockstats import wrap


_INDICATOR_DESCRIPTIONS = {
    "close_50_sma": (
        "50 SMA: A medium-term trend indicator. "
        "Usage: Identify trend direction and serve as dynamic support/resistance. "
        "Tips: It lags price; combine with faster indicators for timely signals."
    ),
    "close_200_sma": (
        "200 SMA: A long-term trend benchmark. "
        "Usage: Confirm overall market trend and identify golden/death cross setups. "
        "Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries."
    ),
    "close_10_ema": (
        "10 EMA: A responsive short-term average. "
        "Usage: Capture quick shifts in momentum and potential entry points. "
        "Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals."
    ),
    "macd": (
        "MACD: Computes momentum via differences of EMAs. "
        "Usage: Look for crossovers and divergence as signals of trend changes. "
        "Tips: Confirm with other indicators in low-volatility or sideways markets."
    ),
    "macds": (
        "MACD Signal: An EMA smoothing of the MACD line. "
        "Usage: Use crossovers with the MACD line to trigger trades. "
        "Tips: Should be part of a broader strategy to avoid false positives."
    ),
    "macdh": (
        "MACD Histogram: Shows the gap between the MACD line and its signal. "
        "Usage: Visualize momentum strength and spot divergence early. "
        "Tips: Can be volatile; complement with additional filters in fast-moving markets."
    ),
    "rsi": (
        "RSI: Measures momentum to flag overbought/oversold conditions. "
        "Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. "
        "Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis."
    ),
    "boll": (
        "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. "
        "Usage: Acts as a dynamic benchmark for price movement. "
        "Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals."
    ),
    "boll_ub": (
        "Bollinger Upper Band: Typically 2 standard deviations above the middle line. "
        "Usage: Signals potential overbought conditions and breakout zones. "
        "Tips: Confirm signals with other tools; prices may ride the band in strong trends."
    ),
    "boll_lb": (
        "Bollinger Lower Band: Typically 2 standard deviations below the middle line. "
        "Usage: Indicates potential oversold conditions. "
        "Tips: Use additional analysis to avoid false reversal signals."
    ),
    "atr": (
        "ATR: Averages true range to measure volatility. "
        "Usage: Set stop-loss levels and adjust position sizes based on current market volatility. "
        "Tips: It's a reactive measure, so use it as part of a broader risk management strategy."
    ),
    "vwma": (
        "VWMA: A moving average weighted by volume. "
        "Usage: Confirm trends by integrating price action with volume data. "
        "Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses."
    ),
    "mfi": (
        "MFI: The Money Flow Index is a momentum indicator that uses both price and volume to measure buying and selling pressure. "
        "Usage: Identify overbought (>80) or oversold (<20) conditions and confirm the strength of trends or reversals. "
        "Tips: Use alongside RSI or MACD to confirm signals; divergence between price and MFI can indicate potential reversals."
    ),
}


def _import_akshare():
    try:
        import akshare as ak
    except ImportError as exc:
        raise ImportError(
            "AkShare is not installed. Install it with: pip install akshare"
        ) from exc
    return ak


def _validate_date(date_str: str) -> str:
    datetime.strptime(date_str, "%Y-%m-%d")
    return date_str


def _base_symbol(ticker: str) -> str:
    normalized = ticker.strip().upper()
    parts = normalized.split(".")
    if len(parts) != 2 or len(parts[0]) != 6 or not parts[0].isdigit():
        raise ValueError(
            f"AkShare expects a 6-digit A-share ticker with exchange suffix, got {ticker!r}"
        )
    return parts[0]


def _load_hist(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    ak = _import_akshare()
    hist = ak.stock_zh_a_hist(
        symbol=_base_symbol(ticker),
        period="daily",
        start_date=_validate_date(start_date).replace("-", ""),
        end_date=_validate_date(end_date).replace("-", ""),
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
    hist = hist[["Date", "Open", "High", "Low", "Close", "Volume"]].copy()
    hist["Date"] = pd.to_datetime(hist["Date"])
    return hist.sort_values("Date")


def get_stock_data(ticker: str, start_date: str, end_date: str) -> str:
    """Retrieve OHLCV stock data for A-share tickers using AkShare."""
    hist = _load_hist(ticker, start_date, end_date)
    if hist.empty:
        return f"No data found for symbol '{ticker}' between {start_date} and {end_date}"

    csv_string = hist.set_index("Date").round(2).to_csv()
    header = f"# Stock data for {ticker.upper()} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(hist)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + csv_string


def get_indicators(
    ticker: str,
    indicator: str,
    curr_date: str,
    look_back_days: int,
) -> str:
    """Retrieve a single technical indicator for an A-share ticker."""
    indicator = indicator.lower()
    if indicator not in _INDICATOR_DESCRIPTIONS:
        raise ValueError(
            f"Indicator {indicator} is not supported. Please choose from: {list(_INDICATOR_DESCRIPTIONS.keys())}"
        )

    curr_date_dt = pd.Timestamp(_validate_date(curr_date))
    start_date = (curr_date_dt - pd.Timedelta(days=look_back_days * 3)).strftime(
        "%Y-%m-%d"
    )
    hist = _load_hist(ticker, start_date, curr_date)
    if hist.empty:
        return f"No data found for indicator '{indicator}' on '{ticker}'"

    stock = wrap(hist.copy())
    stock["Date"] = stock["Date"].dt.strftime("%Y-%m-%d")
    stock[indicator]

    before = curr_date_dt - pd.Timedelta(days=look_back_days)
    date_values = []
    current_dt = curr_date_dt
    while current_dt >= before:
        date_str = current_dt.strftime("%Y-%m-%d")
        matching_rows = stock[stock["Date"] == date_str]
        if matching_rows.empty:
            indicator_value = "N/A: Not a trading day (weekend or holiday)"
        else:
            value = matching_rows.iloc[0][indicator]
            indicator_value = "N/A" if pd.isna(value) else str(value)
        date_values.append((date_str, indicator_value))
        current_dt -= pd.Timedelta(days=1)

    indicator_lines = "".join(f"{date}: {value}\n" for date, value in date_values)
    return (
        f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
        + indicator_lines
        + "\n\n"
        + _INDICATOR_DESCRIPTIONS[indicator]
    )
