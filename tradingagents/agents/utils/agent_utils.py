from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import (
    get_stock_data
)
from tradingagents.agents.utils.technical_indicators_tools import (
    get_indicators
)
from tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement
)
from tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news
)
from tradingagents.market.instrument_profile import (
    resolve_instrument_profile,
    InstrumentProfile,
)


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Applied to every agent whose output reaches the saved report —
    analysts, researchers, debaters, research manager, trader, and
    portfolio manager — so a non-English run produces a fully localized
    report rather than a mix of languages.
    """
    from tradingagents.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    return f" Write your entire response in {lang}."


def build_market_context(profile: InstrumentProfile) -> str:
    """Build market-specific context guidance for the given instrument profile.
    
    Args:
        profile: InstrumentProfile dict with market, exchange, currency, etc.
        
    Returns:
        Market context string to be included in agent prompts, or empty string
        if no special guidance is needed.
        
    Examples:
        For CN_A market:
        - Mentions China A-share market, CNY currency, exchange-qualified tickers
        - Notes board-specific price limits (10% Main Board, 20% STAR/GEM, 30% BSE)
        - Clarifies that insider trading data may be incomplete
        - Warns not to assume US-style disclosure requirements
    """
    market = profile.get("market", "GLOBAL")
    
    if market == "CN_A":
        exchange = profile.get("exchange", "")
        board = profile.get("board", "")
        price_limit = profile.get("price_limit_rule", "10%")
        
        board_desc = {
            "MAIN_BOARD": "Main Board",
            "STAR": "STAR Market (Science and Technology Innovation Board)",
            "GEM": "GEM (Growth Enterprise Market)",
            "BSE": "Beijing Stock Exchange",
        }.get(board, board)
        
        return (
            f"This is a China A-share market instrument trading in CNY on the {exchange} "
            f"({board_desc}). A-share tickers must include the exchange suffix (e.g., `.SH`, `.SZ`, `.BJ`). "
            f"Price limits: {price_limit} daily movement restriction. "
            f"Insider trading disclosures may be incomplete or delayed compared to US markets; "
            f"do not assume the same level of transparency. "
            f"Fundamental data is available but may be reported on different schedules than Western markets."
        )
    
    return ""


def build_instrument_context(
    ticker: str,
    asset_type: str = "stock",
    instrument_profile: InstrumentProfile = None,
) -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers.
    
    Args:
        ticker: The ticker symbol (e.g., "600519.SH", "SPY", "BTC-USD")
        asset_type: "stock" or "crypto"
        instrument_profile: Optional pre-resolved InstrumentProfile. If not provided,
            the function will resolve it internally for stock assets.
            
    Returns:
        A context string describing the instrument, including market-specific guidance
        when applicable (e.g., for A-share stocks).
        
    Examples:
        >>> ctx = build_instrument_context("600519.SH")
        >>> "China A-share" in ctx
        True
        >>> "price limit" in ctx.lower()
        True
    """
    instrument_label = "asset" if asset_type == "crypto" else "instrument"
    extra_hint = (
        " Treat it as a crypto asset rather than a company, and do not assume company fundamentals are available."
        if asset_type == "crypto"
        else ""
    )
    
    base_context = (
        f"The {instrument_label} to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`, `-USD`)."
        + extra_hint
    )
    
    # Add market context for stock assets
    if asset_type == "stock":
        if instrument_profile is None:
            instrument_profile = resolve_instrument_profile(ticker, asset_type)
        
        market_ctx = build_market_context(instrument_profile)
        if market_ctx:
            base_context += " " + market_ctx
    
    return base_context

def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


        
