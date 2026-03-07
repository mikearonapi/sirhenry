"""Tests for pipeline/utils.py — utility functions."""
import os
import tempfile

import pytest

from pipeline.utils import to_float, strip_json_fences, file_hash


class TestToFloat:
    """to_float() safely converts various inputs to float."""

    def test_none(self):
        assert to_float(None) == 0.0

    def test_empty_string(self):
        assert to_float("") == 0.0

    def test_plain_number(self):
        assert to_float("123.45") == 123.45

    def test_integer(self):
        assert to_float(42) == 42.0

    def test_float_passthrough(self):
        assert to_float(99.9) == 99.9

    def test_dollar_sign(self):
        assert to_float("$1,234.56") == 1234.56

    def test_negative(self):
        assert to_float("-500.00") == -500.0

    def test_negative_with_dollar(self):
        assert to_float("-$1,000") == -1000.0

    def test_whitespace(self):
        assert to_float("  42.5  ") == 42.5

    def test_garbage_returns_zero(self):
        assert to_float("not a number") == 0.0

    def test_nan(self):
        import math
        assert to_float(float("nan")) == 0.0

    def test_zero(self):
        assert to_float("0") == 0.0

    def test_large_number(self):
        assert to_float("$1,000,000.99") == 1_000_000.99


class TestStripJsonFences:
    """strip_json_fences() removes markdown code fences from LLM JSON output."""

    def test_no_fences(self):
        assert strip_json_fences('{"key": "value"}') == '{"key": "value"}'

    def test_json_fences(self):
        raw = '```json\n{"key": "value"}\n```'
        assert strip_json_fences(raw) == '{"key": "value"}'

    def test_bare_fences(self):
        raw = '```\n{"key": "value"}\n```'
        assert strip_json_fences(raw) == '{"key": "value"}'

    def test_whitespace_padding(self):
        raw = '  ```json\n{"key": "value"}\n```  '
        assert strip_json_fences(raw) == '{"key": "value"}'

    def test_empty_string(self):
        assert strip_json_fences("") == ""

    def test_plain_text(self):
        assert strip_json_fences("hello world") == "hello world"


class TestFileHash:
    """file_hash() returns SHA-256 hex digest."""

    def test_known_content(self):
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write(b"hello world")
            path = f.name
        try:
            h = file_hash(path)
            # SHA-256 of "hello world"
            assert h == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        finally:
            os.unlink(path)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            path = f.name
        try:
            h = file_hash(path)
            # SHA-256 of empty content
            assert h == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        finally:
            os.unlink(path)

    def test_consistent(self):
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write(b"test data for hashing")
            path = f.name
        try:
            assert file_hash(path) == file_hash(path)
        finally:
            os.unlink(path)
