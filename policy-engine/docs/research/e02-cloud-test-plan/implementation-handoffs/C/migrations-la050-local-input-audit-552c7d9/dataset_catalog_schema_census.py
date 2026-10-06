"""Read only DuckDB information_schema column metadata for the local catalog."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb


DATABASE = Path(
    "/Users/deniskopylov/polisyos/policy-engine/production_data/"
    "datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
)
QUERY = (
    "SELECT table_schema, table_name, column_name, data_type "
    "FROM information_schema.columns "
    "ORDER BY table_schema, table_name, ordinal_position"
)
CANDIDATE_NAMES = ("manifest", "schema_version", "dataset_name", "raw_hash")


def main() -> None:
    connection = duckdb.connect(str(DATABASE), read_only=True)
    try:
        rows = connection.execute(QUERY).fetchall()
    finally:
        connection.close()
    columns = [
        {
            "table_schema": schema,
            "table_name": table,
            "column_name": column,
            "data_type": data_type,
        }
        for schema, table, column, data_type in rows
    ]
    tables = sorted({(row["table_schema"], row["table_name"]) for row in columns})
    candidate_columns = [
        row
        for row in columns
        if any(candidate in row["column_name"].lower() for candidate in CANDIDATE_NAMES)
    ]
    print(
        json.dumps(
            {
                "database_path": str(DATABASE),
                "read_only": True,
                "query": QUERY,
                "query_scope": "information_schema.columns only; no application-table rows, counts, or values were read.",
                "column_metadata_count": len(columns),
                "table_count": len(tables),
                "tables": [{"schema": schema, "name": table} for schema, table in tables],
                "candidate_column_name_terms": list(CANDIDATE_NAMES),
                "candidate_columns": candidate_columns,
                "columns": columns,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
