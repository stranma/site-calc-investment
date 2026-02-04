"""Tests for data_loaders — price/profile resolution from shorthand."""

import json

import pytest

from site_calc_investment.mcp.data_loaders import resolve_price_or_profile


class TestScalarExpansion:
    """Tests for expanding scalar values to arrays."""

    def test_float_expansion(self) -> None:
        result = resolve_price_or_profile(50.0, expected_length=8760)
        assert len(result) == 8760
        assert all(v == 50.0 for v in result)

    def test_int_expansion(self) -> None:
        result = resolve_price_or_profile(35, expected_length=100)
        assert len(result) == 100
        assert all(v == 35.0 for v in result)

    def test_scalar_without_expected_length_raises(self) -> None:
        with pytest.raises(ValueError, match="timespan"):
            resolve_price_or_profile(50.0, expected_length=None)

    def test_zero_expansion(self) -> None:
        result = resolve_price_or_profile(0.0, expected_length=24)
        assert len(result) == 24
        assert all(v == 0.0 for v in result)


class TestListValues:
    """Tests for passing raw list values."""

    def test_list_passthrough(self) -> None:
        values = [30.0, 40.0, 80.0, 50.0]
        result = resolve_price_or_profile(values, expected_length=4)
        assert result == values

    def test_list_wrong_length_raises(self) -> None:
        with pytest.raises(ValueError, match="does not match"):
            resolve_price_or_profile([1.0, 2.0, 3.0], expected_length=4)

    def test_list_no_length_validation(self) -> None:
        result = resolve_price_or_profile([1.0, 2.0], expected_length=None)
        assert result == [1.0, 2.0]

    def test_list_converts_ints(self) -> None:
        result = resolve_price_or_profile([1, 2, 3], expected_length=3)
        assert result == [1.0, 2.0, 3.0]
        assert all(isinstance(v, float) for v in result)


class TestCsvLoading:
    """Tests for loading data from CSV files."""

    def test_load_csv_with_header(self, tmp_csv: str) -> None:
        result = resolve_price_or_profile({"file": tmp_csv}, expected_length=8760)
        assert len(result) == 8760
        assert all(isinstance(v, float) for v in result)

    def test_load_csv_specific_column(self, tmp_csv: str) -> None:
        result = resolve_price_or_profile({"file": tmp_csv, "column": "price_eur"}, expected_length=8760)
        assert len(result) == 8760

    def test_load_csv_wrong_column_raises(self, tmp_csv: str) -> None:
        with pytest.raises(ValueError, match="not found"):
            resolve_price_or_profile({"file": tmp_csv, "column": "nonexistent"}, expected_length=8760)

    def test_load_csv_no_header(self, tmp_csv_no_header: str) -> None:
        result = resolve_price_or_profile({"file": tmp_csv_no_header}, expected_length=100)
        assert len(result) == 100

    def test_load_csv_wrong_length_raises(self, tmp_csv: str) -> None:
        with pytest.raises(ValueError, match="8760 values, but expected 100"):
            resolve_price_or_profile({"file": tmp_csv}, expected_length=100)

    def test_file_not_found_raises(self) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            resolve_price_or_profile({"file": "/nonexistent/path.csv"}, expected_length=100)


class TestJsonLoading:
    """Tests for loading data from JSON files."""

    def test_load_json_array(self, tmp_json: str) -> None:
        result = resolve_price_or_profile({"file": tmp_json}, expected_length=8760)
        assert len(result) == 8760

    def test_load_json_wrong_format(self, tmp_path: object) -> None:
        import pathlib

        path = pathlib.Path(str(tmp_path)) / "bad.json"
        with open(path, "w") as f:
            json.dump({"not": "an array"}, f)
        with pytest.raises(ValueError, match="flat array"):
            resolve_price_or_profile({"file": str(path)}, expected_length=None)


class TestUnsupportedInputs:
    """Tests for unsupported input types."""

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported value type"):
            resolve_price_or_profile("not_a_number", expected_length=100)  # type: ignore

    def test_empty_file_spec_raises(self) -> None:
        with pytest.raises(ValueError, match="file"):
            resolve_price_or_profile({}, expected_length=100)

    def test_unsupported_file_format_raises(self, tmp_path: object) -> None:
        import pathlib

        path = pathlib.Path(str(tmp_path)) / "data.xlsx"
        path.write_text("dummy")
        with pytest.raises(ValueError, match="Unsupported file format"):
            resolve_price_or_profile({"file": str(path)}, expected_length=100)
