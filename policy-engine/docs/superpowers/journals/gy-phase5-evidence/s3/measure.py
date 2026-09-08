"""Read-only complete L6 source and live owner/consumer measurement for GY-S3."""
from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[5]


def emit(payload: object) -> None:
    print(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2, default=str))


def routing() -> None:
    from polisyos.foundry.methods.selection.advisor import select_value_method_for_problem
    from polisyos.runtime.quality.intervention_substrate import (
        default_l6_bundle_paths,
        load_l6_intervention_substrate,
        replace_intervention_substrate_bundle,
        route_observation_family_method,
    )

    bundle = load_l6_intervention_substrate(ROOT)
    paths = default_l6_bundle_paths(ROOT)
    manifest = bundle.observation_manifest
    # Independent identity derivation: typed owner load versus raw JSON file walks.
    identities = {
        "knobs": sorted(bundle.knob_dictionary),
        "laws": sorted(bundle.lex_intervention_map),
        "routes": sorted(row["family"] for row in manifest["routes"]),
    }
    independent = {
        "knobs": sorted(k for k, _ in json.loads(paths["intervention_knob_dictionary"].read_text()).items()),
        "laws": sorted(k for k, _ in json.loads(paths["lex_intervention_map"].read_text()).items()),
        "routes": sorted(row["family"] for row in json.loads(paths["observation_to_contract_manifest"].read_text())["routes"]),
    }
    broken = copy.deepcopy(manifest)
    for row in broken["routes"]:
        row["target_contract"] = {
            "contract_id": "census.nonexistent.contract",
            "contract_fqn": "census.NonexistentContract",
        }
    candidate = {"candidate_id": "census-firm-fundamentals", "atom": {"target_world_slots": ("firm_fundamentals",)}, "diversity_key": ("firm_fundamentals",)}
    problem = {"problem_statement": "Estimate causal effects from firm_fundamentals observations", "outcome_of_interest": {"target_variable": "firm_fundamentals"}, "runtime_hints": {}}
    selections = {
        name: select_value_method_for_problem(candidate=candidate, problem=problem, observation_to_contract_manifest=value)
        for name, value in [("absent", None), ("real", manifest), ("fake_routes", broken), ("positive_flat_panel", {"contracts": [{"data_modality": "panel"}]})]
    }
    routes = {}
    for family in identities["routes"]:
        try:
            routes[family] = route_observation_family_method(bundle, family=family).model_dump(mode="json")
        except Exception as error:
            routes[family] = {"ambiguous": True, "exception_type": type(error).__name__, "detail": str(error)}
    fake_routes = {}
    fake_bundle = replace_intervention_substrate_bundle(bundle, update={"observation_manifest": broken})
    for family in identities["routes"]:
        try:
            fake_routes[family] = route_observation_family_method(fake_bundle, family=family).model_dump(mode="json")
        except Exception as error:
            fake_routes[family] = {"exception_type": type(error).__name__, "code": getattr(error, "code", None), "detail": str(error)}
    emit({
        "root": ROOT, "selector_source": inspect.getfile(select_value_method_for_problem),
        "source_denominators": {key: str(value) for key, value in paths.items()},
        "file_type_denominator": "Complete top-level entries in knob/law JSON; complete routes array in manifest JSON",
        "owner_identity_sets": identities, "independent_raw_json_identity_sets": independent,
        "identity_symmetric_differences": {key: sorted(set(value) ^ set(independent[key])) for key, value in identities.items()},
        "selections": selections, "owner_routes": routes, "owner_fake_routes": fake_routes,
        "absent_equals_real": selections["absent"] == selections["real"],
        "real_equals_fake": selections["real"] == selections["fake_routes"],
        "real_equals_flat_positive": selections["real"] == selections["positive_flat_panel"],
    })
    assert identities == independent


def behavior() -> None:
    from polisyos.runtime.quality.intervention_substrate import intervention_substrate_behavior_report
    report = intervention_substrate_behavior_report(ROOT)
    emit(report)
    sys.exit(0 if report["status"] == "pass" else 1)


def law_registry() -> None:
    from polisyos.lex.knowledge.store import LegalKnowledgeStore
    from polisyos.runtime.quality.intervention_substrate import (
        DEFAULT_L3_LEX_DB_PATH, load_l6_intervention_substrate,
        resolve_intervention_lever, resolve_law_bound_lever,
    )
    from polisyos.runtime.quality.substrate_registry import (
        SubstrateLayer, build_substrate_registry_from_existing_catalogs,
    )
    bundle = load_l6_intervention_substrate(ROOT)
    lex = LegalKnowledgeStore(ROOT / DEFAULT_L3_LEX_DB_PATH, (ROOT / DEFAULT_L3_LEX_DB_PATH).parent, canonical_db_ref_path=DEFAULT_L3_LEX_DB_PATH)
    knobs = {}
    for key, raw in bundle.knob_dictionary.items():
        try:
            knobs[key] = resolve_intervention_lever(bundle, operator_kind=key, parameter_value=(raw["min"] + raw["max"]) / 2).model_dump(mode="json")
        except Exception as error:
            knobs[key] = {"ambiguous": True, "exception_type": type(error).__name__, "detail": str(error)}
    laws = {}
    for law, raw in bundle.lex_intervention_map.items():
        keys = raw if not isinstance(raw, dict) else raw.get("knob_ids") or raw.get("knobs") or raw.get("knob_id")
        if isinstance(keys, str):
            keys = [keys]
        for knob in keys:
            identity = law + "->" + knob
            raw_knob = bundle.knob_dictionary[knob]
            try:
                laws[identity] = resolve_law_bound_lever(bundle, law_token=law, knob_id=knob, parameter_value=(raw_knob["min"] + raw_knob["max"]) / 2, legal_store=lex).model_dump(mode="json")
            except Exception as error:
                laws[identity] = {"ambiguous": True, "exception_type": type(error).__name__, "detail": str(error)}
    registry = build_substrate_registry_from_existing_catalogs(ROOT)
    owner_entries = registry.resolve(layer=SubstrateLayer.L6)
    all_entries = registry.model_dump(mode="json")["entries"]
    raw_selected = [row for row in all_entries if row["layer"] == "L6"]
    emit({"knobs": knobs, "law_knob_pairs": laws,
          "l6_registry_owner": [row.model_dump(mode="json") for row in owner_entries],
          "l6_registry_independent_filter": raw_selected,
          "registry_content_hash": registry.content_hash,
          "registered_scenario_templates_ref": bundle.source_refs["policy_scenario_templates"]})


def decisive_removal() -> None:
    from unittest.mock import patch
    from polisyos.runtime.quality import intervention_substrate as owner

    resolve = owner._registered_methods_for_contract
    def without_target_validation(registry, contract_id, *, contract_fqn):
        matches = resolve(registry, contract_id, contract_fqn=contract_fqn)
        return matches or resolve(registry, "foundry.causal.panel_observational_data.v1", contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.PanelObservationalData")

    with patch.object(owner, "_assert_compiled_contract", lambda *args: None), patch.object(owner, "_registered_methods_for_contract", without_target_validation):
        report = owner.intervention_substrate_behavior_report(ROOT)
    emit({"mutation": "Remove compiled-target and real-registry-target refusal, retain valid target resolution and all marker strings", "report": report})
    # The research succeeds only when the unchanged contract is red.
    assert report["status"] == "fail"
    assert any(row["mutation_id"] == "dead_route_succeeds" and row["status"] == "green" for row in report["remove_property_mutations"])


def n4_routing() -> None:
    from types import SimpleNamespace
    from unittest.mock import patch
    from polisyos.runtime.quality import design_generation as consumer
    from polisyos.runtime.quality import intervention_substrate as owner

    bundle = owner.load_l6_intervention_substrate(ROOT)
    raw = bundle.knob_dictionary["budget_allocation_multiplier"]
    atom, binding = owner._resolve_owner_atom_world_binding(bundle=bundle, operator_kind="budget_allocation_multiplier", raw_knob=raw, parameter_value=1.25)
    candidate = SimpleNamespace(candidate_id="research-owner-atom", atom=atom)
    problem = SimpleNamespace(outcome_of_interest=SimpleNamespace(target_variable="government.balance", metric_id="government.balance"), problem_statement="Estimate the budget allocation effect")
    broken = copy.deepcopy(bundle.observation_manifest)
    for row in broken["routes"]:
        row["target_contract"] = {"contract_id": "census.nonexistent.contract", "contract_fqn": "census.NonexistentContract"}
    fake_bundle = owner.replace_intervention_substrate_bundle(bundle, update={"observation_manifest": broken})
    results = {}
    for name, current in [("real", bundle), ("fake_targets", fake_bundle)]:
        with patch.object(consumer, "load_l6_intervention_substrate", return_value=current):
            results[name] = [row.model_dump(mode="json") for row in consumer.rank_shadow_candidates_with_graph_causal_surrogate((candidate,), design_problem=problem, repo_root=ROOT)]
    emit({"scope": "Actual rank function with a real N2-owner-produced atom; research candidate wrapper is candidate-only and is not a governed design", "world_binding": binding.model_dump(mode="json"), "rankings": results, "identical": results["real"] == results["fake_targets"]})
    assert results["real"] == results["fake_targets"]


def source_census() -> None:
    import os
    source = ROOT / "src"
    first = {str(path.relative_to(ROOT)) for path in source.rglob("*.py") if path.is_file()}
    second = {str((Path(parent) / name).relative_to(ROOT)) for parent, _dirs, files in os.walk(source) for name in files if name.endswith(".py")}
    terms = ("observation_to_contract_manifest", "route_observation_family_method", "_observation_manifest_families", "intervention_substrate")
    findings = {}
    unreadable = []
    for term in terms:
        matches = []
        for relative in sorted(first):
            try:
                lines = (ROOT / relative).read_text().splitlines()
            except (OSError, UnicodeError) as error:
                unreadable.append({"path": relative, "ambiguous": str(error)})
                continue
            matched = [{"line": number, "text": text} for number, text in enumerate(lines, 1) if term in text]
            if matched:
                matches.append({"path": relative, "matches": matched})
        independent = []
        for relative in sorted(second):
            try:
                if term in (ROOT / relative).read_text():
                    independent.append(relative)
            except (OSError, UnicodeError):
                pass
        findings[term] = {"matches": matches, "independent_identity_set": independent, "symmetric_difference": sorted({row["path"] for row in matches} ^ set(independent))}
    emit({"file_type_denominator": "All regular *.py files recursively under src/", "denominator_identity_set": sorted(first), "independent_denominator_identity_set": sorted(second), "denominator_symmetric_difference": sorted(first ^ second), "unreadable": unreadable, "findings": findings})
    assert first == second
    assert not unreadable


def statute_content() -> None:
    from polisyos.lex.knowledge.store import LegalKnowledgeStore
    from polisyos.runtime.quality.intervention_substrate import DEFAULT_L3_LEX_DB_PATH, load_l6_intervention_substrate
    bundle = load_l6_intervention_substrate(ROOT)
    lex = LegalKnowledgeStore(ROOT / DEFAULT_L3_LEX_DB_PATH, (ROOT / DEFAULT_L3_LEX_DB_PATH).parent, canonical_db_ref_path=DEFAULT_L3_LEX_DB_PATH)
    results = []
    for entry in bundle.lex_authority_manifest["intervention_map_entries"]:
        threshold_id = entry["provision_ref"].split(":", 1)[1]
        threshold = lex.resolve_rule_threshold(threshold_id=threshold_id, as_of=entry["measurement_expectations"]["as_of"])
        assert threshold is not None
        details = threshold.model_dump(mode="json")
        provisions = lex.load_provisions_by_anchor(details["doc_id"], [details["provision_anchor"]])
        results.append({"law_token": entry["law_token"], "threshold": details, "resolved_provisions": [row.model_dump(mode="json") for row in provisions]})
    emit({"denominator": "Every entry in the tracked L6 lex_authority_manifest.intervention_map_entries", "results": results})


def statute_sql() -> None:
    import duckdb
    from polisyos.runtime.quality.intervention_substrate import DEFAULT_L3_LEX_DB_PATH, load_l6_intervention_substrate
    bundle = load_l6_intervention_substrate(ROOT)
    connection = duckdb.connect(str(ROOT / DEFAULT_L3_LEX_DB_PATH), read_only=True)
    schemas = {name: connection.execute("DESCRIBE " + name).fetchall() for name in ("lex_rule_thresholds", "lex_normative_facts", "lex_provisions")}
    results = []
    for entry in bundle.lex_authority_manifest["intervention_map_entries"]:
        identity = entry["provision_ref"].split(":", 1)[1]
        query = "SELECT t.*, f.*, p.* FROM lex_rule_thresholds t LEFT JOIN lex_normative_facts f ON f.fact_id=t.fact_id LEFT JOIN lex_provisions p ON p.doc_id=f.doc_id AND p.anchor_path=f.provision_anchor WHERE t.threshold_id=?"
        cursor = connection.execute(query, [identity])
        names = [row[0] for row in cursor.description]
        values = cursor.fetchall()
        results.append({"law_token": entry["law_token"], "threshold_id": identity, "sql": query, "columns": names, "rows": values})
    emit({"denominator": "Every owner binding entry, exact threshold IDs, complete SQL result rows and columns with no LIMIT", "schemas": schemas, "results": results})


def real_but_unrelated_law_target() -> None:
    from polisyos.lex.knowledge.store import LegalKnowledgeStore
    from polisyos.runtime.quality import intervention_substrate as owner
    bundle = owner.load_l6_intervention_substrate(ROOT)
    lex = LegalKnowledgeStore(ROOT / owner.DEFAULT_L3_LEX_DB_PATH, (ROOT / owner.DEFAULT_L3_LEX_DB_PATH).parent, canonical_db_ref_path=owner.DEFAULT_L3_LEX_DB_PATH)
    authority = copy.deepcopy(bundle.lex_authority_manifest)
    # Keep law/knob declarations, transpose targets to preserve registry target-key uniqueness.
    for row in authority["intervention_map_entries"]:
        if row["law_token"] == "tax_relief_statute":
            row["provision_ref"] = "lex_rule_thresholds:a5429abb6621acb11ed10b20"
        elif row["law_token"] == "budget_law":
            row["provision_ref"] = "lex_rule_thresholds:01539d8d9b8cfedb489d689e"
    changed = owner.replace_intervention_substrate_bundle(bundle, update={"lex_authority_manifest": authority})
    original = owner.resolve_law_bound_lever(bundle, law_token="tax_relief_statute", knob_id="tax_relief_rate", parameter_value=0.24, legal_store=lex)
    substituted = owner.resolve_law_bound_lever(changed, law_token="tax_relief_statute", knob_id="tax_relief_rate", parameter_value=0.24, legal_store=lex)
    emit({"scope": "Counterexample to semantic law-knob correspondence, not an authoritative legal determination", "input_change": "Budget and tax provision targets transposed, preserving unique registry target keys and every law/knob/as_of/unit declaration; tax_relief_statute now targets real privatization-state-share threshold", "original": original.model_dump(mode="json"), "substituted": substituted.model_dump(mode="json")})
    assert substituted.status == "admissible"


def contract_diff() -> None:
    from tools.quality.validation import check_layer3_gy_intervention_substrate_contract as gate
    live = gate.build_live_payload(ROOT)
    committed = json.loads((ROOT / gate.OUTPUT_PATH).read_text())
    def flatten(value, path=()):
        if isinstance(value, dict):
            if not value:
                return {path: {"empty_object": True}}
            return {k: v for key, child in value.items() for k, v in flatten(child, (*path, key)).items()}
        if isinstance(value, list):
            if not value:
                return {path: {"empty_array": True}}
            return {k: v for key, child in enumerate(value) for k, v in flatten(child, (*path, key)).items()}
        return {path: {"value": value}}
    left = flatten(committed)
    right = flatten(live)
    differences = []
    for identity in sorted(set(left) | set(right), key=str):
        if identity not in left or identity not in right or left[identity] != right[identity]:
            differences.append({"identity": list(identity), "committed": left[identity] if identity in left else {"absent": True}, "live": right[identity] if identity in right else {"absent": True}})
    emit({"source": gate.OUTPUT_PATH, "complete_leaf_identity_sets": {"committed": [list(key) for key in sorted(left, key=str)], "live": [list(key) for key in sorted(right, key=str)]}, "differences": differences, "live": live})


def mapping_schema() -> None:
    import ast
    artifacts = {}
    for relative, names in [
        ("src/polisyos/runtime/quality/intervention_substrate.py", ("LawAuthorityRef", "LawLeverResolution")),
        ("src/polisyos/lex/intervention_artifacts.py", ("LexInterventionMapEntry", "LexProvisionMappingRegistry")),
    ]:
        source = (ROOT / relative).read_text()
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in names:
                fields = sorted(item.target.id for item in node.body if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name))
                independent = sorted({child.target.id for child in ast.walk(node) if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name) and child.col_offset == node.col_offset + 4})
                artifacts[node.name] = {"path": relative, "fields": fields, "independent_fields": independent, "symmetric_difference": sorted(set(fields) ^ set(independent)), "complete_source": ast.get_source_segment(source, node)}
    declaration_path = ROOT / "architecture/policy_design_case/layer3_gy_l6_owner_authority_bindings.json"
    declaration = json.loads(declaration_path.read_text())
    emit({"scope": "Complete declared field sets in the live LawAuthorityRef/LawLeverResolution/LexInterventionMapEntry and complete LexProvisionMappingRegistry owner source; no tree-wide absence claim", "models": artifacts, "complete_owner_declaration": declaration})


if __name__ == "__main__":
    {"routing": routing, "behavior": behavior, "law_registry": law_registry, "decisive_removal": decisive_removal, "n4_routing": n4_routing, "source_census": source_census, "statute_content": statute_content, "statute_sql": statute_sql, "real_but_unrelated_law_target": real_but_unrelated_law_target, "contract_diff": contract_diff, "mapping_schema": mapping_schema}[sys.argv[1]]()
