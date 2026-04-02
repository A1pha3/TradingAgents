# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TradingAgents is a multi-agent LLM financial trading framework. It orchestrates a pipeline of specialized AI agents (analysts, researchers, traders, risk managers) to produce trading decisions for a given stock and date. Built on LangGraph for graph orchestration and LangChain for LLM abstraction.

## Build & Run Commands

```bash
# Install (editable)
pip install -e .

# Run CLI
tradingagents

# Run single analysis via Python API
python main.py

# Run tests
python -m pytest tests/
python -m unittest tests.test_model_validation
python -m unittest tests.test_ticker_symbol_handling
```

## Architecture

### Agent Pipeline (execution order)

```
Analysts (parallel-ish, sequential in graph) → Researchers (debate) → Research Manager → Trader → Risk Analysts (debate) → Portfolio Manager
```

1. **Analysts** gather data using tools, each producing a report:
   - Market Analyst (technical: OHLCV, indicators)
   - Social Media Analyst (sentiment)
   - News Analyst (news, global news, insider transactions)
   - Fundamentals Analyst (financials, balance sheet, cashflow, income statement)

2. **Research Team** — Bull and Bear Researchers debate, Research Manager synthesizes into `investment_plan`

3. **Trader** creates `trader_investment_plan`

4. **Risk Management** — Aggressive, Conservative, Neutral analysts debate risk, Portfolio Manager issues `final_trade_decision`

### Key Files

- `tradingagents/graph/trading_graph.py` — Main orchestrator (`TradingAgentsGraph`), entry point for running the pipeline
- `tradingagents/graph/setup.py` — LangGraph `StateGraph` construction and edge wiring
- `tradingagents/graph/conditional_logic.py` — Conditional routing (debate rounds, tool loops)
- `tradingagents/agents/utils/agent_states.py` — `AgentState`, `InvestDebateState`, `RiskDebateState` type definitions
- `tradingagents/agents/utils/memory.py` — `FinancialSituationMemory` for reflection
- `tradingagents/default_config.py` — All default configuration values

### Data Flow

- `tradingagents/dataflows/interface.py` — Routes tool calls to vendor implementations (yfinance or Alpha Vantage) with fallback support
- Vendor routing: `tool_vendors` (per-tool) overrides `data_vendors` (per-category). Comma-separated vendor strings create fallback chains.
- Tools are organized into categories: `core_stock_apis`, `technical_indicators`, `fundamental_data`, `news_data`

### LLM Client System

- `tradingagents/llm_clients/factory.py` — `create_llm_client()` factory dispatches to provider-specific clients
- Supports: OpenAI, Anthropic, Google, xAI, OpenRouter, Ollama
- Two LLM levels: `deep_think_llm` (complex reasoning) and `quick_think_llm` (fast tasks)
- Provider-specific kwargs: `google_thinking_level`, `openai_reasoning_effort`, `anthropic_effort`

### Configuration

Config dict passed to `TradingAgentsGraph(config=...)`. Key fields:
- `llm_provider`, `deep_think_llm`, `quick_think_llm`, `backend_url`
- `max_debate_rounds`, `max_risk_discuss_rounds` — control debate iteration
- `data_vendors` / `tool_vendors` — data source selection
- `output_language` — language for analyst reports and final decision (debates stay English)
- `results_dir` — output directory (env override: `TRADINGAGENTS_RESULTS_DIR`)

### CLI

- `cli/main.py` — Rich terminal UI using Typer, with interactive ticker/date/LLM provider selection
- Entry point registered as `tradingagents` console script

## Important Patterns

- All agents are factory functions (`create_*_analyst`, `create_*_researcher`, etc.) returning LangGraph-compatible callables
- Analysts use `ToolNode` for data fetching with a conditional loop (agent → tools → agent until done → next analyst)
- Debate agents pass `InvestDebateState` / `RiskDebateState` through the graph state, with round counting for termination
- State is logged to `eval_results/{ticker}/TradingAgentsStrategy_logs/` as JSON
- Reflection (`reflect_and_remember`) updates per-agent memories after receiving position returns
