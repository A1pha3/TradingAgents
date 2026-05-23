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
