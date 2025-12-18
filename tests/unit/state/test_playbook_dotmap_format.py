"""Tests for Box format specifier support.

This test file ensures that Box properly handles format specifiers
in f-strings, fixing the issue where Box objects don't support format
specifiers like `:,` for number formatting.
"""

from box import Box


class TestBoxFormatSpecifiers:
    """Test Box format specifier support."""

    def test_format_specifier_with_nested_dict_int(self):
        """Test format specifier with nested dictionary containing int values.

        This is the regression test for the reported issue where:
        f"${self.state.report_data['sales']:,}" would fail with:
        "unsupported format string passed to Box.__format__"
        """
        state = Box()
        state.report_data = Box({"sales": 1000, "region": "North", "trend": "positive"})

        # This should work without errors
        sales_value = state.report_data["sales"]
        formatted = f"${sales_value:,}"

        assert formatted == "$1,000"
        assert isinstance(sales_value, int)  # Should be native int, not Box

    def test_format_specifier_in_f_string_directly(self):
        """Test format specifier used directly in f-string with nested access.

        This tests the exact pattern from the user's error case.
        """
        state = Box()
        state.report_data = Box({"sales": 1000, "region": "North", "trend": "positive"})

        # This is the exact pattern that was failing
        summary = f'📊 **North Region Report**: Sales reached **${state.report_data["sales"]:,}** with a **{state.report_data["trend"]}** trend—excellent momentum!'

        assert "**$1,000**" in summary
        assert "**positive**" in summary
        assert "North Region Report" in summary

    def test_format_specifier_with_large_number(self):
        """Test format specifier with large numbers."""
        state = Box()
        state.report_data = Box({"sales": 1234567, "revenue": 9876543.21})

        sales_formatted = f"${state.report_data['sales']:,}"
        revenue_formatted = f"${state.report_data['revenue']:,.2f}"

        assert sales_formatted == "$1,234,567"
        assert revenue_formatted == "$9,876,543.21"

    def test_format_specifier_with_float(self):
        """Test format specifier with float values."""
        state = Box()
        state.metrics = Box({"percentage": 95.5, "ratio": 0.1234})

        percentage = f"{state.metrics['percentage']:.1f}%"
        ratio = f"{state.metrics['ratio']:.2%}"

        assert percentage == "95.5%"
        assert ratio == "12.34%"

    def test_nested_dict_access_returns_native_types(self):
        """Test that accessing nested dict values returns native Python types."""
        state = Box()
        state.data = Box(
            {"count": 42, "name": "test", "price": 99.99, "active": True, "empty": None}
        )

        # All should be native types, not Box
        assert isinstance(state.data["count"], int)
        assert isinstance(state.data["name"], str)
        assert isinstance(state.data["price"], float)
        assert isinstance(state.data["active"], bool)
        assert state.data["empty"] is None

    def test_deeply_nested_dict_format_specifier(self):
        """Test format specifier with deeply nested dictionaries."""
        state = Box()
        state.company = Box(
            {"financials": Box({"q1": Box({"revenue": 1000000, "profit": 250000})})}
        )

        revenue = f"${state.company.financials.q1.revenue:,}"
        profit = f"${state.company.financials.q1.profit:,}"

        assert revenue == "$1,000,000"
        assert profit == "$250,000"

    def test_format_specifier_with_list_of_numbers(self):
        """Test format specifier when accessing list elements."""
        state = Box()
        state.sales = [1000, 2000, 3000]

        # Accessing list elements should work normally
        first_sale = f"${state.sales[0]:,}"
        assert first_sale == "$1,000"

    def test_multiple_format_specifiers_in_one_string(self):
        """Test multiple format specifiers in a single f-string."""
        state = Box()
        state.report_data = Box(
            {"sales": 1000, "region": "North", "trend": "positive", "growth": 15.5}
        )

        summary = (
            f"Sales: ${state.report_data['sales']:,} | "
            f"Region: {state.report_data['region']} | "
            f"Growth: {state.report_data['growth']:.1f}%"
        )

        assert "Sales: $1,000" in summary
        assert "Region: North" in summary
        assert "Growth: 15.5%" in summary

    def test_format_specifier_preserves_dict_access(self):
        """Test that format specifiers work but dict access still works."""
        state = Box()
        state.report_data = Box({"sales": 1000, "details": Box({"region": "North"})})

        # Format specifier should work
        sales_formatted = f"${state.report_data['sales']:,}"
        assert sales_formatted == "$1,000"

        # Nested dict access should still work
        assert state.report_data["details"]["region"] == "North"
        assert state.report_data.details.region == "North"
