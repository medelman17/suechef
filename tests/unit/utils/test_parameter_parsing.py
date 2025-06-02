"""
Unit tests for parameter parsing utilities.
"""

import pytest
from src.utils.parameter_parsing import parse_string_list


class TestParameterParsing:
    """Test parameter parsing utilities."""

    def test_parse_string_list_with_list(self):
        """Test parsing when input is already a list."""
        input_data = ["item1", "item2", "item3"]
        result = parse_string_list(input_data)
        assert result == ["item1", "item2", "item3"]

    def test_parse_string_list_with_string(self):
        """Test parsing comma-separated string."""
        input_data = "item1,item2,item3"
        result = parse_string_list(input_data)
        assert result == ["item1", "item2", "item3"]

    def test_parse_string_list_with_whitespace(self):
        """Test parsing string with whitespace."""
        input_data = "item1, item2 , item3"
        result = parse_string_list(input_data)
        assert result == ["item1", "item2", "item3"]

    def test_parse_string_list_with_empty_string(self):
        """Test parsing empty string."""
        result = parse_string_list("")
        assert result is None

    def test_parse_string_list_with_none(self):
        """Test parsing None value."""
        result = parse_string_list(None)
        assert result is None

    def test_parse_string_list_with_json_array(self):
        """Test parsing JSON array string."""
        input_data = '["item1", "item2", "item3"]'
        result = parse_string_list(input_data)
        assert result == ["item1", "item2", "item3"]

    def test_parse_string_list_with_single_item(self):
        """Test parsing single item."""
        result = parse_string_list("single_item")
        assert result == ["single_item"]