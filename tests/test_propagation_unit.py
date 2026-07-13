"""Tests for Propagator state initialization and graph args.

Covers create_initial_state structure (debate states, asset_type, instrument
context) and get_graph_args with/without callbacks — the callbacks branch was
uncovered (propagation.py 67%).
"""

import pytest

from tradingagents.graph.propagation import Propagator


@pytest.mark.unit
class TestCreateInitialState:
    def test_initializes_debate_states_empty(self):
        state = Propagator().create_initial_state("AAPL", "2024-05-10")
        ids = state["investment_debate_state"]
        assert ids["count"] == 0
        assert ids["current_response"] == ""
        assert ids["bull_history"] == ""
        assert ids["bear_history"] == ""
        rds = state["risk_debate_state"]
        assert rds["count"] == 0
        assert rds["latest_speaker"] == ""
        assert rds["aggressive_history"] == ""
        assert rds["current_aggressive_response"] == ""

    def test_threads_company_date_asset(self):
        state = Propagator().create_initial_state(
            "BTC-USD", "2024-05-10", asset_type="crypto"
        )
        assert state["company_of_interest"] == "BTC-USD"
        assert state["trade_date"] == "2024-05-10"
        assert state["asset_type"] == "crypto"

    def test_includes_past_and_instrument_context(self):
        state = Propagator().create_initial_state(
            "AAPL", "2024-05-10",
            past_context="prior run lessons",
            instrument_context="The instrument to analyze is `AAPL`. ...",
        )
        assert state["past_context"] == "prior run lessons"
        assert state["instrument_context"] == "The instrument to analyze is `AAPL`. ..."

    def test_defaults_for_empty_contexts(self):
        state = Propagator().create_initial_state("AAPL", "2024-05-10")
        assert state["past_context"] == ""
        assert state["instrument_context"] == ""

    def test_reports_initialized_empty(self):
        state = Propagator().create_initial_state("AAPL", "2024-05-10")
        for key in ("market_report", "sentiment_report", "news_report", "fundamentals_report"):
            assert state[key] == ""

    def test_trade_date_coerced_to_string(self):
        state = Propagator().create_initial_state("AAPL", 20240510)
        assert state["trade_date"] == "20240510"
        assert isinstance(state["trade_date"], str)

    def test_messages_seed_with_company_name(self):
        state = Propagator().create_initial_state("AAPL", "2024-05-10")
        assert state["messages"][0] == ("human", "AAPL")


@pytest.mark.unit
class TestGetGraphArgs:
    def test_default_args_without_callbacks(self):
        args = Propagator().get_graph_args()
        assert args["stream_mode"] == "values"
        assert args["config"]["recursion_limit"] == 100

    def test_custom_recursion_limit(self):
        args = Propagator(max_recur_limit=250).get_graph_args()
        assert args["config"]["recursion_limit"] == 250

    def test_callbacks_included_when_provided(self):
        # Covers the callbacks branch.
        cb = [object()]
        args = Propagator().get_graph_args(callbacks=cb)
        assert args["config"]["callbacks"] is cb

    def test_callbacks_omitted_when_none(self):
        args = Propagator().get_graph_args(callbacks=None)
        assert "callbacks" not in args["config"]

    def test_callbacks_omitted_when_empty_list(self):
        # An empty list is falsy -> callbacks key not added.
        args = Propagator().get_graph_args(callbacks=[])
        assert "callbacks" not in args["config"]
