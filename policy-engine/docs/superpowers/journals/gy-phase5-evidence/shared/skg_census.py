"""Research only: whole retained-input identity sets and production CG2 source."""

import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess

import duckdb

from polisyos.runtime.quality import grounding_bind


def digest(items):
    return hashlib.sha256(json.dumps(items, sort_keys=True, default=str).encode()).hexdigest()


def main():
    root = Path("production_data").resolve()
    a = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    b = {str((Path(d) / n).relative_to(root)) for d, _, names in os.walk(root) for n in names if (Path(d) / n).is_file()}
    assert a == b, {"pathlib_only": sorted(a-b), "walk_only": sorted(b-a)}
    manifest = json.loads((root / "manifest.json").read_text())
    path = root / manifest["bundles"]["academic"]["academic_db_path"]
    databases = []
    for rel in sorted(a):
        if Path(rel).suffix not in {".duckdb", ".sqlite", ".sqlite3", ".db"}:
            continue
        item = {"path": rel, "size": (root / rel).stat().st_size}
        try:
            with duckdb.connect(str(root / rel), read_only=True) as con:
                first = con.execute("SELECT table_schema, table_name FROM information_schema.tables WHERE table_type='BASE TABLE' ORDER BY ALL").fetchall()
                second = con.execute("SELECT schema_name, table_name FROM duckdb_tables() WHERE NOT internal ORDER BY ALL").fetchall()
                assert first == second, (first, second)
                item["base_table_identity_set"] = first
                if root / rel == path:
                    tables = []
                    for schema, name in first:
                        quote = lambda v: '"' + v.replace('"','""') + '"'
                        cursor = con.execute(f"SELECT * FROM {quote(schema)}.{quote(name)} LIMIT 0")
                        columns = [(v[0], str(v[1])) for v in cursor.description]
                        tables.append({"schema":schema, "name":name, "columns":columns,
                            "rows":con.execute(f"SELECT count(*) FROM {quote(schema)}.{quote(name)}").fetchone()[0]})
                    item["all_academic_holder_tables"] = tables
        except (duckdb.Error, OSError) as exc:
            item["status"] = "ambiguous"
            item["error"] = repr(exc)
        databases.append(item)
    con = duckdb.connect(str(path), read_only=True)
    projections = {
        "canonical_variables": ("ac_skg_variables", "canonical_name,resolution_method,is_approved_canonical"),
        "claims": ("ac_causal_claims", "id,candidate_layer,strong_design_evidence"),
        "edges": ("ac_skg_edges", "edge_id,candidate_layer,evidence_strength"),
        "adjudications": ("ac_claim_adjudications", "claim_id,source_basis,support_status,publishable_edge"),
        "numeric_uncertainty": ("ac_parameter_estimates", "id,ci_low,ci_high,country"),
        "simulation_source": ("ac_skg_simulation_parameters", "numeric_id,openalex_id,canonical_name,linked_claim_ids_json,linked_edges_json"),
    }
    populations = {}
    for name, (table, columns) in projections.items():
        rows = con.execute(f"SELECT {columns} FROM {table}").fetchall()
        native = Counter(tuple(row) for row in rows)
        sql = {tuple(row[:-1]):row[-1] for row in con.execute(f"SELECT {columns},count(*) FROM {table} GROUP BY ALL").fetchall()}
        assert dict(native) == sql
        identities = sorted(str(row[0]) for row in rows)
        independently = sorted(str(row[0]) for row in con.execute(f"SELECT {columns.split(',')[0]} FROM {table} ORDER BY 1").fetchall())
        assert identities == independently
        populations[name] = {"table":table, "columns":columns, "rows":len(rows), "distinct_first_column":len(set(identities)),
            "identity_multiset_sha256":digest(identities), "independent_multiset_equal":True}
        if name in {"canonical_variables", "claims", "edges", "adjudications"}:
            populations[name]["group_counts"] = [(list(key), n) for key,n in sorted(Counter(tuple(row[1:]) for row in rows).items(), key=lambda v:str(v[0]))]
        if name == "numeric_uncertainty":
            populations[name]["both_native_bounds"] = sum(row[1] is not None and row[2] is not None for row in rows)
            populations[name]["nonzero_native_interval"] = sum(row[1] is not None and row[2] is not None and row[1] < row[2] for row in rows)
    con.close()
    # Complete tracked production Python set, reconciled to the filesystem set.
    tracked = subprocess.check_output(["git","ls-files","-z","src/polisyos"],text=True).split('\0')
    tracked = {p for p in tracked if p.endswith('.py')}
    walked = {str(p) for p in Path("src/polisyos").rglob("*.py")}
    assert tracked == walked, {"git_only":sorted(tracked-walked),"walk_only":sorted(walked-tracked)}
    keys = {"RelationAcceptanceSlot", "ProductionCG2CalibrationSource", "_owned_calibration_store"}
    calls, ambiguous = [], []
    for name in sorted(tracked):
        try:
            tree = ast.parse(Path(name).read_text())
        except (SyntaxError, UnicodeError) as exc:
            ambiguous.append({"path":name,"error":repr(exc)})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                token = node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else None
                if token in keys:
                    calls.append({"path":name,"line":node.lineno,"call":ast.unparse(node)})
    owner = grounding_bind._owned_calibration_store("unknown",source="production",calibration_min_samples=20)
    ledger = owner.ledger.model_dump(mode="json")
    # Persist the full native identity projections too; reports never promote count to truth.
    output = {"file_denominator":{"root":str(root),"file_types":"all regular files recursively", "count":len(a), "identity_set":sorted(a), "independent_identity_set_equal":True},
        "databases":databases,"populations":populations,"source_calls":{"denominator":"all tracked src/polisyos/**/*.py", "count":len(tracked),"identity_set_sha256":digest(sorted(tracked)), "ambiguous":ambiguous,"calls":calls},
        "executed_production_cg2_ledger":ledger,
        "limitations":["A table/field census proves retained vocabulary, not semantic impossibility.","Row presence and publication support do not establish proposal/reference relation truth.","No synthetic/caller assertion is supplied to the production calibration owner."]}
    print(json.dumps(output,indent=2,default=str))


if __name__ == "__main__":
    main()
