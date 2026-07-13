"""Tests for the analyst tool-loop routers in ConditionalLogic.

The four ``should_continue_{market,social,news,fundamentals}`` routers are the
per-analyst conditional edges that decide whether the analyst re-enters its
tool node (more data to fetch) or clears messages and moves on (analysis
done). They were the only ConditionalLogic routers without direct tests --
``test_risk_router_path_map`` covers the debate/risk routers only.

Each router reads ``state["messages"][-1].tool_calls``: a non-empty list routes
to the tool node, anything falsy routes to the clear node. These tests pin that
contract and cross-check the returned labels against ``AnalystNodeSpec`` so a
node rename in one place but not the other is caught (#1088-style drift).
"""

import pytest

from tradingagents.graph.analyst_execution import ANALYST_NODE_SPECS
from tradingagents.graph.conditional_logic import ConditionalLogic


class _FakeMessage:
    """Minimal stand-in for a LangChain message: only ``tool_calls`` is read."""

    def __init__(self, tool_calls):
        self.tool_calls = tool_calls


def _state(tool_calls, *, prior=None):
    messages = list(prior or [])
    messages.append(_FakeMessage(tool_calls))
    return {"messages": messages}


@pytest.mark.unit
@pytest.mark.parametrize("key", list(ANALYST_NODE_SPECS))
def test_routes_to_tool_node_when_tool_calls_present(key):
    spec = ANALYST_NODE_SPECS[key]
    logic = ConditionalLogic()
    router = getattr(logic, f"should_continue_{key}")
    state = _state([{"name": "get_stock_data", "args": {}, "id": "call_1"}])
    assert router(state) == spec.tool_node


@pytest.mark.unit
@pytest.mark.parametrize("key", list(ANALYST_NODE_SPECS))
def test_routes_to_clear_node_when_no_tool_calls(key):
    spec = ANALYST_NODE_SPECS[key]
    logic = ConditionalLogic()
    router = getattr(logic, f"should_continue_{key}")
    # Empty list: the analyst has no pending tool calls -> move on.
    assert router(_state([])) == spec.clear_node


@pytest.mark.unit
@pytest.mark.parametrize("key", list(ANALYST_NODE_SPECS))
def test_routes_to_clear_node_when_tool_calls_is_none(key):
    spec = ANALYST_NODE_SPECS[key]
    logic = ConditionalLogic()
    router = getattr(logic, f"should_continue_{key}")
    # None is falsy: defensive against providers that omit tool_calls.
    assert router(_state(None)) == spec.clear_node


@pytest.mark.unit
@pytest.mark.parametrize("key", list(ANALYST_NODE_SPECS))
def test_router_only_inspects_last_message(key):
    spec = ANALYST_NODE_SPECS[key]
    logic = ConditionalLogic()
    router = getattr(logic, f"should_continue_{key}")
    # An earlier message with tool calls must not direct the router; only the
    # trailing message matters (the router indexes messages[-1]).
    prior = _FakeMessage([{"name": "earlier", "args": {}, "id": "1"}])
    assert router(_state([], prior=[prior])) == spec.clear_node

    prior_done = _FakeMessage([])
    state_active = _state(
        [{"name": "now", "args": {}, "id": "2"}], prior=[prior_done]
    )
    assert router(state_active) == spec.tool_node


@pytest.mark.unit
@pytest.mark.parametrize("key", list(ANALYST_NODE_SPECS))
def test_router_labels_are_routable_in_setup(key):
    """Setup wires each router with ``[tool_node, clear_node]`` only; the
    router must never return a label outside that set or LangGraph crashes
    mid-run (#1088)."""
    spec = ANALYST_NODE_SPECS[key]
    logic = ConditionalLogic()
    router = getattr(logic, f"should_continue_{key}")
    routable = {spec.tool_node, spec.clear_node}
    assert router(_state([{"name": "x", "args": {}, "id": "1"}])) in routable
    assert router(_state([])) in routable
    assert router(_state(None)) in routable


@pytest.mark.unit
def test_social_router_keeps_legacy_method_name():
    """The wire key is 'social' (saved-config back-compat) even though the
    clear label is 'Msg Clear Sentiment'. The router method must exist under
    the legacy name so setup's ``getattr(should_continue_social)`` resolves."""
    logic = ConditionalLogic()
    assert hasattr(logic, "should_continue_social")
    spec = ANALYST_NODE_SPECS["social"]
    assert logic.should_continue_social(_state([])) == spec.clear_node
    assert spec.clear_node == "Msg Clear Sentiment"


@pytest.mark.unit
def test_debate_depth_does_not_affect_analyst_routers():
    """Analyst routers are tool-loop gates, not debate counters; debate depth
    config must not change their behaviour."""
    logic = ConditionalLogic(max_debate_rounds=7, max_risk_discuss_rounds=9)
    assert logic.should_continue_market(
        _state([{"name": "x", "args": {}, "id": "1"}])
    ) == "tools_market"
    assert logic.should_continue_news(_state([])) == "Msg Clear News"
