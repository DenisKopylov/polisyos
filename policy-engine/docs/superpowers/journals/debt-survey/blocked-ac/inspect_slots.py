"""Read pinned slot/consumer bodies and reconcile the DS5 subject table.

This is a measurement script, not a validator or a capability-closure gate.
Static calls are occurrences; dynamic reachability requires an existing test.
"""

import argparse
import ast
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[5]
BASE = "fc823071a7b6f2c9a573172aec3499ad6d138c0f"
spec = importlib.util.spec_from_file_location("survey_tree", Path(__file__).parent.parent / "open/inspect_tree.py")
tree_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tree_module)


def read(path):
    return subprocess.check_output(["git", "show", f"{BASE}:policy-engine/{path}"], cwd=ROOT, text=True)


GROUPS = {
    "public": [
        ("src/polisyos/runtime/http/routes/public_decisions.py", ".*"),
        ("src/polisyos/runtime/http/services/public_decision_verification_contracts.py", ".*"),
        ("src/polisyos/runtime/quality/global_case_index.py", ".*"),
        ("src/polisyos/runtime/quality/capability_discovery.py", "GlobalCaseIndexCapabilityDiscoveryProvider"),
        ("src/polisyos/runtime/http/services/public_decision_verification_configuration.py", "build_public_decision_verification_service"),
    ],
    "claim": [
        ("src/polisyos/scientist/evidence/claims/head_index.py", "build_default_claim_ledger_owner|UnappointedClaimLedgerOwner|append_verified_owner_event"),
        ("src/polisyos/scientist/evidence/claims/owner_events.py", "ClaimSupersessionAuthority|ClaimSupersessionAppointment|produce_claim_supersession_owner_event|resolve_claim_supersession_owner_event"),
        ("src/polisyos/scientist/governance/continuous/lifecycle_bridge.py", "bridge_monitor_event"),
    ],
    "epoch": [
        ("src/polisyos/runtime/quality/epoch_validity_cascade.py", "EpochValidityTransitionProducer|EpochDependencyDenominatorProvider|EpochPerturbationAdjudicationProvider|NoEpochTransitionSigningAuthority"),
        ("src/polisyos/scientist/validation/decision_validity.py", "NoEpochTransitionVerifier|__init__|apply_epoch_validity_transition|_resolve_epoch_target_denominator"),
        ("src/polisyos/runtime/quality/epoch_denominator_reconciliation.py", "EpochTransitionDenominatorReconciliationReader|_require_appointment"),
    ],
    "promotion": [
        ("src/polisyos/runtime/quality/promotion_sequence.py", "_eval_safety_obligation|CanonicalN9PromotionPort|_load_persisted_value_receipt"),
        ("src/polisyos/runtime/quality/generation_cycle.py", "ValueGateReceipt|ValuePortObservation|FoundryValuePort|_DefaultSimulationBoundFoundryValuePort|_blocked_value_observation"),
        ("src/polisyos/runtime/quality/evaluation_safety.py", "EvalSafetyCertificate"),
    ],
    "mandate": [
        ("src/polisyos/runtime/quality/agent_action_authority.py", "CurrentMandateOwnerEvidence|_resolve_current_mandate_authority|resolve_delegation_contract"),
        ("src/polisyos/runtime/http/services/acquisition_action_service.py", "AcquisitionAuthorityGatewayProvider|_require_authority_provider|__init__|request_decision|execute"),
        ("src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py", "AgentActionDelegationContract"),
        ("src/polisyos/runtime/http/app.py", "create_runtime_api_app"),
        ("src/polisyos/runtime/http/container.py", "RuntimeContainerOverrides"),
    ],
    "a11y": [
        ("src/polisyos/scientist/evidence/claims/posture.py", "AccessibilityEvidenceKind|AccessibilityPurpose|AccessibilityDocumentBinding|_validate_fixed_semantic_bindings"),
    ],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("group", choices=[*GROUPS, "ds5", "c13", "authority"])
    args = parser.parse_args()
    output = {"base": BASE, "group": args.group}
    if args.group in GROUPS:
        records = []
        for path, regex in GROUPS[args.group]:
            try:
                text = read(path)
            except subprocess.CalledProcessError:
                records.append({"path": path, "present": False})
                continue
            parsed = ast.parse(text)
            chosen = [n for n in ast.walk(parsed) if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and re.fullmatch(regex, n.name)]
            # Suppress a child already printed as part of a selected parent.
            chosen = [n for n in chosen if not any(p is not n and p.lineno <= n.lineno and n.end_lineno <= p.end_lineno for p in chosen)]
            records.append({"source": f"{path}@{BASE}", "selected_definitions": [
                {"kind": type(n).__name__, "name": n.name, "line": n.lineno,
                 "body": ast.get_source_segment(text, n)} for n in chosen]})
        output["records"] = records
        inventory = tree_module.ast_inventory()
        names = {
            "epoch": r"EpochValidityTransitionProducer|\.produce_and_persist$|resolve_complete_epoch_dependencies|resolve_complete_owner_adjudications|DecisionValidityService|epoch_transition_verifier|epoch_denominator_reconciliation_reader",
            "claim": r"ClaimSupersessionAuthority|produce_claim_supersession_owner_event|build_default_claim_ledger_owner|append_verified_owner_event|owner_event_authority",
            "promotion": r"ValueGateReceipt|CanonicalN9PromotionPort|ValuePortObservation|persist_effect_obligation|persist_measurement_root|persist_effective_independence|Promotion.*Safety|Safety.*Promotion",
            "public": r"GlobalCaseIndexProducer|GlobalCaseIndexCapabilityDiscoveryProvider|build_public_decision_verification_service|promoted_record",
            "mandate": r"mandate.*[Pp]rovider|[Dd]elegation.*[Pp]rovider|CurrentMandateOwnerEvidence|AgentActionDelegationContract",
            "a11y": r"[Cc]ountersign|AccessibilityDocumentBinding|accessibility_document",
        }[args.group]
        source = [r for r in inventory["records"] if r["path"].startswith("src/") and re.search(names, r["name"])]
        output["source_ast"] = {"file_type": ".py", "path_denominator": "src/**/*.py",
            "file_count": len([p for p in inventory["paths"] if p.startswith("src/")]),
            "path_identity_crosscheck": "git ls-tree == os.walk; ast.walk == NodeVisitor",
            "parse_ambiguities": inventory["ambiguities"], "query": names,
            "occurrences_by_package": dict(sorted(Counter(r["path"].split("/")[2] for r in source).items())),
            "occurrences": source}
    elif args.group == "ds5":
        path = "docs/plans/active/atlas-slices/DS5-enforcement-waist.md"
        text = read(path)
        section = text.split("| Direct-`Badge` debt group |", 1)[1].split("\n\n", 1)[0]
        first = []
        for line in section.splitlines()[2:]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            first.append({"group": cells[0], "sites": int(cells[1]), "slice": cells[2], "states": cells[3], "signal": cells[4]})
        second = [(m.group(1).strip(), int(m.group(2)), m.group(3)) for m in re.finditer(r"^\| ([^|]+) \| (\d+) \| (DS\d+) \|", text, re.M)]
        assert sorted((r["group"], r["sites"], r["slice"]) for r in first) == sorted(second)
        output.update(source=f"{path}@{BASE}", denominator="entire direct-Badge Markdown table; one .md file",
                      identity_crosscheck="table-cell parser equals independent anchored row regex",
                      groups=len(first), sites=sum(r["sites"] for r in first),
                      distribution={s: {"groups": sum(r["slice"] == s for r in first), "sites": sum(r["sites"] for r in first if r["slice"] == s)} for s in sorted({r["slice"] for r in first})},
                      historical_handoffs=[r for r in first if r["slice"] in {"DS12", "DS14", "DS15", "DS18"}])
    elif args.group == "c13":
        schema_path = "architecture/atlas_surfaces/frontend-disposition-register.schema.json"
        schema = json.loads(read(schema_path))
        checker = read("architecture/atlas_surfaces/check_frontend_disposition_register.py")
        parsed = ast.parse(checker)
        constants = {n.targets[0].id: ast.literal_eval(n.value) for n in parsed.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in {"C13_RECEIPT_REF", "C13_RECEIPT_START", "C13_RECEIPT_END"}}
        journal = read(constants["C13_RECEIPT_REF"])
        receipt = json.loads(journal.split(constants["C13_RECEIPT_START"])[1].split(constants["C13_RECEIPT_END"])[0])
        output.update(schema_source=f"{schema_path}@{BASE}", schema= schema["$defs"]["ds18TimeSemanticsLineage"],
                      receipt_source=f'{constants["C13_RECEIPT_REF"]}@{BASE}', receipt_fields=list(receipt),
                      binding_fields={k:v for k,v in receipt.items() if "binding" in k})
        output["complete_binding_comparison"] = {}
        for key in ["source_bindings", "producer_bindings"]:
            compared = []
            for binding in receipt[key]:
                raw = subprocess.check_output(["git", "show", f'{BASE}:policy-engine/{binding["path"]}'], cwd=ROOT)
                current = hashlib.sha256(raw).hexdigest()
                compared.append({"path": binding["path"], "expected": binding["sha256"], "actual": current, "matches": current == binding["sha256"]})
            assert len({r["path"] for r in compared}) == len(compared)
            output["complete_binding_comparison"][key] = {"denominator": len(compared), "current": sum(r["matches"] for r in compared), "rows": compared}
        selected = [n for n in ast.walk(parsed) if isinstance(n, ast.FunctionDef) and n.name in {"_c13_independent_print_receipt", "_c13_receipt_shape_errors", "_validate_c13_print_roots"}]
        output["reader_bodies"] = [{"name": n.name, "line": n.lineno, "body": ast.get_source_segment(checker, n)} for n in selected]
    else:
        path = "docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md"
        text = read(path)
        sections = {}
        for name in ["DS12", "DS14"]:
            heading = re.search(rf"^#### {name} — .+$", text, re.M)
            end = re.search(r"^####? ", text[heading.end():], re.M)
            sections[name] = text[heading.start(): heading.end() + end.start() if end else len(text)]
        output.update(source=f"{path}@{BASE}", frontmatter=text.split("---", 2)[1] if text.startswith("---") else "no frontmatter", sections=sections)
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
