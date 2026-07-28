# Copyright (c) Opendatalab. All rights reserved.
"""DOCX 编号处理单元测试。

覆盖以下模块：
- mineru.model.docx.docx_converter.DocxConverter._format_number_by_numfmt
- mineru.model.docx.docx_converter.DocxConverter._to_roman / _to_letter / _to_chinese_number 等
- mineru.model.docx.docx_converter.DocxConverter._is_numbered_list
- mineru.model.docx.docx_converter.DocxConverter._advance_list_counter
- mineru.model.docx.docx_converter.DocxConverter._get_numbering_level_start
- mineru.backend.office.mkcontent.output_builders.format_ordered_number
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

# ── 编号格式化函数测试（纯逻辑，无依赖） ─────────────────────────


class TestFormatNumberByNumfmt:
    """DocxConverter._format_number_by_numfmt 及相关静态方法测试。"""

    def _make_converter(self):
        """Create a minimal DocxConverter instance for testing formatting methods."""
        from mineru.model.docx.docx_converter import DocxConverter
        conv = MagicMock(spec=DocxConverter)
        # Bind static methods
        conv._format_number_by_numfmt = DocxConverter._format_number_by_numfmt.__get__(conv, DocxConverter)
        conv._to_roman = staticmethod(DocxConverter._to_roman).__get__(conv, DocxConverter)
        conv._to_letter = staticmethod(DocxConverter._to_letter).__get__(conv, DocxConverter)
        conv._to_chinese_number = staticmethod(DocxConverter._to_chinese_number).__get__(conv, DocxConverter)
        conv._to_chinese_upper_number = staticmethod(DocxConverter._to_chinese_upper_number).__get__(conv, DocxConverter)
        conv._to_enclosed_circle = staticmethod(DocxConverter._to_enclosed_circle).__get__(conv, DocxConverter)
        conv._to_japanese_kana = staticmethod(DocxConverter._to_japanese_kana).__get__(conv, DocxConverter)
        conv._to_greek_letter = staticmethod(DocxConverter._to_greek_letter).__get__(conv, DocxConverter)
        return conv

    def test_decimal(self):
        conv = self._make_converter()
        assert conv._format_number_by_numfmt(1, "decimal") == "1"
        assert conv._format_number_by_numfmt(5, "decimal") == "5"
        assert conv._format_number_by_numfmt(10, "decimal") == "10"

    def test_decimal_zero(self):
        conv = self._make_converter()
        assert conv._format_number_by_numfmt(1, "decimalZero") == "1"

    def test_lower_roman(self):
        conv = self._make_converter()
        assert conv._format_number_by_numfmt(1, "lowerRoman") == "i"
        assert conv._format_number_by_numfmt(4, "lowerRoman") == "iv"
        assert conv._format_number_by_numfmt(9, "lowerRoman") == "ix"
        assert conv._format_number_by_numfmt(10, "lowerRoman") == "x"
        assert conv._format_number_by_numfmt(49, "lowerRoman") == "xlix"
        assert conv._format_number_by_numfmt(100, "lowerRoman") == "c"

    def test_upper_roman(self):
        conv = self._make_converter()
        assert conv._format_number_by_numfmt(1, "upperRoman") == "I"
        assert conv._format_number_by_numfmt(4, "upperRoman") == "IV"
        assert conv._format_number_by_numfmt(9, "upperRoman") == "IX"
        assert conv._format_number_by_numfmt(10, "upperRoman") == "X"

    def test_lower_letter(self):
        conv = self._make_converter()
        assert conv._format_number_by_numfmt(1, "lowerLetter") == "a"
        assert conv._format_number_by_numfmt(2, "lowerLetter") == "b"
        assert conv._format_number_by_numfmt(26, "lowerLetter") == "z"
        assert conv._format_number_by_numfmt(27, "lowerLetter") == "aa"
        assert conv._format_number_by_numfmt(28, "lowerLetter") == "ab"

    def test_upper_letter(self):
        conv = self._make_converter()
        assert conv._format_number_by_numfmt(1, "upperLetter") == "A"
        assert conv._format_number_by_numfmt(2, "upperLetter") == "B"
        assert conv._format_number_by_numfmt(26, "upperLetter") == "Z"
        assert conv._format_number_by_numfmt(27, "upperLetter") == "AA"

    def test_chinese_counting(self):
        conv = self._make_converter()
        assert conv._format_number_by_numfmt(1, "chineseCounting") == "一"
        assert conv._format_number_by_numfmt(2, "chineseCounting") == "二"
        assert conv._format_number_by_numfmt(3, "chineseCounting") == "三"
        assert conv._format_number_by_numfmt(10, "chineseCounting") == "十"
        assert conv._format_number_by_numfmt(11, "chineseCounting") == "十一"
        assert conv._format_number_by_numfmt(20, "chineseCounting") == "二十"
        assert conv._format_number_by_numfmt(50, "chineseCounting") == "五十"

    def test_chinese_counting_thousand(self):
        conv = self._make_converter()
        assert conv._format_number_by_numfmt(1, "chineseCountingThousand") == "壹"
        assert conv._format_number_by_numfmt(2, "chineseCountingThousand") == "贰"
        assert conv._format_number_by_numfmt(10, "chineseCountingThousand") == "拾"

    def test_enclosed_circle(self):
        conv = self._make_converter()
        assert conv._format_number_by_numfmt(1, "decimalEnclosedCircle") == "①"
        assert conv._format_number_by_numfmt(2, "decimalEnclosedCircle") == "②"
        assert conv._format_number_by_numfmt(10, "decimalEnclosedCircle") == "⑩"
        assert conv._format_number_by_numfmt(20, "decimalEnclosedCircle") == "⑳"
        assert conv._format_number_by_numfmt(21, "decimalEnclosedCircle") == "21"

    def test_japanese_kana_aiueo(self):
        conv = self._make_converter()
        assert conv._format_number_by_numfmt(1, "aiueo") == "あ"
        assert conv._format_number_by_numfmt(2, "aiueo") == "い"
        assert conv._format_number_by_numfmt(3, "aiueo") == "う"

    def test_japanese_kana_iroha(self):
        conv = self._make_converter()
        assert conv._format_number_by_numfmt(1, "iroha") == "い"
        assert conv._format_number_by_numfmt(2, "iroha") == "ろ"
        assert conv._format_number_by_numfmt(3, "iroha") == "は"

    def test_greek_letter(self):
        conv = self._make_converter()
        assert conv._format_number_by_numfmt(1, "lowerGreek") == "α"
        assert conv._format_number_by_numfmt(2, "lowerGreek") == "β"
        assert conv._format_number_by_numfmt(24, "lowerGreek") == "ω"

    def test_unknown_numfmt_fallback(self):
        conv = self._make_converter()
        assert conv._format_number_by_numfmt(5, "unknown_format") == "5"


class TestFormatOrderedNumber:
    """output_builders.format_ordered_number 测试。"""

    def test_decimal(self):
        from mineru.backend.office.mkcontent.output_builders import format_ordered_number
        assert format_ordered_number(1, "decimal") == "1"
        assert format_ordered_number(10, "decimal") == "10"

    def test_chinese_counting(self):
        from mineru.backend.office.mkcontent.output_builders import format_ordered_number
        assert format_ordered_number(1, "chineseCounting") == "一"
        assert format_ordered_number(3, "chineseCounting") == "三"

    def test_lower_roman(self):
        from mineru.backend.office.mkcontent.output_builders import format_ordered_number
        assert format_ordered_number(4, "lowerRoman") == "iv"

    def test_upper_letter(self):
        from mineru.backend.office.mkcontent.output_builders import format_ordered_number
        assert format_ordered_number(1, "upperLetter") == "A"
        assert format_ordered_number(26, "upperLetter") == "Z"

    def test_enclosed_circle(self):
        from mineru.backend.office.mkcontent.output_builders import format_ordered_number
        assert format_ordered_number(1, "decimalEnclosedCircle") == "①"

    def test_unknown_fallback(self):
        from mineru.backend.office.mkcontent.output_builders import format_ordered_number
        assert format_ordered_number(5, "nonexistent") == "5"


# ── _is_numbered_list 测试 ────────────────────────────────


class MockXmlElement:
    """Simplified mock for lxml element used in numbering tests."""

    def __init__(self, tag: str, attrib: dict = None, text: str = None):
        self.tag = tag
        self.attrib = attrib or {}
        self.text = text
        self._children = []

    def find(self, xpath, namespaces=None):
        """Simple xpath-like lookup (only supports .//tag or tag)."""
        # Strip namespace prefixes for simplicity
        for child in self._children:
            simple_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if simple_tag in xpath:
                return child
        return None

    def findall(self, xpath, namespaces=None):
        return [c for c in self._children]

    def get(self, key, default=None):
        # Handle namespace-prefixed keys
        simple_key = key.split("}")[-1] if "}" in key else key
        return self.attrib.get(simple_key, default)


def make_mock_lvl_element(numFmt_val: str, lvlText_val: str = "%1."):
    """Create a mock <w:lvl> element with numFmt and lvlText children."""
    numFmt = MockXmlElement("w:numFmt", {"val": numFmt_val})
    lvlText = MockXmlElement("w:lvlText", {"val": lvlText_val})
    lvl = MockXmlElement("w:lvl", {"ilvl": "0"})
    lvl._children = [numFmt, lvlText]
    return lvl


class TestIsNumberedList:
    """DocxConverter._is_numbered_list 测试。"""

    @pytest.fixture
    def converter(self):
        from mineru.model.docx.docx_converter import DocxConverter
        conv = MagicMock(spec=DocxConverter)
        conv._get_numbering_level_definition = MagicMock()
        conv._is_numbered_list = DocxConverter._is_numbered_list.__get__(conv, DocxConverter)
        return conv

    def test_decimal_is_numbered(self, converter):
        converter._get_numbering_level_definition.return_value = make_mock_lvl_element("decimal")
        assert converter._is_numbered_list(1, 0) is True

    def test_chinese_counting_is_numbered(self, converter):
        converter._get_numbering_level_definition.return_value = make_mock_lvl_element("chineseCounting")
        assert converter._is_numbered_list(1, 0) is True

    def test_lower_roman_is_numbered(self, converter):
        converter._get_numbering_level_definition.return_value = make_mock_lvl_element("lowerRoman")
        assert converter._is_numbered_list(1, 0) is True

    def test_upper_letter_is_numbered(self, converter):
        converter._get_numbering_level_definition.return_value = make_mock_lvl_element("upperLetter")
        assert converter._is_numbered_list(1, 0) is True

    def test_bullet_is_not_numbered(self, converter):
        converter._get_numbering_level_definition.return_value = make_mock_lvl_element("bullet")
        assert converter._is_numbered_list(1, 0) is False

    def test_none_lvl_element_returns_false(self, converter):
        converter._get_numbering_level_definition.return_value = None
        assert converter._is_numbered_list(1, 0) is False

    def test_decimal_enclosed_circle_is_numbered(self, converter):
        converter._get_numbering_level_definition.return_value = make_mock_lvl_element("decimalEnclosedCircle")
        assert converter._is_numbered_list(1, 0) is True

    def test_ordinal_is_numbered(self, converter):
        converter._get_numbering_level_definition.return_value = make_mock_lvl_element("ordinal")
        assert converter._is_numbered_list(1, 0) is True


# ── _advance_list_counter 测试 ────────────────────────────


class TestAdvanceListCounter:
    """DocxConverter._advance_list_counter 测试。"""

    @pytest.fixture
    def converter(self):
        from mineru.model.docx.docx_converter import DocxConverter
        conv = MagicMock(spec=DocxConverter)
        conv.list_counters = {}
        conv._get_numbering_level_start = MagicMock(return_value=1)
        conv._advance_list_counter = DocxConverter._advance_list_counter.__get__(conv, DocxConverter)
        return conv

    def test_first_call_returns_start(self, converter):
        assert converter._advance_list_counter(1, 0) == 1

    def test_second_call_increments(self, converter):
        converter._advance_list_counter(1, 0)
        assert converter._advance_list_counter(1, 0) == 2

    def test_third_call_increments_again(self, converter):
        converter._advance_list_counter(1, 0)
        converter._advance_list_counter(1, 0)
        assert converter._advance_list_counter(1, 0) == 3

    def test_different_numid_separate_counters(self, converter):
        assert converter._advance_list_counter(1, 0) == 1
        assert converter._advance_list_counter(2, 0) == 1
        assert converter._advance_list_counter(1, 0) == 2

    def test_child_counter_reset_on_parent_advance(self, converter):
        converter._advance_list_counter(1, 0)  # parent at 1
        converter._advance_list_counter(1, 1)  # child at 1
        converter._advance_list_counter(1, 0)  # parent advances to 2, child should be deleted
        # Child should reset to start value
        assert converter._advance_list_counter(1, 1) == 1

    def test_custom_start_value(self, converter):
        converter._get_numbering_level_start.return_value = 3
        assert converter._advance_list_counter(1, 0) == 3


# ── _get_numbering_level_start 测试 ───────────────────────


class TestGetNumberingLevelStart:
    """DocxConverter._get_numbering_level_start 测试。"""

    @pytest.fixture
    def converter(self):
        from mineru.model.docx.docx_converter import DocxConverter
        conv = MagicMock(spec=DocxConverter)
        conv._numbering_start_cache = {}
        conv._get_numbering_num_element = MagicMock()
        conv._get_numbering_level_definition = MagicMock()
        conv._str_to_int = MagicMock(side_effect=lambda val, default: int(val) if val is not None else default)
        conv.XML_KEY = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"
        conv._get_numbering_level_start = DocxConverter._get_numbering_level_start.__get__(conv, DocxConverter)
        return conv

    def test_default_start_is_one(self, converter):
        converter._get_numbering_num_element.return_value = None
        converter._get_numbering_level_definition.return_value = None
        assert converter._get_numbering_level_start(1, 0) == 1

    def test_abstract_num_start(self, converter):
        # No num element, but abstractNum lvl has a start
        converter._get_numbering_num_element.return_value = None
        start_elem = MockXmlElement("w:start", {"val": "5"})
        lvl = MockXmlElement("w:lvl")
        lvl._children = [start_elem]
        converter._get_numbering_level_definition.return_value = lvl
        assert converter._get_numbering_level_start(1, 0) == 5

    def test_lvl_override_start(self, converter):
        # num element with lvlOverride/startOverride
        start_override = MockXmlElement("w:startOverride", {"val": "10"})
        lvl_override = MockXmlElement("w:lvlOverride", {"ilvl": "0"})
        lvl_override._children = [start_override]
        num = MockXmlElement("w:num", {"numId": "1"})
        num._children = [lvl_override]
        converter._get_numbering_num_element.return_value = num
        assert converter._get_numbering_level_start(1, 0) == 10


# ── _render_numbering_prefix 测试 ─────────────────────────


class TestRenderNumberingPrefix:
    """DocxConverter._render_numbering_prefix 测试。"""

    @pytest.fixture
    def converter(self):
        from mineru.model.docx.docx_converter import DocxConverter
        conv = MagicMock(spec=DocxConverter)
        conv._get_numbering_level_definition = MagicMock()
        conv._advance_list_counter = MagicMock(return_value=1)
        conv.XML_KEY = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"
        conv._format_number_by_numfmt = MagicMock(side_effect=lambda n, f: str(n))
        conv._render_numbering_prefix = DocxConverter._render_numbering_prefix.__get__(conv, DocxConverter)
        return conv

    def test_chinese_counting_prefix(self, converter):
        """%1、 with chineseCounting at number 1 → 一、"""
        lvl = make_mock_lvl_element("chineseCounting", "%1、")
        converter._get_numbering_level_definition.return_value = lvl
        converter._format_number_by_numfmt.side_effect = lambda n, f: {1: "一", 2: "二"}.get(n, str(n))
        converter._advance_list_counter.return_value = 1
        result = converter._render_numbering_prefix(1, 0)
        assert "一" in result
        assert "、" in result

    def test_decimal_parentheses_prefix(self, converter):
        """(%1) with decimal at number 1 → (1)"""
        lvl = make_mock_lvl_element("decimal", "(%1)")
        converter._get_numbering_level_definition.return_value = lvl
        converter._advance_list_counter.return_value = 1
        converter._format_number_by_numfmt.side_effect = lambda n, f: str(n)
        result = converter._render_numbering_prefix(1, 0)
        assert result == "(1)"

    def test_roman_prefix(self, converter):
        """%1. with lowerRoman at number 4 → iv."""
        lvl = make_mock_lvl_element("lowerRoman", "%1.")
        converter._get_numbering_level_definition.return_value = lvl
        converter._advance_list_counter.return_value = 4
        converter._format_number_by_numfmt.side_effect = lambda n, f: "iv"
        result = converter._render_numbering_prefix(1, 0)
        assert result == "iv."

    def test_no_lvl_element_returns_empty(self, converter):
        converter._get_numbering_level_definition.return_value = None
        result = converter._render_numbering_prefix(1, 0)
        assert result == ""

    def test_no_lvl_text_returns_empty(self, converter):
        lvl = MockXmlElement("w:lvl")
        converter._get_numbering_level_definition.return_value = lvl
        result = converter._render_numbering_prefix(1, 0)
        assert result == ""


# ── _get_numfmt 测试 ──────────────────────────────────────


class TestGetNumfmt:
    """DocxConverter._get_numfmt 测试。"""

    @pytest.fixture
    def converter(self):
        from mineru.model.docx.docx_converter import DocxConverter
        conv = MagicMock(spec=DocxConverter)
        conv._get_numbering_level_definition = MagicMock()
        conv._get_numfmt = DocxConverter._get_numfmt.__get__(conv, DocxConverter)
        return conv

    def test_returns_numfmt_from_lvl(self, converter):
        converter._get_numbering_level_definition.return_value = make_mock_lvl_element("chineseCounting")
        assert converter._get_numfmt(1, 0) == "chineseCounting"

    def test_returns_decimal_when_no_lvl(self, converter):
        converter._get_numbering_level_definition.return_value = None
        assert converter._get_numfmt(1, 0) == "decimal"

    def test_returns_decimal_for_bullet(self, converter):
        converter._get_numbering_level_definition.return_value = make_mock_lvl_element("bullet")
        assert converter._get_numfmt(1, 0) == "bullet"
