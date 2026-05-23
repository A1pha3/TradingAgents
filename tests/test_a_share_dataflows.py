"""Test A-share market-aware vendor routing and AkShare integration."""

import copy
import unittest
from unittest.mock import Mock, patch

import pytest

import tradingagents.default_config as default_config
from tradingagents.dataflows.config import get_config, set_config
from tradingagents.dataflows.interface import (
    get_vendor,
    route_to_vendor,
    detect_market,
)


@pytest.mark.unit
class AShareMarketDetectionTests(unittest.TestCase):
    """Test market detection from ticker symbols."""

    def test_detect_market_cn_a_shanghai(self):
        self.assertEqual(detect_market("600519.SH"), "CN_A")
        self.assertEqual(detect_market("600519.SS"), "CN_A")

    def test_detect_market_cn_a_shenzhen(self):
        self.assertEqual(detect_market("300750.SZ"), "CN_A")

    def test_detect_market_cn_a_beijing(self):
        self.assertEqual(detect_market("830799.BJ"), "CN_A")

    def test_detect_market_non_cn_a(self):
        self.assertIsNone(detect_market("AAPL"))
        self.assertIsNone(detect_market("7203.T"))
        self.assertIsNone(detect_market("0700.HK"))

    def test_detect_market_case_insensitive(self):
        self.assertEqual(detect_market("600519.sh"), "CN_A")
        self.assertEqual(detect_market("300750.sz"), "CN_A")


@pytest.mark.unit
class AShareVendorRoutingTests(unittest.TestCase):
    """Test market-aware vendor routing for A-shares."""

    def setUp(self):
        """Reset config to default before each test."""
        # Force reset of config state to prevent pollution
        from tradingagents.dataflows import config as config_module
        config_module._config = None
        config_module.initialize_config()
        
        base_config = copy.deepcopy(default_config.DEFAULT_CONFIG)
        base_config["market_data_vendors"] = {
            "CN_A": {
                "core_stock_apis": "akshare",
                "technical_indicators": "akshare",
            }
        }
        set_config(base_config)

    def tearDown(self):
        """Restore default config after each test."""
        from tradingagents.dataflows import config as config_module
        config_module._config = None
        config_module.initialize_config()

    def test_get_vendor_cn_a_core_stock_apis(self):
        """A-share symbols route to akshare for core stock APIs."""
        vendor = get_vendor("core_stock_apis", method="get_stock_data", symbol="600519.SH")
        self.assertEqual(vendor, "akshare")

    def test_get_vendor_cn_a_technical_indicators(self):
        """A-share symbols route to akshare for technical indicators."""
        vendor = get_vendor("technical_indicators", method="get_indicators", symbol="300750.SZ")
        self.assertEqual(vendor, "akshare")

    def test_get_vendor_cn_a_fundamentals_not_routed(self):
        """Fundamentals should not route to akshare (not in market_data_vendors)."""
        vendor = get_vendor("fundamental_data", method="get_fundamentals", symbol="600519.SH")
        # Should fall back to data_vendors default (yfinance)
        self.assertEqual(vendor, "yfinance")

    def test_get_vendor_non_cn_a_unchanged(self):
        """Non-A-share symbols should use default vendor."""
        vendor = get_vendor("core_stock_apis", method="get_stock_data", symbol="AAPL")
        self.assertEqual(vendor, "yfinance")

    def test_tool_vendors_override_market_routing(self):
        """Tool-level override should take precedence over market routing."""
        config = get_config()
        config["tool_vendors"]["get_stock_data"] = "yfinance"
        set_config(config)

        vendor = get_vendor("core_stock_apis", method="get_stock_data", symbol="600519.SH")
        # tool_vendors override should win
        self.assertEqual(vendor, "yfinance")

    def test_get_vendor_no_symbol_uses_default(self):
        """When no symbol provided, fall back to category default."""
        vendor = get_vendor("core_stock_apis", method="get_stock_data", symbol=None)
        self.assertEqual(vendor, "yfinance")


@pytest.mark.unit
class AShareRouteToVendorTests(unittest.TestCase):
    """Test route_to_vendor with A-share symbols."""

    def setUp(self):
        """Reset config to default before each test."""
        # Force reset of config state to prevent pollution
        from tradingagents.dataflows import config as config_module
        config_module._config = None
        config_module.initialize_config()
        
        base_config = copy.deepcopy(default_config.DEFAULT_CONFIG)
        base_config["market_data_vendors"] = {
            "CN_A": {
                "core_stock_apis": "akshare",
                "technical_indicators": "akshare",
            }
        }
        set_config(base_config)

    def tearDown(self):
        """Restore default config after each test."""
        from tradingagents.dataflows import config as config_module
        config_module._config = None
        config_module.initialize_config()

    def test_route_to_vendor_dispatches_to_akshare(self):
        """route_to_vendor should dispatch A-share symbols to akshare."""
        from tradingagents.dataflows.interface import VENDOR_METHODS
        
        # Create mock for akshare
        mock_akshare = Mock(return_value=Mock())
        
        # Temporarily replace akshare implementation
        original_impl = VENDOR_METHODS["get_stock_data"]["akshare"]
        VENDOR_METHODS["get_stock_data"]["akshare"] = mock_akshare
        
        try:
            route_to_vendor("get_stock_data", "600519.SH", start_date="2024-01-01", end_date="2024-01-31")
            
            mock_akshare.assert_called_once()
            args = mock_akshare.call_args[0]
            self.assertEqual(args[0], "600519.SH")
        finally:
            # Restore original implementation
            VENDOR_METHODS["get_stock_data"]["akshare"] = original_impl

    def test_route_to_vendor_us_symbol_uses_yfinance(self):
        """Non-A-share symbols should still use yfinance."""
        from tradingagents.dataflows.interface import VENDOR_METHODS
        
        # Create mock for yfinance
        mock_yfinance = Mock(return_value=Mock())
        
        # Temporarily replace yfinance implementation
        original_impl = VENDOR_METHODS["get_stock_data"]["yfinance"]
        VENDOR_METHODS["get_stock_data"]["yfinance"] = mock_yfinance
        
        try:
            route_to_vendor("get_stock_data", "AAPL", start_date="2024-01-01", end_date="2024-01-31")
            
            mock_yfinance.assert_called_once()
        finally:
            # Restore original implementation
            VENDOR_METHODS["get_stock_data"]["yfinance"] = original_impl


@pytest.mark.unit
class AShareConfigTests(unittest.TestCase):
    """Test A-share config structure."""

    def test_default_config_has_market_data_vendors(self):
        """Default config should include market_data_vendors."""
        config = default_config.DEFAULT_CONFIG
        self.assertIn("market_data_vendors", config)
        self.assertIn("CN_A", config["market_data_vendors"])

    def test_benchmark_map_includes_cn_a_suffixes(self):
        """Benchmark map should include A-share exchange suffixes."""
        config = default_config.DEFAULT_CONFIG
        benchmark_map = config["benchmark_map"]
        
        # Check A-share suffixes map to CSI 300
        self.assertEqual(benchmark_map[".SH"], "000300.SS")
        self.assertEqual(benchmark_map[".SS"], "000300.SS")
        self.assertEqual(benchmark_map[".SZ"], "000300.SS")
        self.assertEqual(benchmark_map[".BJ"], "000300.SS")


if __name__ == "__main__":
    unittest.main()
