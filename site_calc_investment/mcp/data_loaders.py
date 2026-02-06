"""Data loading utilities for resolving price/profile shorthand to arrays."""

import csv
import json
import os
import posixpath
from typing import Any, Optional, Union
from urllib.parse import urlparse


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


def _resolve_save_path(file_path: str, data_dir: Optional[str] = None) -> str:
    """Resolve a file path for saving, applying data_dir for relative paths.

    :param file_path: Filename or path (relative or absolute).
    :param data_dir: Base directory for relative paths (or None for cwd).
    :returns: Absolute path string.
    :raises ValueError: If the extension is present but not '.csv'.
    """
    _, ext = os.path.splitext(file_path)
    if ext and ext.lower() != ".csv":
        raise ValueError(f"Only .csv files are supported, got '{ext}'. Use a .csv extension or omit the extension.")
    if not ext:
        file_path = file_path + ".csv"

    if os.path.isabs(file_path):
        return file_path

    base = data_dir if data_dir else os.getcwd()
    return os.path.abspath(os.path.join(base, file_path))


def save_csv(
    file_path: str,
    columns: dict[str, list[float]],
    data_dir: Optional[str] = None,
    overwrite: bool = False,
) -> str:
    """Save column data as a CSV file.

    :param file_path: Filename or path. Relative paths resolve against data_dir (or cwd).
        Extension '.csv' is appended if missing.
    :param columns: Named columns of numeric data. All must have the same length.
    :param data_dir: Base directory for relative paths.
    :param overwrite: Allow overwriting an existing file (default: False).
    :returns: Absolute path to the saved file.
    :raises ValueError: If columns are empty, have no rows, or have mismatched lengths.
    :raises FileExistsError: If file exists and overwrite is False.
    """
    if not columns:
        raise ValueError("columns must not be empty -- provide at least one named column.")

    lengths = {name: len(vals) for name, vals in columns.items()}
    unique_lengths = set(lengths.values())

    if unique_lengths == {0}:
        raise ValueError("All columns have 0 rows -- provide at least one row of data.")
    if len(unique_lengths) > 1:
        raise ValueError(f"All columns must have the same length, got: {lengths}")

    resolved = _resolve_save_path(file_path, data_dir)

    if not overwrite and os.path.exists(resolved):
        raise FileExistsError(f"File already exists: {resolved}. Set overwrite=True to replace it.")

    parent = os.path.dirname(resolved)
    if parent:
        os.makedirs(parent, exist_ok=True)

    col_names = list(columns.keys())
    row_count = len(next(iter(columns.values())))

    with open(resolved, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(col_names)
        for i in range(row_count):
            writer.writerow([columns[name][i] for name in col_names])

    return resolved


def _get_csv_metadata(file_path: str) -> dict[str, Any]:
    """Extract metadata from a CSV file (rows, columns, numeric columns).

    :param file_path: Absolute path to the CSV file.
    :returns: Dict with rows, columns, columns_count, numeric_columns.
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
            headers = [h.strip() for h in next(reader)]
            row_count = 0
        else:
            first_row = next(reader)
            headers = [f"col_{i}" for i in range(len(first_row))]
            row_count = 1
        numeric_cols: set[int] = set(range(len(headers)))
        rows_to_sample = 10
        if not has_header:
            for i in list(numeric_cols):
                if i < len(first_row):
                    try:
                        float(first_row[i])
                    except ValueError:
                        numeric_cols.discard(i)
        for row in reader:
            if not row or all(cell.strip() == "" for cell in row):
                continue
            row_count += 1
            if row_count <= rows_to_sample:
                for i in list(numeric_cols):
                    if i < len(row):
                        try:
                            float(row[i])
                        except ValueError:
                            numeric_cols.discard(i)
            if row_count == rows_to_sample:
                row_count += sum(1 for _ in reader)
                break

    numeric_column_names = [headers[i] for i in sorted(numeric_cols) if i < len(headers)]

    return {
        "rows": row_count,
        "columns": headers,
        "columns_count": len(headers),
        "numeric_columns": numeric_column_names,
    }


def fetch_url_to_file(
    url: str,
    data_dir: Optional[str] = None,
    file_path: Optional[str] = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Download a URL and save it to the local filesystem.

    :param url: URL to download.
    :param data_dir: Base directory for relative paths (or None for cwd).
    :param file_path: Filename or path. If None, derived from the URL.
    :param overwrite: Allow overwriting an existing file (default: False).
    :returns: Dict with file_path, url, rows, columns, columns_count, numeric_columns, message.
    :raises ValueError: If the URL is invalid or empty.
    :raises FileExistsError: If file exists and overwrite is False.
    :raises RuntimeError: If the download fails.
    """
    import httpx

    if not url or not url.strip():
        raise ValueError("URL must not be empty.")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL must use http or https scheme, got '{parsed.scheme}'.")

    if file_path is None:
        url_filename = posixpath.basename(parsed.path)
        if not url_filename or "." not in url_filename:
            url_filename = "downloaded_data.csv"
        file_path = url_filename

    resolved = _resolve_download_path(file_path, data_dir)

    if not overwrite and os.path.exists(resolved):
        raise FileExistsError(f"File already exists: {resolved}. Set overwrite=True to replace it.")

    parent = os.path.dirname(resolved)
    if parent:
        os.makedirs(parent, exist_ok=True)

    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=30.0) as response:
            response.raise_for_status()
            with open(resolved, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"HTTP error {e.response.status_code} downloading {url}") from e
    except httpx.RequestError as e:
        raise RuntimeError(f"Failed to download {url}: {e}") from e

    result: dict[str, Any] = {
        "file_path": resolved,
        "url": url,
    }

    ext = os.path.splitext(resolved)[1].lower()
    if ext in (".csv", ".tsv", ".txt"):
        try:
            metadata = _get_csv_metadata(resolved)
            result.update(metadata)
        except Exception as e:
            result["metadata_error"] = f"Could not extract CSV metadata: {e}"

    result["message"] = f"Downloaded {url} to {resolved}"
    if "rows" in result:
        result["message"] += f" ({result['rows']} rows, {result['columns_count']} columns)"

    return result


def _resolve_download_path(file_path: str, data_dir: Optional[str] = None) -> str:
    """Resolve a file path for downloads, allowing any extension.

    :param file_path: Filename or path (relative or absolute).
    :param data_dir: Base directory for relative paths (or None for cwd).
    :returns: Absolute path string.
    """
    if os.path.isabs(file_path):
        return file_path

    base = data_dir if data_dir else os.getcwd()
    return os.path.abspath(os.path.join(base, file_path))
