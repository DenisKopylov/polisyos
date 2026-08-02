"""Validate or re-derive the GY-N10 CG1-to-L2 census receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from polisyos.pdc import gy_content_hash
from tools.lib.timing import run_timed_entrypoint

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(tempfile.gettempdir()) / "gy_n10_cg1_l2_relation_census.json"
TARGET = ROOT / (
    "architecture/policy_design_case/"
    "layer3_gy_n10_cg1_l2_relation_census.json"
)


def _build_compact(raw: dict[str, Any]) -> dict[str, Any]:
    numeric: dict[str, dict[str, object]] = {}
    bindings: dict[str, dict[str, object]] = {}
    compact_relations: list[dict[str, object]] = []
    keys: set[tuple[object, ...]] = set()
    for row in raw["relation_rows"]:
        numeric_id = row["numeric_id"]
        numeric.setdefault(
            numeric_id,
            {
                "numeric_id": numeric_id,
                "row_content_hash": row["numeric_row_content_hash"],
                "ref": row["numeric_ref"],
                "openalex_id": row["openalex_id"],
                "canonical_name": row["canonical_name"],
                "estimate_type": row["estimate_type"],
                "point_estimate": row["point_estimate"],
                "unit": row["unit"],
                "ci_low": row["ci_low"],
                "ci_high": row["ci_high"],
                "std_error": row["std_error"],
                "native_interval_eligible": row["native_interval_eligible"],
                "owner_interval_blocker": row["owner_interval_blocker"],
                "owner_interval_diagnostics": row["owner_interval_diagnostics"],
            },
        )
        edge_id = row["edge_id"]
        if edge_id is not None:
            binding_key = f"{numeric_id}:{edge_id}"
            bindings.setdefault(
                binding_key,
                {
                    "binding_key": binding_key,
                    "numeric_id": numeric_id,
                    "edge_id": edge_id,
                    "edge_row_content_hash": row["edge_row_content_hash"],
                    "edge_src": row["edge_src"],
                    "edge_dst": row["edge_dst"],
                    "edge_direction": row["edge_direction"],
                    "edge_evidence_refs": row["edge_evidence_refs"],
                },
            )
        compact = {
            key: row[key]
            for key in (
                "atom_id",
                "atom_content_hash",
                "identified_cg0_atom_id",
                "numeric_id",
                "edge_id",
                "target_context_id",
                "skg_version_id",
                "transport_skg_version",
                "transport_present",
                "transport_eligible",
                "transport_id",
                "transport_row_content_hash",
                "transport_confidence",
                "transport_floor",
                "signature_group_hash",
                "certificate_id",
                "certificate_content_hash",
                "census_status",
                "selected_relation",
                "solver_status",
                "critical_contradictions",
                "unresolved_axes",
                "unresolved_critical_axes",
                "unsat_core_if_any",
                "certified_relation",
                "runtime_identity_bridge_status",
                "safe_cg1_cover",
                "fork_a_evidence_candidate",
                "production_value_eligible",
                "authority_status",
                "blockers",
                "relation_row_content_hash",
            )
        }
        key = (
            compact["atom_content_hash"],
            compact["numeric_id"],
            compact["edge_id"],
            compact["target_context_id"],
            compact["skg_version_id"],
        )
        if key in keys:
            raise SystemExit(f"duplicate_relation_primary_key:{key}")
        keys.add(key)
        compact_relations.append(compact)

    certificates: dict[str, dict[str, object]] = {}
    for signature_hash, certificate in raw["certificate_summaries"].items():
        targets: dict[str, dict[str, object]] = {}
        for atom_hash, relation in certificate["target_atom_relations"].items():
            witnesses = relation.get("axis_witnesses", [])
            targets[atom_hash] = {
                key: value
                for key, value in relation.items()
                if key != "axis_witnesses"
            }
            targets[atom_hash]["axis_witness_count"] = len(witnesses)
            targets[atom_hash]["axis_witnesses_content_hash"] = gy_content_hash(
                witnesses
            )
        certificates[signature_hash] = {
            key: value
            for key, value in certificate.items()
            if key != "target_atom_relations"
        }
        certificates[signature_hash]["target_atom_relations"] = targets

    payload = {
        key: value
        for key, value in raw.items()
        if key not in {"certificate_summaries", "content_hash", "relation_rows"}
    }
    numeric_rows = [numeric[key] for key in sorted(numeric)]
    binding_rows = [bindings[key] for key in sorted(bindings)]
    relation_rows = sorted(
        compact_relations,
        key=lambda item: (
            str(item["atom_content_hash"]),
            str(item["numeric_id"]),
            str(item["edge_id"] or ""),
            str(item["target_context_id"]),
        ),
    )

    def columnar(rows: list[dict[str, object]]) -> dict[str, object]:
        columns = sorted({key for row in rows for key in row})
        return {
            "columns": columns,
            "rows": [[row.get(column) for column in columns] for row in rows],
        }

    payload.update(
        {
            "schema_version": "policyos.gy_n10.cg1_l2_prior_census.compact.v1",
            "raw_full_table_content_hash": raw["content_hash"],
            "normalization": (
                "full primary-key relation denominator retained; repeated numeric, edge, "
                "and certificate witness payloads content-deduplicated"
            ),
            "relation_denominator_formula": (
                "2 atoms * (3579 exact numeric-edge bindings + 2967 numeric "
                "identities without an exact edge) = 13092 relation rows; null-edge "
                "rows remain typed bridge_missing sentinels"
            ),
            "numeric_identity_table": columnar(numeric_rows),
            "numeric_edge_binding_table": columnar(binding_rows),
            "certificate_summaries": {
                key: certificates[key] for key in sorted(certificates)
            },
            "relation_table": columnar(relation_rows),
        }
    )
    if len(numeric_rows) != raw["coverage_manifest"]["simulation_rows_seen"]:
        raise SystemExit("numeric_identity_denominator_drift")
    if len(relation_rows) != raw["coverage_manifest"][
        "atom_x_numeric_edge_pairs_evaluated"
    ]:
        raise SystemExit("relation_denominator_drift")
    output = {**payload, "content_hash": gy_content_hash(payload)}
    return output


def _table_rows(table: dict[str, Any]) -> list[dict[str, Any]]:
    columns = table.get("columns")
    rows = table.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise ValueError("columnar_table_invalid")
    if len(set(columns)) != len(columns):
        raise ValueError("columnar_columns_repeated")
    output: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) != len(columns):
            raise ValueError("columnar_row_width_drift")
        output.append(dict(zip(columns, row, strict=True)))
    return output


def _validate(payload: dict[str, Any]) -> dict[str, Any]:
    stored_hash = payload.get("content_hash")
    stable = {key: value for key, value in payload.items() if key != "content_hash"}
    if stored_hash != gy_content_hash(stable):
        raise ValueError("census_content_hash_mismatch")
    if payload.get("fork") != "B":
        raise ValueError("census_fork_not_evidence_selected")
    if payload.get("authority") != "shadow_read_only_no_bind":
        raise ValueError("census_authority_drift")
    if payload.get("fork_a_evidence_candidate_refs") != []:
        raise ValueError("fork_a_candidate_denominator_nonempty")

    manifest = payload.get("coverage_manifest")
    if not isinstance(manifest, dict):
        raise ValueError("coverage_manifest_missing")
    numeric_rows = _table_rows(payload["numeric_identity_table"])
    binding_rows = _table_rows(payload["numeric_edge_binding_table"])
    relation_rows = _table_rows(payload["relation_table"])
    expected_numeric = int(manifest["simulation_rows_seen"])
    expected_bindings = int(manifest["exact_numeric_edge_denominator"])
    expected_relations = int(manifest["atom_x_numeric_edge_pairs_evaluated"])
    if len(numeric_rows) != expected_numeric:
        raise ValueError("numeric_identity_denominator_drift")
    if len(binding_rows) != expected_bindings:
        raise ValueError("numeric_edge_binding_denominator_drift")
    if len(relation_rows) != expected_relations:
        raise ValueError("relation_denominator_drift")
    formula_total = len(payload["atoms"]) * (
        expected_bindings
        + int(manifest["numeric_identities_without_exact_bound_edge"])
    )
    if formula_total != expected_relations:
        raise ValueError("relation_denominator_formula_drift")

    primary_keys: set[tuple[Any, ...]] = set()
    measured_counts: Counter[str] = Counter()
    certificates = payload.get("certificate_summaries")
    if not isinstance(certificates, dict):
        raise ValueError("certificate_summaries_missing")
    for row in relation_rows:
        primary_key = (
            row["atom_content_hash"],
            row["numeric_id"],
            row["edge_id"],
            row["target_context_id"],
            row["skg_version_id"],
        )
        if primary_key in primary_keys:
            raise ValueError("duplicate_relation_primary_key")
        primary_keys.add(primary_key)
        measured_counts[f"{row['solver_status']}:{row['selected_relation']}"] += 1
        if row["production_value_eligible"] is not False:
            raise ValueError("shadow_census_granted_value_authority")
        if row["fork_a_evidence_candidate"] is not False:
            raise ValueError("fork_a_candidate_not_empty")
        if row["runtime_identity_bridge_status"] != "bridge_missing":
            raise ValueError("runtime_identity_bridge_fabricated")
        signature_hash = row["signature_group_hash"]
        if signature_hash is None:
            if row["certificate_id"] is not None:
                raise ValueError("certificate_without_signature")
            continue
        summary = certificates.get(signature_hash)
        if not isinstance(summary, dict):
            raise ValueError("relation_certificate_summary_missing")
        if row["certificate_id"] != summary.get("certificate_id"):
            raise ValueError("relation_certificate_id_drift")
        if row["certificate_content_hash"] != summary.get("certificate_content_hash"):
            raise ValueError("relation_certificate_content_hash_drift")
    if dict(sorted(measured_counts.items())) != payload.get("relation_counts"):
        raise ValueError("relation_counts_drift")

    artifact_ref = ROOT / payload["input_refs"]["design_generation_artifact"]
    artifact_hash = f"sha256:{hashlib.sha256(artifact_ref.read_bytes()).hexdigest()}"
    if artifact_hash != payload["input_refs"]["design_generation_artifact_sha256"]:
        raise ValueError("design_generation_artifact_ref_drift")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if "/Users/" in serialized or str(ROOT) in serialized:
        raise ValueError("census_absolute_path_leaked")
    for forbidden in ('"created_at"', '"timestamp"', '"wall_time', '"elapsed_'):
        if forbidden in serialized:
            raise ValueError(f"census_volatile_field:{forbidden}")

    return {
        "content_hash": stored_hash,
        "fork": payload["fork"],
        "numeric_identities": len(numeric_rows),
        "numeric_edge_bindings": len(binding_rows),
        "relation_rows": len(relation_rows),
        "relation_counts": dict(sorted(measured_counts.items())),
    }


def _write(payload: dict[str, Any], target: Path) -> bytes:
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encoded)
    return encoded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--rederive-audit", action="store_true")
    modes.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=TARGET)
    args = parser.parse_args(argv)

    if args.check:
        report = _validate(json.loads(args.output.read_text(encoding="utf-8")))
        print(json.dumps({"status": "pass", **report}, sort_keys=True))
        return 0
    if args.corrupt_field_drift_check:
        corrupt = json.loads(args.output.read_text(encoding="utf-8"))
        columns = corrupt["relation_table"]["columns"]
        authority_index = columns.index("production_value_eligible")
        corrupt["relation_table"]["rows"][0][authority_index] = True
        stable = {key: value for key, value in corrupt.items() if key != "content_hash"}
        corrupt["content_hash"] = gy_content_hash(stable)
        try:
            _validate(corrupt)
        except ValueError as exc:
            print(f"corrupt-field drift check: PASS corruption rejected [{exc}]")
            return 1
        print("corrupt-field drift check: FAIL corruption was accepted")
        return 0
    if args.write:
        compact = _build_compact(json.loads(args.source.read_text(encoding="utf-8")))
        report = _validate(compact)
        _write(compact, args.output)
        print(json.dumps({"status": "written", **report}, sort_keys=True))
        return 0

    from tools.quality.validation.rederive_layer3_gy_n10_cg1_l2_relation_census import (
        main as rederive,
    )

    with tempfile.TemporaryDirectory(prefix="gy_n10_cg1_l2_census_") as directory:
        raw_output = Path(directory) / "raw.json"
        rederive(output_path=raw_output)
        compact = _build_compact(json.loads(raw_output.read_text(encoding="utf-8")))
        report = _validate(compact)
        encoded = (
            json.dumps(
                compact,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            + "\n"
        ).encode()
        if encoded != args.output.read_bytes():
            raise SystemExit("census_rederive_drift")
    print(json.dumps({"status": "pass", **report}, sort_keys=True))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
