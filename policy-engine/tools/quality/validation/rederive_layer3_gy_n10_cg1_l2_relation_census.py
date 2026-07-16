"""Re-derive the read-only GY-N10 CG1-to-L2 relation census.

This is an intentionally long, shadow-only audit lane.  It never binds a relation
or grants value authority; it measures the complete owner denominator and writes a
content-addressed raw receipt for the compact checker to normalize.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(tempfile.gettempdir()) / "gy_n10_cg1_l2_relation_census.json"
ARTIFACT_PATH = ROOT / (
    "architecture/policy_design_case/layer3_gy_design_generation_contract.json"
)
DATABASE_PATH = ROOT / (
    "production_data/policyos_academic_runtime_slim_20260411T112032Z/"
    "academic/graph/scholar_knowledge.duckdb"
)
CERTIFIED_RELATIONS = {
    "exact",
    "certified-specialization",
    "generalization",
    "partial",
}
CRITICAL_RELATION_AXES = {
    "op",
    "target",
    "do_value",
    "sign",
    "scope",
    "population",
    "outcome",
    "effect_path",
    "estimand",
}
SAFE_CG1_COVERS = {"exact", "certified-specialization", "compositional"}
CANONICAL_ESTIMANDS = {
    "ate": "average_treatment_effect",
    "average_treatment_effect": "average_treatment_effect",
    "total_effect": "total_effect",
    "late": "local_average_treatment_effect",
    "local_average_treatment_effect": "local_average_treatment_effect",
    "controlled_direct": "controlled_direct_effect",
    "controlled_direct_effect": "controlled_direct_effect",
}
SIGN_ALIASES = {
    "increase": "increase",
    "increases": "increase",
    "positive": "increase",
    "+": "increase",
    "decrease": "decrease",
    "decreases": "decrease",
    "negative": "decrease",
    "-": "decrease",
}


def stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def parse_json(value: object, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    try:
        result = json.loads(str(value))
    except (json.JSONDecodeError, TypeError, ValueError):
        return fallback
    return result


def clean_list(value: object) -> tuple[str, ...]:
    payload = parse_json(value, [])
    if not isinstance(payload, list):
        return ()
    return tuple(sorted({str(item).strip() for item in payload if str(item).strip()}))


def exact_edge_tokens(value: object) -> tuple[tuple[str, ...], tuple[str, ...]]:
    payload = parse_json(value, [])
    if not isinstance(payload, list):
        return (), ()
    exact: set[str] = set()
    unresolved: set[str] = set()
    for item in payload:
        if isinstance(item, str):
            token = item.strip()
            if token:
                exact.add(token)
            continue
        if not isinstance(item, dict):
            unresolved.add(repr(item))
            continue
        edge_id = str(item.get("edge_id") or "").strip()
        if edge_id:
            exact.add(edge_id)
            continue
        src = str(item.get("src") or "").strip()
        dst = str(item.get("dst") or "").strip()
        direction = str(item.get("direction") or "").strip()
        if src and dst:
            unresolved.add(f"{src}->{dst}" + (f":{direction}" if direction else ""))
        else:
            unresolved.add(json.dumps(item, sort_keys=True, separators=(",", ":")))
    return tuple(sorted(exact)), tuple(sorted(unresolved))


def finite_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def context_fields(value: object) -> dict[str, Any]:
    payload = parse_json(value, {})
    return dict(payload) if isinstance(payload, dict) else {}


def relation_pair(certificate: Any, atom_id: str) -> dict[str, Any] | None:
    for row in certificate.relation_set.get("candidate_results", []):
        if str(row.get("atom_id") or "") == atom_id:
            return dict(row)
    return None


def main(*, output_path: Path = OUTPUT) -> int:
    started = time.monotonic()
    expected_venv = (ROOT / ".venv").resolve()
    if Path(sys.prefix).resolve() != expected_venv:
        raise SystemExit(
            f"wrong_interpreter_resolved:{Path(sys.prefix).resolve()}!={expected_venv}"
        )
    import polisyos

    package_path = Path(polisyos.__file__).resolve()
    if not package_path.is_relative_to(ROOT / "src"):
        raise SystemExit(f"wrong_checkout_resolved:{package_path}")

    from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
    from polisyos.ir._internal.validation import ensure_confidence_interval
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.intervention_atom_binding import InterventionAtomBinding
    from tools.quality.validation.shared_grounding_world_cache import GroundingWorldCache

    artifact_bytes = ARTIFACT_PATH.read_bytes()
    artifact = json.loads(artifact_bytes)
    atom_objects: list[Any] = []
    atom_errors: list[str] = []
    for run_index, run in enumerate(artifact.get("generation_results", [])):
        for candidate_index, candidate in enumerate(run.get("candidates", [])):
            atom_payload = candidate.get("atom")
            if atom_payload is None:
                continue
            try:
                atom_objects.append(
                    InterventionAtomBinding.model_validate(atom_payload)
                )
            except Exception as exc:
                atom_errors.append(
                    f"$.generation_results[{run_index}].candidates"
                    f"[{candidate_index}].atom:{type(exc).__name__}:{exc}"
                )
    if atom_errors:
        raise SystemExit(f"invalid_atom_shaped_rows:{atom_errors}")
    atoms_by_hash: dict[str, Any] = {}
    for atom in atom_objects:
        existing = atoms_by_hash.get(atom.content_hash)
        if existing is not None and existing != atom:
            raise SystemExit(f"conflicting_atom_content_hash:{atom.content_hash}")
        atoms_by_hash[atom.content_hash] = atom
    dispositions: dict[str, dict[str, Any]] = {}
    for run in artifact.get("generation_results", []):
        for disposition in run.get("grounding_dispositions", []):
            content_hash = str(disposition.get("shadow_atom_content_hash") or "")
            if disposition.get("disposition") == "shadow_bound" and content_hash:
                payload = dict(disposition)
                existing = dispositions.get(content_hash)
                if existing is not None and existing != payload:
                    raise SystemExit(
                        f"conflicting_shadow_disposition:{content_hash}"
                    )
                dispositions[content_hash] = payload
    denominator_hashes = sorted(set(atoms_by_hash) & set(dispositions))
    if len(denominator_hashes) != 2:
        raise SystemExit(f"canonical_shadow_atom_denominator_drift:{len(denominator_hashes)}")

    world_cache = GroundingWorldCache(ROOT)
    cache_entry = world_cache.get_entry(reason="gy_n10_cg1_l2_census")
    relation_engine = cache_entry.relation_engine
    reference_atom_ids = {item.atom_id for item in relation_engine.reference_atoms}

    atoms: list[dict[str, Any]] = []
    for content_hash in denominator_hashes:
        atom = atoms_by_hash[content_hash]
        disposition = dispositions[content_hash]
        identified_atom_id = str(disposition.get("identified_atom_id") or "")
        if identified_atom_id not in reference_atom_ids:
            raise SystemExit(f"identified_cg0_atom_missing:{identified_atom_id}")
        direct = atom.direct_effect_bundle
        direct_payload = direct.model_dump(mode="json")
        params = dict(direct_payload.get("params") or {})
        atoms.append(
            {
                "atom_id": atom.atom_id,
                "atom_content_hash": atom.content_hash,
                "artifact_ref": (
                    "architecture/policy_design_case/"
                    "layer3_gy_design_generation_contract.json"
                ),
                "candidate_id": disposition.get("candidate_id"),
                "identified_cg0_atom_id": identified_atom_id,
                "operator": atom.operator_kind.trinity_kind,
                "target_world_slots": list(atom.target_world_slots),
                "direct_outcomes": [
                    str(item) for item in params.get("outcome_slots", []) if str(item)
                ],
                "intended_outcomes": list(
                    atom.intended_downstream_estimand.outcome_variables
                ),
                "effect_path": [
                    str(item) for item in params.get("effect_path", []) if str(item)
                ],
                "estimand": atom.intended_downstream_estimand.functional,
                "target_context_id": atom.intended_downstream_estimand.target_population,
                "wmr_ref": atom.world_model_record_ref,
                "shadow_disposition": disposition.get("disposition"),
                "existing_cg1_certificate_id": (
                    disposition.get("certificate_chain") or {}
                ).get("cg1_certificate_id"),
                "existing_cg1_content_hash": (
                    disposition.get("certificate_chain") or {}
                ).get("cg1_content_hash"),
            }
        )

    if not DATABASE_PATH.exists():
        raise SystemExit("l2_owner_database_missing")
    skg_owner = SKGQuery(DATABASE_PATH, DATABASE_PATH.parent)
    try:
        skg_version_id = skg_owner.latest_skg_version_id()
        if skg_version_id is None or not skg_owner.has_skg_version_id(
            version_id=skg_version_id
        ):
            raise SystemExit("l2_owner_skg_version_unresolved")
    finally:
        skg_owner.close()
    con = duckdb.connect(str(DATABASE_PATH), read_only=True)
    try:
        simulation_rows = con.execute(
            """
            SELECT numeric_id, openalex_id, canonical_name, estimate_type,
                   point_estimate, estimate_sign, unit, evidence_strength,
                   confidence_interval_json, std_error, linked_claim_ids_json,
                   linked_edges_json, context_json, source_layer,
                   uncertainty_source, quality_flags_json
            FROM ac_skg_simulation_parameters
            ORDER BY numeric_id
            """
        ).fetchall()
        edge_rows = con.execute(
            """
            SELECT edge_id, src, dst, direction, n_articles, article_refs,
                   evidence_strength, confidence, scope_conditions,
                   meta_effect_size, candidate_layer, quality_signals_json
            FROM ac_skg_edges
            ORDER BY edge_id
            """
        ).fetchall()
        evidence_rows = con.execute(
            """
            SELECT edge_id, claim_id, openalex_id, src, dst, direction,
                   evidence_strength, confidence, design_family,
                   design_quality_tier, skg_version
            FROM ac_skg_edge_evidence
            ORDER BY edge_id, claim_id, openalex_id
            """
        ).fetchall()
        transport_rows = con.execute(
            """
            SELECT transport_id, edge_id, target_context_id, base_confidence,
                   generic_penalty, context_match_reward, transport_confidence,
                   match_mode, matched_moderators_json, skg_version
            FROM ac_skg_transport_scores
            ORDER BY edge_id, target_context_id, skg_version, transport_id
            """
        ).fetchall()
        floor_row = con.execute(
            """
            SELECT COALESCE(QUANTILE_CONT(transport_confidence, 0.10), 1.0)
            FROM ac_skg_transport_scores
            WHERE transport_confidence IS NOT NULL
            """
        ).fetchone()
    finally:
        con.close()
    # The transport owner derives this column from MAX(ac_skg_versions.version_id)
    # in run_transport_score; it is not a sibling column on ac_skg_versions.
    transport_skg_version = int(skg_version_id)

    transport_floor = max(0.0, min(1.0, float(floor_row[0] if floor_row else 1.0)))
    edges = {
        str(row[0]): {
            "edge_id": str(row[0]),
            "src": str(row[1]),
            "dst": str(row[2]),
            "direction": str(row[3]),
            "n_articles": int(row[4] or 0),
            "article_refs": parse_json(row[5], []),
            "evidence_strength": str(row[6] or ""),
            "confidence": finite_float(row[7]),
            "scope_conditions": parse_json(row[8], []),
            "meta_effect_size": finite_float(row[9]),
            "candidate_layer": str(row[10] or ""),
            "quality_signals": parse_json(row[11], {}),
        }
        for row in edge_rows
    }
    for edge in edges.values():
        edge["row_content_hash"] = stable_hash(edge)

    evidence_by_triple: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in evidence_rows:
        payload = {
            "edge_id": str(row[0]),
            "claim_id": str(row[1]),
            "openalex_id": str(row[2]),
            "src": str(row[3]),
            "dst": str(row[4]),
            "direction": str(row[5]),
            "evidence_strength": str(row[6] or ""),
            "confidence": finite_float(row[7]),
            "design_family": str(row[8] or ""),
            "design_quality_tier": None if row[9] is None else int(row[9]),
            "skg_version": int(row[10]),
        }
        payload["row_content_hash"] = stable_hash(payload)
        evidence_by_triple[
            (payload["edge_id"], payload["claim_id"], payload["openalex_id"])
        ] = payload

    transport_by_key: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in transport_rows:
        payload = {
            "transport_id": str(row[0]),
            "edge_id": str(row[1]),
            "target_context_id": str(row[2]),
            "base_confidence": finite_float(row[3]),
            "generic_penalty": finite_float(row[4]),
            "context_match_reward": finite_float(row[5]),
            "transport_confidence": finite_float(row[6]),
            "match_mode": str(row[7] or ""),
            "matched_moderators": parse_json(row[8], []),
            "skg_version": int(row[9]),
        }
        payload["row_content_hash"] = stable_hash(payload)
        transport_by_key[
            (payload["edge_id"], payload["target_context_id"], payload["skg_version"])
        ].append(payload)
    for records in transport_by_key.values():
        records.sort(
            key=lambda item: (
                -(item["transport_confidence"] or 0.0),
                item["transport_id"],
            )
        )

    manifest = Counter()
    manifest["simulation_rows_seen"] = len(simulation_rows)
    exact_pairs: list[dict[str, Any]] = []
    all_numeric_rows: list[dict[str, Any]] = []
    unresolved_numeric_rows: list[dict[str, Any]] = []
    unresolved_edge_tokens: set[str] = set()
    exact_edge_tokens_seen: set[str] = set()
    resolved_edge_ids: set[str] = set()
    for row in simulation_rows:
        numeric = {
            "numeric_id": str(row[0]),
            "openalex_id": str(row[1]),
            "canonical_name": str(row[2]),
            "estimate_type": str(row[3]),
            "point_estimate": finite_float(row[4]),
            "estimate_sign": str(row[5] or ""),
            "unit": str(row[6] or ""),
            "evidence_strength": str(row[7] or ""),
            "confidence_interval": parse_json(row[8], []),
            "std_error": finite_float(row[9]),
            "linked_claim_ids": list(clean_list(row[10])),
            "linked_edges": parse_json(row[11], []),
            "context": context_fields(row[12]),
            "source_layer": str(row[13] or ""),
            "uncertainty_source": str(row[14] or ""),
            "quality_flags": parse_json(row[15], []),
        }
        numeric["row_content_hash"] = stable_hash(numeric)
        interval_diagnostics: list[str] = []
        parameter = SKGQuery._to_evidence_parameter(
            numeric["canonical_name"],
            {
                "display_name": numeric["canonical_name"],
                "value": numeric["point_estimate"],
                "unit": numeric["unit"] or None,
                "evidence_strength": numeric["evidence_strength"],
                "confidence_interval": numeric["confidence_interval"],
                "std_error": numeric["std_error"],
            },
            diagnostics=interval_diagnostics,
        )
        ci = None
        interval_blocker = None
        if parameter is None:
            interval_blocker = "owner_parameter_validation_failed"
        elif parameter.confidence_interval is None:
            interval_blocker = "native_confidence_interval_missing"
        else:
            try:
                ensure_confidence_interval(
                    parameter.confidence_interval,
                    label="confidence_interval",
                    point_estimate=parameter.value,
                )
                ci = (
                    float(parameter.confidence_interval[0]),
                    float(parameter.confidence_interval[1]),
                )
            except (TypeError, ValueError) as exc:
                interval_blocker = (
                    f"owner_interval_validation_failed:{type(exc).__name__}:{exc}"
                )
        resolved_uncertainty_source = numeric["uncertainty_source"]
        if not resolved_uncertainty_source and ci is not None:
            resolved_uncertainty_source = "confidence_interval"
        elif not resolved_uncertainty_source and numeric["std_error"] is not None:
            resolved_uncertainty_source = "std_error"
        numeric["owner_interval_diagnostics"] = interval_diagnostics
        numeric["owner_interval_blocker"] = interval_blocker
        numeric["owner_ci_low"] = None if ci is None else ci[0]
        numeric["owner_ci_high"] = None if ci is None else ci[1]
        numeric["resolved_uncertainty_source"] = resolved_uncertainty_source
        numeric["owner_interval_eligible"] = ci is not None
        all_numeric_rows.append(numeric)
        if ci is not None:
            manifest["owner_validated_explicit_ci"] += 1
        elif numeric["std_error"] is not None:
            manifest["se_only"] += 1
        edge_tokens, pair_tokens = exact_edge_tokens(row[11])
        identity_blockers: set[str] = set()
        exact_edge_tokens_seen.update(edge_tokens)
        unresolved_edge_tokens.update(pair_tokens)
        if pair_tokens:
            identity_blockers.add("pair_only_edge_link_not_authoritative")
        if not edge_tokens:
            manifest["simulation_rows_without_edge_token"] += 1
            identity_blockers.add("exact_edge_link_missing")
        claim_ids = tuple(numeric["linked_claim_ids"])
        if not claim_ids:
            manifest["simulation_rows_without_claim_token"] += 1
            identity_blockers.add("linked_claim_id_missing")
        bound_pair_count = 0
        for edge_id in edge_tokens:
            edge = edges.get(edge_id)
            if edge is None:
                unresolved_edge_tokens.add(edge_id)
                manifest["edge_tokens_unresolved"] += 1
                identity_blockers.add("edge_id_unresolved")
                continue
            resolved_edge_ids.add(edge_id)
            triples = []
            for claim_id in claim_ids:
                evidence = evidence_by_triple.get(
                    (edge_id, claim_id, numeric["openalex_id"])
                )
                if evidence is None:
                    continue
                if evidence["skg_version"] != transport_skg_version:
                    manifest["exact_triples_wrong_skg_version"] += 1
                    continue
                triples.append(evidence)
            if not triples:
                manifest["edge_rows_without_exact_claim_edge_work_triple"] += 1
                identity_blockers.add("claim_edge_work_triple_unresolved")
                continue
            manifest["exact_claim_edge_work_triples"] += len(triples)
            pair = {
                "numeric": numeric,
                "edge": edge,
                "edge_evidence": triples,
                "ci_low": None if ci is None else ci[0],
                "ci_high": None if ci is None else ci[1],
                "native_interval_eligible": ci is not None,
            }
            exact_pairs.append(pair)
            bound_pair_count += 1
        numeric["identity_blockers"] = sorted(identity_blockers)
        if bound_pair_count == 0:
            unresolved_numeric_rows.append(numeric)
    manifest["exact_edge_tokens_seen"] = len(exact_edge_tokens_seen)
    manifest["edge_ids_resolved"] = len(resolved_edge_ids)
    manifest["pair_only_or_unresolved_edge_links"] = len(unresolved_edge_tokens)
    manifest["exact_numeric_edge_denominator"] = len(exact_pairs)
    manifest["numeric_identities_without_exact_bound_edge"] = len(
        unresolved_numeric_rows
    )

    target_contexts = sorted({str(atom["target_context_id"]) for atom in atoms})
    for pair in exact_pairs:
        edge_id = pair["edge"]["edge_id"]
        pair["transport_by_context"] = {}
        for context_id in target_contexts:
            records = list(
                transport_by_key.get(
                    (edge_id, context_id, transport_skg_version), []
                )
            )
            eligible = [
                item
                for item in records
                if item["transport_confidence"] is not None
                and item["transport_confidence"] >= transport_floor
            ]
            pair["transport_by_context"][context_id] = {
                "records": records,
                "transport_present": bool(records),
                "transport_eligible": bool(eligible),
                "selected_transport": (
                    eligible[0] if eligible else records[0] if records else None
                ),
            }
            if records:
                manifest[f"transport_present:{context_id}"] += 1
            if eligible:
                manifest[f"transport_above_floor:{context_id}"] += 1

    signature_groups: dict[str, dict[str, Any]] = {}
    pair_signature_key: dict[tuple[str, str], str] = {}
    registered_l6_operators = {
        str(edge.edge_id)
        for edge in cache_entry.reference.essential_edges.values()
        if edge.modality == "L6_KNOB_OPERATOR"
    }
    writable_wmr_slots = {
        str(slot)
        for candidate in relation_engine.reference_atoms
        for slot in candidate.signature.X_do
    }
    for pair in exact_pairs:
        numeric = pair["numeric"]
        edge = pair["edge"]
        raw_estimand = numeric["estimate_type"].strip().casefold().replace(" ", "_")
        estimand = CANONICAL_ESTIMANDS.get(raw_estimand)
        sign_token = (
            numeric["estimate_sign"].strip().casefold().replace(" ", "_")
            or edge["direction"].strip().casefold().replace(" ", "_")
        )
        sign = SIGN_ALIASES.get(sign_token)
        context = numeric["context"]
        population = str(context.get("context_id") or "").strip() or None
        time_value = (
            str(context.get("time_period") or "").strip()
            or str(context.get("publication_year") or "").strip()
            or None
        )
        group_basis = {
            "edge_id": edge["edge_id"],
            "edge_row_content_hash": edge["row_content_hash"],
            "estimand": estimand,
            "resolved_l6_operator": (
                edge["src"] if edge["src"] in registered_l6_operators else None
            ),
            "resolved_wmr_target": (
                edge["src"] if edge["src"] in writable_wmr_slots else None
            ),
            "population": population,
            "sign": sign,
            "time": time_value,
            "unit": numeric["unit"] or None,
        }
        key = stable_hash(group_basis)
        pair_signature_key[(numeric["numeric_id"], edge["edge_id"])] = key
        group = signature_groups.setdefault(
            key,
            {
                "basis": group_basis,
                "numeric_ids": [],
                "edge_evidence_refs": set(),
            },
        )
        group["numeric_ids"].append(numeric["numeric_id"])
        for evidence in pair["edge_evidence"]:
            group["edge_evidence_refs"].add(evidence["row_content_hash"])

    certificate_summaries: dict[str, dict[str, Any]] = {}
    ordered_groups = sorted(signature_groups.items())
    print(
        "CG1_CENSUS_DENOMINATOR",
        json.dumps(
            {
                "atoms": len(atoms),
                "exact_numeric_edge_pairs": len(exact_pairs),
                "signature_groups": len(ordered_groups),
                "transport_floor": transport_floor,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    for index, (key, group) in enumerate(ordered_groups, start=1):
        basis = group["basis"]
        edge = edges[basis["edge_id"]]
        l2_modal_claim = {
            "outcome": edge["dst"],
            "estimand": basis["estimand"] or "",
        }
        if basis["resolved_l6_operator"] is not None:
            l2_modal_claim["op"] = basis["resolved_l6_operator"]
        if basis["resolved_wmr_target"] is not None:
            l2_modal_claim["target"] = basis["resolved_wmr_target"]
        signature = {
            "op": basis["resolved_l6_operator"],
            "X_do": (
                [basis["resolved_wmr_target"]]
                if basis["resolved_wmr_target"] is not None
                else []
            ),
            "x_do": {},
            "sign": basis["sign"],
            "params": {},
            "scope": None,
            "unit": basis["unit"],
            "population": basis["population"],
            "time": basis["time"],
            "outcome": [edge["dst"]],
            "effect_path": [edge["src"], edge["dst"]],
            "estimand": basis["estimand"],
            "admissibility": "candidate_unverified",
            "wm_version": cache_entry.reference.component_versions.get("WMR"),
            "evidence": [
                f"l2_skg_edge:{edge['edge_id']}",
                edge["row_content_hash"],
                *sorted(group["edge_evidence_refs"]),
                f"skg_version_id:{skg_version_id}",
                f"transport_skg_version:{transport_skg_version}",
            ],
            "modal_claims": {"L2": l2_modal_claim},
        }
        raw_text = (
            f"Owner L2 causal estimate identity {edge['src']} -> {edge['dst']} "
            f"with direction {edge['direction']}."
        )
        certificate = relation_engine.certificate_for(
            {"raw_text": raw_text, "signature": signature},
            proposal_id=f"gy_n10.cg1_l2_census.{key.removeprefix('sha256:')[:16]}",
        )
        target_rows: dict[str, Any] = {}
        for atom in atoms:
            target_id = atom["identified_cg0_atom_id"]
            pair_row = relation_pair(certificate, target_id)
            if pair_row is None:
                target_rows[atom["atom_content_hash"]] = {
                    "census_status": "target_cg0_atom_not_retrieved",
                    "selected_relation": "unknown",
                    "solver_status": "UNKNOWN",
                    "critical_contradictions": [],
                    "unresolved_axes": ["cg1_target_candidate_retrieval"],
                    "residual_constraints": [],
                    "unsat_core_if_any": [],
                    "axis_witnesses": [],
                }
                continue
            target_rows[atom["atom_content_hash"]] = {
                "census_status": (
                    "cg1_certificate_emitted_via_read_only_exact_adapter_probe"
                ),
                "selected_relation": pair_row.get("selected_relation"),
                "solver_status": pair_row.get("solver_status"),
                "critical_contradictions": pair_row.get("critical_contradictions", []),
                "unresolved_axes": pair_row.get("unresolved_axes", []),
                "residual_constraints": pair_row.get("residual_constraints", []),
                "unsat_core_if_any": pair_row.get("unsat_core_if_any", []),
                "retrieval_reasons": pair_row.get("retrieval_reasons", []),
                "retrieval_score": pair_row.get("retrieval_score", 0.0),
                "axis_witnesses": pair_row.get("axis_witnesses", []),
            }
        certificate_summaries[key] = {
            "signature_basis": basis,
            "numeric_id_count": len(set(group["numeric_ids"])),
            "certificate_id": certificate.certificate_id,
            "certificate_content_hash": certificate.content_hash,
            "proposal_selected_relation": certificate.selected_relation,
            "proposal_solver_status": certificate.solver_status,
            "proposal_unsat_core": list(certificate.unsat_core_if_any),
            "reference_versions": dict(certificate.reference_versions),
            "shadow_only": certificate.shadow_only,
            "no_bind_admit_promote": certificate.no_bind_admit_promote,
            "target_atom_relations": target_rows,
        }
        if index % 100 == 0 or index == len(ordered_groups):
            print(
                "CG1_CENSUS_PROGRESS",
                index,
                len(ordered_groups),
                flush=True,
            )

    relation_rows: list[dict[str, Any]] = []
    viable_rows: list[str] = []
    relation_counts: Counter[str] = Counter()
    for pair in exact_pairs:
        numeric = pair["numeric"]
        edge = pair["edge"]
        signature_key = pair_signature_key[(numeric["numeric_id"], edge["edge_id"])]
        certificate = certificate_summaries[signature_key]
        for atom in atoms:
            atom_hash = atom["atom_content_hash"]
            relation = certificate["target_atom_relations"][atom_hash]
            transport = pair["transport_by_context"][atom["target_context_id"]]
            relation_class = str(relation["selected_relation"])
            solver_status = str(relation["solver_status"])
            critical_unresolved = sorted(
                set(relation["unresolved_axes"]) & CRITICAL_RELATION_AXES
            )
            certified = (
                relation["census_status"]
                == "cg1_certificate_emitted_via_read_only_exact_adapter_probe"
                and solver_status == "SAT"
                and relation_class in CERTIFIED_RELATIONS
                and relation_class not in {"false-analog", "unknown", "blocked"}
                and not relation["critical_contradictions"]
                and not critical_unresolved
            )
            safe_cover = certified and relation_class in SAFE_CG1_COVERS
            fork_a_evidence_candidate = bool(
                pair["native_interval_eligible"]
                and transport["transport_eligible"]
                and certified
            )
            blockers: list[str] = []
            if not pair["native_interval_eligible"]:
                blockers.append("native_interval_missing")
            if not transport["transport_present"]:
                blockers.append("transport_unavailable_for_scope")
            elif not transport["transport_eligible"]:
                blockers.append("transport_confidence_below_floor")
            if (
                relation["census_status"]
                != "cg1_certificate_emitted_via_read_only_exact_adapter_probe"
            ):
                blockers.append("cg1_target_candidate_not_retrieved")
            elif solver_status == "UNSAT":
                blockers.append("cg1_relation_blocked")
            elif solver_status != "SAT":
                blockers.append("cg1_relation_unknown")
            elif relation_class == "false-analog":
                blockers.append("cg1_false_analog_veto")
            elif relation_class not in CERTIFIED_RELATIONS:
                blockers.append("cg1_relation_uncertified")
            if relation_class in {"generalization", "partial"}:
                blockers.append("cg1_relation_not_safe_cover")
            blockers.append("runtime_numeric_estimate_identity_bridge_missing")
            row_payload = {
                "atom_id": atom["atom_id"],
                "atom_content_hash": atom_hash,
                "identified_cg0_atom_id": atom["identified_cg0_atom_id"],
                "numeric_id": numeric["numeric_id"],
                "numeric_row_content_hash": numeric["row_content_hash"],
                "numeric_ref": f"ac_skg_simulation_parameters:{numeric['numeric_id']}",
                "openalex_id": numeric["openalex_id"],
                "canonical_name": numeric["canonical_name"],
                "estimate_type": numeric["estimate_type"],
                "point_estimate": numeric["point_estimate"],
                "unit": numeric["unit"],
                "ci_low": pair["ci_low"],
                "ci_high": pair["ci_high"],
                "std_error": numeric["std_error"],
                "native_interval_eligible": pair["native_interval_eligible"],
                "owner_interval_diagnostics": numeric[
                    "owner_interval_diagnostics"
                ],
                "owner_interval_blocker": numeric["owner_interval_blocker"],
                "identity_link_blockers": numeric["identity_blockers"],
                "edge_id": edge["edge_id"],
                "edge_row_content_hash": edge["row_content_hash"],
                "edge_src": edge["src"],
                "edge_dst": edge["dst"],
                "edge_direction": edge["direction"],
                "edge_evidence_refs": sorted(
                    item["row_content_hash"] for item in pair["edge_evidence"]
                ),
                "target_context_id": atom["target_context_id"],
                "skg_version_id": skg_version_id,
                "transport_skg_version": transport_skg_version,
                "transport_floor": transport_floor,
                "transport_present": transport["transport_present"],
                "transport_eligible": transport["transport_eligible"],
                "transport_id": (
                    None
                    if transport["selected_transport"] is None
                    else transport["selected_transport"]["transport_id"]
                ),
                "transport_row_content_hash": (
                    None
                    if transport["selected_transport"] is None
                    else transport["selected_transport"]["row_content_hash"]
                ),
                "transport_confidence": (
                    None
                    if transport["selected_transport"] is None
                    else transport["selected_transport"]["transport_confidence"]
                ),
                "signature_group_hash": signature_key,
                "certificate_id": certificate["certificate_id"],
                "certificate_content_hash": certificate["certificate_content_hash"],
                "census_status": relation["census_status"],
                "selected_relation": relation_class,
                "solver_status": solver_status,
                "critical_contradictions": relation["critical_contradictions"],
                "unresolved_axes": relation["unresolved_axes"],
                "unresolved_critical_axes": critical_unresolved,
                "unsat_core_if_any": relation["unsat_core_if_any"],
                "certified_relation": certified,
                "runtime_identity_bridge_status": "bridge_missing",
                "safe_cg1_cover": safe_cover,
                "fork_a_evidence_candidate": fork_a_evidence_candidate,
                "production_value_eligible": False,
                "authority_status": "shadow_read_only_no_bind",
                "blockers": sorted(set(blockers)),
            }
            row_payload["relation_row_content_hash"] = stable_hash(row_payload)
            relation_rows.append(row_payload)
            relation_counts[f"{solver_status}:{relation_class}"] += 1
            if fork_a_evidence_candidate:
                viable_rows.append(row_payload["relation_row_content_hash"])

    for numeric in unresolved_numeric_rows:
        for atom in atoms:
            blockers = set(numeric["identity_blockers"])
            if not numeric["owner_interval_eligible"]:
                blockers.add(
                    numeric["owner_interval_blocker"]
                    or "native_confidence_interval_missing"
                )
            blockers.add("cg1_l2_numeric_estimate_adapter_missing")
            blockers.add("runtime_numeric_estimate_identity_bridge_missing")
            row_payload = {
                "atom_id": atom["atom_id"],
                "atom_content_hash": atom["atom_content_hash"],
                "identified_cg0_atom_id": atom["identified_cg0_atom_id"],
                "numeric_id": numeric["numeric_id"],
                "numeric_row_content_hash": numeric["row_content_hash"],
                "numeric_ref": (
                    f"ac_skg_simulation_parameters:{numeric['numeric_id']}"
                ),
                "openalex_id": numeric["openalex_id"],
                "canonical_name": numeric["canonical_name"],
                "estimate_type": numeric["estimate_type"],
                "point_estimate": numeric["point_estimate"],
                "unit": numeric["unit"],
                "ci_low": numeric["owner_ci_low"],
                "ci_high": numeric["owner_ci_high"],
                "std_error": numeric["std_error"],
                "native_interval_eligible": numeric[
                    "owner_interval_eligible"
                ],
                "owner_interval_diagnostics": numeric[
                    "owner_interval_diagnostics"
                ],
                "owner_interval_blocker": numeric["owner_interval_blocker"],
                "edge_id": None,
                "edge_row_content_hash": None,
                "edge_src": None,
                "edge_dst": None,
                "edge_direction": None,
                "edge_evidence_refs": [],
                "target_context_id": atom["target_context_id"],
                "skg_version_id": skg_version_id,
                "transport_skg_version": transport_skg_version,
                "transport_floor": transport_floor,
                "transport_present": False,
                "transport_eligible": False,
                "transport_id": None,
                "transport_row_content_hash": None,
                "transport_confidence": None,
                "signature_group_hash": None,
                "certificate_id": None,
                "certificate_content_hash": None,
                "census_status": "not_evaluated_bridge_missing",
                "selected_relation": "unknown",
                "solver_status": "UNKNOWN",
                "critical_contradictions": [],
                "unresolved_axes": ["l2_numeric_estimate_identity"],
                "unresolved_critical_axes": ["l2_numeric_estimate_identity"],
                "unsat_core_if_any": [],
                "certified_relation": False,
                "runtime_identity_bridge_status": "bridge_missing",
                "safe_cg1_cover": False,
                "fork_a_evidence_candidate": False,
                "production_value_eligible": False,
                "authority_status": "shadow_read_only_no_bind",
                "blockers": sorted(blockers),
            }
            row_payload["relation_row_content_hash"] = stable_hash(row_payload)
            relation_rows.append(row_payload)
            relation_counts["UNKNOWN:unknown"] += 1

    manifest["atom_x_numeric_edge_pairs_evaluated"] = len(relation_rows)
    manifest["minimum_atom_x_numeric_identity_denominator"] = (
        len(atoms) * len(all_numeric_rows)
    )
    manifest["fork_a_evidence_candidate_rows"] = len(viable_rows)
    numeric_owner_fingerprint = stable_hash(
        sorted({row["row_content_hash"] for row in all_numeric_rows})
    )
    edge_owner_fingerprint = stable_hash(
        sorted({pair["edge"]["row_content_hash"] for pair in exact_pairs})
    )
    transport_owner_fingerprint = stable_hash(
        sorted(
            item["row_content_hash"]
            for pair in exact_pairs
            for context in pair["transport_by_context"].values()
            for item in context["records"]
        )
    )
    payload = {
        "schema_version": "policyos.gy_n10.cg1_l2_prior_census.v1",
        "rule_version": "policyos.layer3.gy.n10.cg1_relation_extension.v1",
        "authority": "shadow_read_only_no_bind",
        "fork": "A" if viable_rows else "B",
        "fork_rule": (
            "A iff a SAT certified CG1 atom relation has an exact-bound, owner-validated "
            "native interval and owner transport at or above the data-derived floor; "
            "the runtime bridge still lands only after Fork A is selected; otherwise B"
        ),
        "input_refs": {
            "design_generation_artifact": (
                "architecture/policy_design_case/"
                "layer3_gy_design_generation_contract.json"
            ),
            "design_generation_artifact_sha256": (
                f"sha256:{hashlib.sha256(artifact_bytes).hexdigest()}"
            ),
            "l2_database_repo_relative": str(DATABASE_PATH.relative_to(ROOT)),
            "skg_version_id": skg_version_id,
            "transport_skg_version": transport_skg_version,
            "transport_version_binding_rule": (
                "run_transport_score:MAX(ac_skg_versions.version_id)"
            ),
        },
        "cache_receipt": {
            key: value
            for key, value in cache_entry.to_receipt().items()
            if not key.endswith("wall_seconds")
        },
        "atoms": atoms,
        "coverage_manifest": dict(sorted(manifest.items())),
        "owner_fingerprints": {
            "numeric_rows": numeric_owner_fingerprint,
            "edge_rows": edge_owner_fingerprint,
            "transport_rows": transport_owner_fingerprint,
        },
        "transport_floor": transport_floor,
        "transport_floor_rule": (
            "quantile_cont(ac_skg_transport_scores.transport_confidence,0.10)"
        ),
        "relation_counts": dict(sorted(relation_counts.items())),
        "fork_a_evidence_candidate_refs": sorted(viable_rows),
        "certificate_summaries": {
            key: certificate_summaries[key] for key in sorted(certificate_summaries)
        },
        "relation_rows": sorted(
            relation_rows,
            key=lambda item: (
                item["atom_content_hash"],
                item["numeric_id"],
                item["edge_id"],
                item["target_context_id"],
            ),
        ),
        "known_bridge_limits": [
            "cg1_l2_numeric_estimate_adapter_not_persisted",
            "numeric_to_raw_estimate_identity_bridge_missing",
        ],
        "probe_authority_limit": (
            "The census itself exact-joins numeric, claim, work, and edge owner rows, then "
            "constructs CG1's public explicit signature for shadow measurement. CG1 does "
            "not independently resolve numeric_id or verify those evidence refs; every "
            "runtime identity bridge remains bridge_missing until Fork A implementation."
        ),
        "retrieval_authority": (
            "CG1 FTS received only the exact L2 edge source, destination, and direction. "
            "No candidate atom vocabulary or caller hint entered retrieval or relation; "
            "naturally unretrieved target atoms remain typed unknown."
        ),
    }
    output = {**payload, "content_hash": gy_content_hash(payload)}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "CG1_CENSUS_RESULT",
        json.dumps(
            {
                "artifact": str(output_path),
                "content_hash": output["content_hash"],
                "fork": output["fork"],
                "manifest": output["coverage_manifest"],
                "relation_counts": output["relation_counts"],
                "fork_a_evidence_candidate_rows": len(
                    output["fork_a_evidence_candidate_refs"]
                ),
                "wall_time_seconds": round(time.monotonic() - started, 6),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    raise SystemExit(main(output_path=args.output))
