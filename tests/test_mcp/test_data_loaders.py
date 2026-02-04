"""Tests for data_loaders — price/profile resolution from shorthand."""

import json
import os

import pytest

from site_calc_investment.mcp.data_loaders import resolve_price_or_profile, save_csv


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


class TestSaveCsv:
    """Tests for save_csv -- writing column data to CSV files."""

    def test_save_basic_csv(self, tmp_path: object) -> None:
        """Write a basic CSV and read it back via resolve_price_or_profile."""
        import pathlib

        out = pathlib.Path(str(tmp_path)) / "basic.csv"
        prices = [30.0, 40.0, 80.0, 50.0]
        saved = save_csv(str(out), columns={"price_eur": prices})
        assert os.path.isfile(saved)
        result = resolve_price_or_profile({"file": saved, "column": "price_eur"}, expected_length=4)
        assert result == prices

    def test_save_appends_csv_extension(self, tmp_path: object) -> None:
        """If no extension, .csv is appended."""
        import pathlib

        out = pathlib.Path(str(tmp_path)) / "no_ext"
        saved = save_csv(str(out), columns={"v": [1.0, 2.0]})
        assert saved.endswith(".csv")
        assert os.path.isfile(saved)

    def test_save_rejects_non_csv_extension(self, tmp_path: object) -> None:
        """Non-.csv extensions raise ValueError."""
        import pathlib

        out = pathlib.Path(str(tmp_path)) / "data.xlsx"
        with pytest.raises(ValueError, match="csv"):
            save_csv(str(out), columns={"v": [1.0]})

    def test_save_empty_columns_raises(self, tmp_path: object) -> None:
        """Empty columns dict raises ValueError."""
        import pathlib

        out = pathlib.Path(str(tmp_path)) / "empty.csv"
        with pytest.raises(ValueError, match="columns"):
            save_csv(str(out), columns={})

    def test_save_empty_rows_raises(self, tmp_path: object) -> None:
        """Columns with no rows raise ValueError."""
        import pathlib

        out = pathlib.Path(str(tmp_path)) / "empty_rows.csv"
        with pytest.raises(ValueError, match="row"):
            save_csv(str(out), columns={"v": []})

    def test_save_mismatched_lengths_raises(self, tmp_path: object) -> None:
        """Columns with different lengths raise ValueError."""
        import pathlib

        out = pathlib.Path(str(tmp_path)) / "mismatch.csv"
        with pytest.raises(ValueError, match="length"):
            save_csv(str(out), columns={"a": [1.0, 2.0], "b": [1.0]})

    def test_save_no_overwrite_raises_on_existing(self, tmp_path: object) -> None:
        """FileExistsError when file exists and overwrite=False."""
        import pathlib

        out = pathlib.Path(str(tmp_path)) / "exists.csv"
        save_csv(str(out), columns={"v": [1.0]})
        with pytest.raises(FileExistsError):
            save_csv(str(out), columns={"v": [2.0]}, overwrite=False)

    def test_save_overwrite_replaces_file(self, tmp_path: object) -> None:
        """overwrite=True replaces existing file."""
        import pathlib

        out = pathlib.Path(str(tmp_path)) / "overwrite.csv"
        save_csv(str(out), columns={"v": [1.0]})
        save_csv(str(out), columns={"v": [99.0]}, overwrite=True)
        result = resolve_price_or_profile({"file": str(out), "column": "v"}, expected_length=1)
        assert result == [99.0]

    def test_save_creates_parent_directories(self, tmp_path: object) -> None:
        """Nested parent directories are created automatically."""
        import pathlib

        out = pathlib.Path(str(tmp_path)) / "a" / "b" / "c" / "nested.csv"
        saved = save_csv(str(out), columns={"v": [1.0, 2.0]})
        assert os.path.isfile(saved)

    def test_save_resolves_relative_with_data_dir(self, tmp_path: object) -> None:
        """Relative path is resolved against data_dir."""
        import pathlib

        data_dir = pathlib.Path(str(tmp_path)) / "data_root"
        data_dir.mkdir()
        saved = save_csv("relative.csv", columns={"v": [1.0]}, data_dir=str(data_dir))
        assert str(data_dir) in saved
        assert os.path.isfile(saved)

    def test_save_large_dataset(self, tmp_path: object) -> None:
        """8760 rows roundtrip correctly."""
        import pathlib

        out = pathlib.Path(str(tmp_path)) / "large.csv"
        prices = [float(i % 100) for i in range(8760)]
        saved = save_csv(str(out), columns={"price": prices})
        result = resolve_price_or_profile({"file": saved, "column": "price"}, expected_length=8760)
        assert len(result) == 8760
        assert result[0] == 0.0
        assert result[99] == 99.0
