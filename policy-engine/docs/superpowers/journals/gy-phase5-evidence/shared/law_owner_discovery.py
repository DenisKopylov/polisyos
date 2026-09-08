"""Enumerate the current law-map owner graph and execute its existing candidate APIs."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import subprocess


def main() -> None:
    """Measure exact source identities and reusable law-mapping owners."""
    root = Path.cwd()
    first = {str(path.relative_to(root)) for path in (root / "src").rglob("*.py")}
    second = {
        str((Path(directory) / name).relative_to(root))
        for directory, _, names in os.walk(root / "src")
        for name in names
        if name.endswith(".py")
    }
    pattern = re.compile(
        r"LexInterventionMapEntry|LexProvisionMappingRegistry|LegalToDAGMapping|"
        r"build_gl_lex_intervention_map_bindings|mapping_evidence_ref|"
        r"law.{0,20}correspondence|correspondence.{0,20}law|"
        r"mapping_predicate_provenance"
    )
    ambiguous: list[dict[str, str]] = []
    matches: list[dict[str, object]] = []
    file_hashes: dict[str, str] = {}
    for relative in sorted(first):
        try:
            data = (root / relative).read_bytes()
            source = data.decode("utf-8")
            ast.parse(source)
        except (OSError, UnicodeError, SyntaxError) as exc:
            ambiguous.append({"path": relative, "error": str(exc)})
            continue
        file_hashes[relative] = hashlib.sha256(data).hexdigest()
        for number, line in enumerate(source.splitlines(), 1):
            if pattern.search(line):
                matches.append({"path": relative, "line": number, "text": line})
    rg = subprocess.run(
        ["rg", "--json", "--glob", "*.py", pattern.pattern, "src"],
        capture_output=True, text=True, check=False,
    )
    rg_identities = {
        (row["data"]["path"]["text"], row["data"]["line_number"])
        for line in rg.stdout.splitlines()
        if (row := json.loads(line))["type"] == "match"
    }
    identity_set = {(row["path"], row["line"]) for row in matches}
    census = {
        "denominator": "every filesystem src/**/*.py, including untracked lane source",
        "path_rglob": sorted(first), "os_walk": sorted(second),
        "paths_equal": first == second, "file_count": len(first),
        "ambiguous": ambiguous, "regex_matches": matches,
        "rg_identities": sorted(rg_identities), "rg_returncode": rg.returncode,
        "match_identity_sets_equal": identity_set == rg_identities,
        "matching_file_sha256": {key: file_hashes[key] for key, _ in sorted(identity_set)},
    }
    print(json.dumps({"source_census": census}, ensure_ascii=False, indent=2), flush=True)
    assert first == second and not ambiguous and rg.returncode in (0, 1)
    assert identity_set == rg_identities

    import duckdb
    from polisyos.lex.intervention_artifacts import LexInterventionMapEntry, LexProvisionMappingRegistry
    from polisyos.lex.interventions import LexInterventionCompiler
    from polisyos.lex.legal_evaluation.transport_constraints import LegalConstraintBridge
    from polisyos.lex.normpack.legal_authority import build_legal_authority_report
    from polisyos.runtime.quality import intervention_substrate as substrate
    from polisyos.runtime.quality.proving_ground import legal_mandate_search as gl

    bundle = substrate.load_l6_intervention_substrate(root)
    registry = substrate._lex_owner_registry(bundle)
    declarations = list(bundle.lex_authority_manifest["intervention_map_entries"])
    mappings = [registry.require_mapping(row["provision_ref"]).model_dump(mode="json") for row in declarations]
    declaration_refs = {row["provision_ref"] for row in declarations}
    resolved_refs = {row["provision_ref"] for row in mappings}
    assert declaration_refs == resolved_refs
    print(json.dumps({
        "existing_owner_execution": {
            "denominator": "every actual L6 lex_authority_manifest.intervention_map_entries member",
            "declarations": declarations, "resolved_registry_mappings": mappings,
            "identity_sets_equal": declaration_refs == resolved_refs,
            "map_entry_fields": list(LexInterventionMapEntry.model_fields),
            "gl_binding_fields": list(gl.Layer3GLLexInterventionMapBinding.model_fields),
            "gl_empty_real_input_output": [item.model_dump(mode="json") for item in gl.build_gl_lex_intervention_map_bindings(root)],
            "legal_authority_empty_input_output": build_legal_authority_report(
                target_context={}, candidate_norms=(), recommendation_claims=()
            ),
            "empty_transport_input_output": LegalConstraintBridge().map_constraints_to_dag([], None),
        },
        "owner_sources": {
            f"{owner.__module__}.{owner.__qualname__}": inspect.getsource(owner)
            for owner in (
                LexProvisionMappingRegistry.resolve,
                LexInterventionCompiler.compile,
                LegalConstraintBridge.map_constraints_to_dag,
                gl.build_gl_lex_intervention_map_bindings,
                gl._lex_intervention_registry_for_provision,
                build_legal_authority_report,
            )
        },
    }, ensure_ascii=False, indent=2), flush=True)
    db_path = root / substrate.DEFAULT_L3_LEX_DB_PATH
    with duckdb.connect(str(db_path), read_only=True) as connection:
        info = connection.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('information_schema', 'pg_catalog') "
            "ORDER BY table_schema, table_name"
        ).fetchall()
        native = connection.execute(
            "SELECT schema_name, table_name FROM duckdb_tables() WHERE NOT internal "
            "ORDER BY schema_name, table_name"
        ).fetchall()
        assert info == native
        tables = []
        for schema, table in info:
            quoted = '"' + schema.replace('"', '""') + '"."' + table.replace('"', '""') + '"'
            cursor = connection.execute(f"SELECT * FROM {quoted} LIMIT 0")
            columns = [(row[0], str(row[1])) for row in cursor.description]
            native_columns = connection.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema=? AND table_name=? ORDER BY ordinal_position", [schema, table]
            ).fetchall()
            assert [row[0] for row in columns] == [row[0] for row in native_columns]
            item = {"schema": schema, "table": table, "columns": columns, "native_columns": native_columns}
            if any(token in table.lower() for token in ("intervention", "mapping", "crosswalk", "adjudic")):
                rows = connection.execute(f"SELECT * FROM {quoted}").fetchall()
                count = connection.execute(f"SELECT count(*) FROM {quoted}").fetchone()[0]
                assert len(rows) == count
                item.update({"row_count": count, "rows": rows})
            tables.append(item)
    print(json.dumps({"lex_database": {
        "path": str(db_path.relative_to(root)), "read_only": True,
        "denominator": "every native base table, every column; every row for named intervention/mapping/crosswalk/adjudication tables",
        "information_schema_table_identities": info, "duckdb_table_identities": native,
        "tables": tables,
    }}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
