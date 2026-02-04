"""Data loading utilities for resolving price/profile shorthand to arrays."""

import csv
import json
import os
from typing import Any, Optional, Union


def resolve_price_or_profile(
    value: Union[float, int, list[float], dict[str, Any]],
    expected_length: Optional[int],
) -> list[float]:
    """Resolve a price or profile value to a flat list of floats.

    Accepts:
    - float/int: expanded to constant array of expected_length
    - list[float]: validated length (if expected_length set), returned as-is
    - {"file": "path.csv"}: loaded from CSV (first numeric column)
    - {"file": "path.csv", "column": "price_eur"}: specific column from CSV
    - {"file": "path.json"}: loaded from JSON (flat array)

    :param value: The value to resolve.
    :param expected_length: Expected array length (from timespan). None skips length validation.
    :returns: List of floats.
    :raises ValueError: If the value cannot be resolved or has wrong length.
    :raises FileNotFoundError: If a referenced file does not exist.
    """
    if isinstance(value, (int, float)):
        if expected_length is None:
            raise ValueError(
                "Cannot expand scalar value without a timespan. Set the timespan first, or provide an explicit array."
            )
        return [float(value)] * expected_length

    if isinstance(value, list):
        result = [float(v) for v in value]
        if expected_length is not None and len(result) != expected_length:
            raise ValueError(
                f"Array length {len(result)} does not match expected length {expected_length} "
                f"(from timespan). Provide exactly {expected_length} values."
            )
        return result

    if isinstance(value, dict):
        return _load_from_file(value, expected_length)

    raise ValueError(
        f"Unsupported value type: {type(value).__name__}. "
        "Expected a number (flat value), list of numbers, or "
        '{"file": "path.csv"} for file loading.'
    )


def _load_from_file(spec: dict[str, Any], expected_length: Optional[int]) -> list[float]:
    """Load data from a file reference.

    :param spec: Dict with "file" key and optional "column" key.
    :param expected_length: Expected array length.
    :returns: List of floats loaded from file.
    """
    file_path = spec.get("file")
    if not file_path:
        raise ValueError('File reference must include a "file" key with the path.')

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Data file not found: {file_path}. Provide an absolute path to a CSV or JSON file on the local filesystem."
        )

    ext = os.path.splitext(file_path)[1].lower()
    column = spec.get("column")

    if ext == ".json":
        result = _load_json(file_path)
    elif ext in (".csv", ".tsv", ".txt"):
        result = _load_csv(file_path, column)
    else:
        raise ValueError(f"Unsupported file format: '{ext}'. Supported formats: .csv, .tsv, .json")

    if expected_length is not None and len(result) != expected_length:
        raise ValueError(
            f"File '{file_path}' has {len(result)} values, but expected {expected_length} "
            f"(from timespan). The file must contain exactly {expected_length} values."
        )

    return result


def _load_json(file_path: str) -> list[float]:
    """Load a flat array from a JSON file."""
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(
            f"JSON file '{file_path}' must contain a flat array of numbers, but got {type(data).__name__}."
        )

    try:
        return [float(v) for v in data]
    except (TypeError, ValueError) as e:
        raise ValueError(f"JSON file '{file_path}' contains non-numeric values: {e}") from e


def _load_csv(file_path: str, column: Optional[str] = None) -> list[float]:
    """Load numeric data from a CSV file.

    If column is specified, reads that column by header name.
    Otherwise, reads the first numeric column.
    """
    with open(file_path, encoding="utf-8", newline="") as f:
        sample = f.read(8192)
        f.seek(0)

        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel  # type: ignore[assignment]

        has_header = csv.Sniffer().has_header(sample)
        f.seek(0)

        reader = csv.reader(f, dialect)

        if has_header:
            headers = next(reader)
            if column:
                try:
                    col_idx = headers.index(column)
                except ValueError:
                    raise ValueError(
                        f"Column '{column}' not found in '{file_path}'. Available columns: {', '.join(headers)}"
                    )
            else:
                col_idx = _find_first_numeric_column(headers, file_path)
        else:
            if column:
                raise ValueError(f"Cannot use column='{column}' with '{file_path}': the file has no header row.")
            col_idx = 0

        values: list[float] = []
        for row_num, row in enumerate(reader, start=2 if has_header else 1):
            if not row or all(cell.strip() == "" for cell in row):
                continue
            if col_idx >= len(row):
                raise ValueError(
                    f"Row {row_num} in '{file_path}' has only {len(row)} columns, "
                    f"but column index {col_idx} was expected."
                )
            try:
                values.append(float(row[col_idx]))
            except ValueError:
                raise ValueError(
                    f"Non-numeric value '{row[col_idx]}' at row {row_num}, column {col_idx} in '{file_path}'."
                )

    if not values:
        raise ValueError(f"No data found in '{file_path}'.")

    return values


def _find_first_numeric_column(headers: list[str], file_path: str) -> int:
    """Find the first column that looks numeric based on the header name."""
    numeric_hints = ["price", "value", "cost", "demand", "power", "mw", "mwh", "eur", "profile"]
    for i, h in enumerate(headers):
        h_lower = h.lower().strip()
        for hint in numeric_hints:
            if hint in h_lower:
                return i
    return 0
