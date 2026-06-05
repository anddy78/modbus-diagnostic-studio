"""Unit tests for parse_coil_values and parse_register_values helpers.

No GUI, no hardware — pure function tests.
"""

from __future__ import annotations

import pytest

from modbus_diagnostic_studio.gui.tabs.advanced_master_tab import (
    parse_coil_values,
    parse_register_values,
)


# ── parse_coil_values ────────────────────────────────────────────────────────


class TestParseCoilValues:
    def test_ones_and_zeros_comma(self) -> None:
        assert parse_coil_values("1,0,1") == [True, False, True]

    def test_ones_and_zeros_space(self) -> None:
        assert parse_coil_values("1 0 1 0") == [True, False, True, False]

    def test_true_false_lower(self) -> None:
        assert parse_coil_values("true false true") == [True, False, True]

    def test_true_false_upper(self) -> None:
        assert parse_coil_values("TRUE FALSE") == [True, False]

    def test_mixed_separator(self) -> None:
        assert parse_coil_values("1, 0, true, false") == [True, False, True, False]

    def test_single_true(self) -> None:
        assert parse_coil_values("true") == [True]

    def test_single_false(self) -> None:
        assert parse_coil_values("0") == [False]

    def test_single_one(self) -> None:
        assert parse_coil_values("1") == [True]

    def test_all_true(self) -> None:
        assert parse_coil_values("1 1 1 1 1 1 1 1") == [True] * 8

    def test_all_false(self) -> None:
        assert parse_coil_values("0 0 0") == [False] * 3

    def test_invalid_token_raises(self) -> None:
        with pytest.raises(ValueError, match="token"):
            parse_coil_values("1, yes, 0")

    def test_on_off_rejected(self) -> None:
        with pytest.raises(ValueError, match="token"):
            parse_coil_values("on off")

    def test_integer_2_rejected(self) -> None:
        with pytest.raises(ValueError, match="token"):
            parse_coil_values("1 2 0")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="No coil values"):
            parse_coil_values("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="No coil values"):
            parse_coil_values("   ")


# ── parse_register_values ────────────────────────────────────────────────────


class TestParseRegisterValues:
    def test_decimal_single(self) -> None:
        assert parse_register_values("100") == [100]

    def test_decimal_multiple_comma(self) -> None:
        assert parse_register_values("100,200,300") == [100, 200, 300]

    def test_decimal_multiple_space(self) -> None:
        assert parse_register_values("10 20 30") == [10, 20, 30]

    def test_hex_prefix_lower(self) -> None:
        assert parse_register_values("0x0001") == [1]

    def test_hex_prefix_upper(self) -> None:
        assert parse_register_values("0xFF00") == [0xFF00]

    def test_mixed_decimal_and_hex(self) -> None:
        assert parse_register_values("100, 0x0064") == [100, 100]

    def test_zero_value(self) -> None:
        assert parse_register_values("0") == [0]

    def test_max_value(self) -> None:
        assert parse_register_values("65535") == [65535]

    def test_max_hex(self) -> None:
        assert parse_register_values("0xFFFF") == [0xFFFF]

    def test_mixed_separator(self) -> None:
        assert parse_register_values("1, 2, 3") == [1, 2, 3]

    def test_value_out_of_range_positive_raises(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            parse_register_values("65536")

    def test_value_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            parse_register_values("-1")

    def test_hex_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            parse_register_values("0x10000")

    def test_invalid_text_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid register value"):
            parse_register_values("abc")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="No register values"):
            parse_register_values("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="No register values"):
            parse_register_values("   ")

    def test_hex_value_0x_prefix_only_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid register value"):
            parse_register_values("0x")
