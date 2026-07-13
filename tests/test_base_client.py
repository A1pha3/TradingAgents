"""Tests for the base LLM client.

Covers ``normalize_content`` (list-of-blocks -> string extraction) and the
``BaseLLMClient`` helpers (``get_provider_name`` fallback, ``warn_if_unknown_model``).
The normalize_content body and the abstract-method concrete behavior were
uncovered (base_client.py 76%).
"""

import warnings
from unittest.mock import MagicMock

import pytest

from tradingagents.llm_clients.base_client import BaseLLMClient, normalize_content


class _Resp:
    def __init__(self, content):
        self.content = content


@pytest.mark.unit
class TestNormalizeContent:
    def test_string_content_unchanged(self):
        r = normalize_content(_Resp("hello"))
        assert r.content == "hello"

    def test_list_of_text_blocks_joined(self):
        r = normalize_content(_Resp([
            {"type": "text", "text": "first"},
            {"type": "text", "text": "second"},
        ]))
        assert r.content == "first\nsecond"

    def test_reasoning_blocks_discarded(self):
        r = normalize_content(_Resp([
            {"type": "reasoning", "text": "hidden"},
            {"type": "text", "text": "visible"},
        ]))
        assert r.content == "visible"

    def test_list_of_plain_strings_joined(self):
        r = normalize_content(_Resp(["a", "b", "c"]))
        assert r.content == "a\nb\nc"

    def test_empty_text_items_dropped(self):
        r = normalize_content(_Resp([
            {"type": "text", "text": ""},
            {"type": "text", "text": "kept"},
        ]))
        assert r.content == "kept"

    def test_mixed_block_types(self):
        r = normalize_content(_Resp([
            {"type": "text", "text": "t"},
            {"type": "reasoning"},  # dict but not text
            "plain",
            123,  # neither dict nor str -> ""
        ]))
        assert r.content == "t\nplain"

    def test_empty_list_yields_empty_string(self):
        r = normalize_content(_Resp([]))
        assert r.content == ""

    def test_returns_same_response_object(self):
        resp = _Resp("x")
        assert normalize_content(resp) is resp


class _Client(BaseLLMClient):
    def get_llm(self):
        return "llm"

    def validate_model(self):
        return True


class _ClientWithProvider(BaseLLMClient):
    provider = "deepseek"

    def get_llm(self):
        return "llm"

    def validate_model(self):
        return True


class _InvalidModelClient(BaseLLMClient):
    provider = "test"

    def get_llm(self):
        return "llm"

    def validate_model(self):
        return False


@pytest.mark.unit
class TestBaseLLMClient:
    def test_init_stores_model_base_url_kwargs(self):
        c = _Client("gpt-4", base_url="http://x", extra="kw")
        assert c.model == "gpt-4"
        assert c.base_url == "http://x"
        assert c.kwargs == {"extra": "kw"}

    def test_base_url_defaults_none(self):
        c = _Client("gpt-4")
        assert c.base_url is None
        assert c.kwargs == {}

    def test_get_provider_name_uses_provider_attr(self):
        c = _ClientWithProvider("m")
        assert c.get_provider_name() == "deepseek"

    def test_get_provider_name_falls_back_to_class_name(self):
        # No `provider` attr -> class name minus "Client", lowercased.
        c = _Client("m")
        assert c.get_provider_name() == "_"  # "_Client" -> removesuffix("Client") -> "_"

    def test_warn_if_unknown_model_silent_when_valid(self):
        c = _ClientWithProvider("m")
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # any warning -> failure
            c.warn_if_unknown_model()

    def test_warn_if_unknown_model_warns_when_invalid(self):
        c = _InvalidModelClient("mystery-model")
        with pytest.warns(RuntimeWarning, match="not in the known model list"):
            c.warn_if_unknown_model()

    def test_cannot_instantiate_abstract_directly(self):
        with pytest.raises(TypeError):
            BaseLLMClient("m")  # abstract methods get_llm/validate_model
