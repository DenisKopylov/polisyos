#!/usr/bin/env python3
"""
Bootstrap utility to scan DuckDB files and generate draft data contracts.

Scans all DuckDB files in a directory, extracts schema information,
and generates a draft data_contracts.json file. The developer then
annotates the drafts with descriptions, units, and PII tiers.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from tools._lib.imports import repo_root_from
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(repo_root_from(__file__)))

from tools._lib.fs import atomic_write_json, normalize_filesystem_path
from tools._lib.sql import validate_sql_identifier

try:
    import duckdb
except ImportError:
    print("Error: duckdb is required. Install with: pip install duckdb", file=sys.stderr)
    sys.exit(1)


DUCKDB_TYPE_MAP = {
    "TINYINT": "int",
    "SMALLINT": "int",
    "INTEGER": "int",
    "BIGINT": "int",
    "HUGEINT": "int",
    "UTINYINT": "int",
    "USMALLINT": "int",
    "UINTEGER": "int",
    "UBIGINT": "int",
    "INT": "int",
    "INT8": "int",
    "INT16": "int",
    "INT32": "int",
    "INT64": "int",
    "INT128": "int",
    "FLOAT": "float",
    "DOUBLE": "float",
    "DECIMAL": "float",
    "REAL": "float",
    "NUMERIC": "float",
    "BOOLEAN": "boolean",
    "BOOL": "boolean",
    "DATE": "datetime",
    "TIME": "datetime",
    "TIMESTAMP": "datetime",
    "TIMESTAMP WITH TIME ZONE": "datetime",
    "TIMESTAMPTZ": "datetime",
    "INTERVAL": "datetime",
    "VARCHAR": "string",
    "CHAR": "string",
    "BPCHAR": "string",
    "TEXT": "string",
    "STRING": "string",
    "UUID": "string",
    "BLOB": "string",
    "LIST": "array",
    "ARRAY": "array",
    "MAP": "json",
    "STRUCT": "json",
    "JSON": "json",
}


def map_duckdb_type(dtype: str) -> str:
    """Map DuckDB type to our DataType enum value."""

    dtype_upper = dtype.upper()

    if dtype_upper.endswith("[]"):
        return "array"

    base_type = re.split(r"[(\[]", dtype_upper)[0].strip()

    return DUCKDB_TYPE_MAP.get(base_type, "string")


def make_metric_id(db_stem: str, table: str, column: str) -> str:
    """
    Generate a canonical metric_id from source components.

    Format: {db_stem}.{table}.{column} normalized to lowercase.
    """

    def normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9_]", "_", value.lower())

    return f"{normalize(db_stem)}.{normalize(table)}.{normalize(column)}"


def make_display_name(column: str) -> str:
    """Generate human-readable display name from column name."""

    words = column.replace("_", " ").split()
    return " ".join(word.capitalize() for word in words)


def infer_pii_tier(column: str, dtype: str) -> str:
    """
    Infer PII tier from column name patterns.

    This is a heuristic -- human review is required.
    """

    column_lower = column.lower()

    high_pii = ["ssn", "social_security", "tax_id", "password", "secret", "credit_card"]
    for pattern in high_pii:
        if pattern in column_lower:
            return "high"

    medium_pii = ["email", "phone", "address", "name", "birth", "dob"]
    for pattern in medium_pii:
        if pattern in column_lower:
            return "medium"

    low_pii = ["age", "income", "salary", "zip", "postal"]
    for pattern in low_pii:
        if pattern in column_lower:
            return "low"

    return "none"


def infer_unit(column: str, dtype: str) -> str | None:
    """
    Infer unit from column name patterns.

    Returns None if no pattern matches -- human annotation required.
    """

    column_lower = column.lower()

    if any(
        pattern in column_lower
        for pattern in ["price", "cost", "amount", "balance", "income", "salary", "gdp"]
    ):
        return "usd"

    if any(pattern in column_lower for pattern in ["rate", "ratio", "percent", "pct"]):
        return "ratio"

    if any(pattern in column_lower for pattern in ["count", "num", "total", "qty"]):
        return "count"

    if any(pattern in column_lower for pattern in ["days", "hours", "minutes", "seconds"]):
        return column_lower.split("_")[-1]

    return None


def scan_duckdb(path: Path) -> list[dict[str, Any]]:
    """
    Extract column info from a DuckDB file.

    Args:
        path: Path to .duckdb file

    Returns:
        List of draft contract dictionaries
    """

    contracts: list[dict[str, Any]] = []
    safe_path = normalize_filesystem_path(
        path,
        kind="DuckDB path",
        must_exist=True,
        allow_directory=False,
    )
    db_stem = safe_path.stem

    try:
        conn = duckdb.connect(str(safe_path), read_only=True)
    except Exception as exc:
        print(f"Warning: Could not open {safe_path}: {exc}", file=sys.stderr)
        return contracts

    try:
        tables = conn.execute("SHOW TABLES").fetchall()

        for (table_name,) in tables:
            if str(table_name).startswith("_"):
                continue
            try:
                safe_table_name = validate_sql_identifier(str(table_name), kind="table")
            except ValueError as exc:
                print(f"Warning: Skipping unsafe table identifier {table_name!r}: {exc}", file=sys.stderr)
                continue

            try:
                columns = conn.execute(f"DESCRIBE {safe_table_name}").fetchall()
            except Exception as exc:
                print(f"Warning: Could not describe {safe_table_name}: {exc}", file=sys.stderr)
                continue

            for row in columns:
                col_name = row[0]
                col_type = row[1]

                if col_name.lower() in {"id", "created_at", "updated_at", "row_id"}:
                    continue

                dtype = map_duckdb_type(col_type)

                contract = {
                    "metric_id": make_metric_id(db_stem, table_name, col_name),
                    "display_name": make_display_name(col_name),
                    "description": f"TODO: Describe {col_name} from {safe_table_name}",
                    "dtype": dtype,
                    "unit": infer_unit(col_name, dtype),
                    "granularity": None,
                    "dimensions": [],
                    "valid_range": None,
                    "source_system": str(safe_path),
                    "source_table": safe_table_name,
                    "source_column": col_name,
                    "jurisdiction": None,
                    "pii_tier": infer_pii_tier(col_name, dtype),
                    "aliases": [col_name.lower()],
                    "tags": [],
                    "deprecated": False,
                    "superseded_by": None,
                }

                contracts.append(contract)

    finally:
        conn.close()

    return contracts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan DuckDB files and generate draft data contracts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "\n".join(
                [
                    "Examples:",
                    "    # Scan curated directory",
                    "    python tools/diagnostics/scan_fabric.py data/curated/",
                    "",
                    "    # Output to specific file",
                    "    python tools/diagnostics/scan_fabric.py data/curated/ -o contracts.json",
                    "",
                    "    # Scan with verbose output",
                    "    python tools/diagnostics/scan_fabric.py data/curated/ -v",
                ]
            )
        ),
    )

    parser.add_argument(
        "curated_dir",
        type=Path,
        help="Directory containing DuckDB files to scan",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("draft_contracts.json"),
        help="Output file path (default: draft_contracts.json)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--glob",
        default="*.duckdb",
        help="Glob pattern for DuckDB files (default: *.duckdb)",
    )

    args = parser.parse_args()

    if not args.curated_dir.exists():
        print(f"Error: Directory not found: {args.curated_dir}", file=sys.stderr)
        return 1

    all_contracts: list[dict[str, Any]] = []
    db_files = list(args.curated_dir.glob(args.glob))

    if not db_files:
        print(f"Warning: No DuckDB files found in {args.curated_dir}", file=sys.stderr)
        return 1

    for db_file in sorted(db_files):
        if args.verbose:
            print(f"Scanning {db_file}...")

        contracts = scan_duckdb(db_file)
        all_contracts.extend(contracts)

        if args.verbose:
            print(f"  Found {len(contracts)} columns")

    output = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "tools/diagnostics/scan_fabric.py",
        "contracts": all_contracts,
    }

    atomic_write_json(args.output, output)

    print(f"Generated {len(all_contracts)} draft contracts to {args.output}")
    print("\nNext steps:")
    print("  1. Review and edit the generated contracts")
    print("  2. Fill in TODO descriptions")
    print("  3. Verify units and PII tiers")
    print(
        "  4. Move to production: mv "
        f"{args.output} {args.curated_dir}/data_contracts.json"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
