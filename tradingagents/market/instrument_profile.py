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
