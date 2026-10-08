"""Compare native DuckDB integer expressions with the previous parameter API."""
import json

import duckdb

from polisyos.data_forge.domains.catalog.batch.core_sources import loaders


def main():
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE years(raw VARCHAR)")
    con.executemany("INSERT INTO years VALUES (?)", [(None,), ("invalid",), ("-2147483648",), ("0",), ("2020",), ("2147483647",), ("2147483648",)])
    rows = []
    for value in (-(2**100), -(2**63)-1, -(2**63), -(2**31)-1, -(2**31), 0, 2020, 2**31-1, 2**31, 2**63-1, 2**63, 2**100):
        original_type, original_value = con.execute("SELECT typeof(?), ?", [value, value]).fetchone()
        expression = loaders._integer_sql_constant(value)
        relation = con.table("years")
        new_type, new_value = relation.project(duckdb.FunctionExpression("typeof", expression), expression).limit(1).fetchone()
        assert (original_type, original_value) == (new_type, new_value)
        year = duckdb.SQLExpression('try_cast("raw" AS INTEGER)')
        original = con.execute('SELECT raw FROM years WHERE try_cast("raw" AS INTEGER) >= ? ORDER BY raw', [value]).fetchall()
        current = relation.filter(year >= expression).project("raw").order("raw").fetchall()
        assert original == current
        rows.append({"integer": str(value), "native_type": original_type, "native_value": str(original_value), "original_selected": original, "new_selected": current})
    print(json.dumps({"duckdb": duckdb.__version__, "rows": rows, "count": len(rows), "nullable_invalid_and_outside_integer_column": True}, indent=2))


if __name__ == "__main__":
    main()
