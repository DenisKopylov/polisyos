"""Record the full actual registry census through the default causal selector."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from _build.gy_gaps.c1_followup_probe import _canonical_factory
from polisyos.foundry.methods import MethodRegistry
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.workspace import loop


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    source = root / "tools/quality/validation/check_layer3_gy_phase2_artifacts.py"
    problem = _canonical_factory(source, DesignProblem)(verification_required=True)
    result = loop._phase2_value_method_selection(problem.to_workspace_intent(), design_problem=problem)
    print(json.dumps({"selection": result, "request_owner": str(source.relative_to(root)),
                      "request_owner_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                      "request_factory_arguments": {"verification_required": True}}, sort_keys=True))
    registry = MethodRegistry.get_instance()
    by_list = {item.fqn: item.stable_digest() for item in registry.list_all()}
    snapshot = registry.snapshot()
    snapshot_entries = tuple(snapshot.entries())
    by_snapshot = {item.fqn: item.signature.stable_digest() for item in snapshot_entries}
    by_selection = {item["method_fqn"]: item["signature_digest"] for item in result["candidates"]}
    print(json.dumps({"reconciliation": {
        "list_all_count": len(registry.list_all()), "snapshot_entry_count": len(snapshot_entries),
        "candidate_count": len(result["candidates"]),
        "selection_vs_list_added": sorted(set(by_selection) - set(by_list)),
        "selection_vs_list_lost": sorted(set(by_list) - set(by_selection)),
        "snapshot_vs_list_added": sorted(set(by_snapshot) - set(by_list)),
        "snapshot_vs_list_lost": sorted(set(by_list) - set(by_snapshot)),
        "signature_mismatches": sorted(key for key in set(by_selection) & set(by_list) if by_selection[key] != by_list[key]),
        "complete_identity_and_digest_agreement": by_list == by_snapshot == by_selection,
        "authority_scope": "candidate_search_only"}}, sort_keys=True))
    assert result["denominator"] == sorted(by_list)
    assert by_list == by_snapshot == by_selection
    assert result["denominator_established"] is True
    assert not result["registry_bridge_errors"] and not result["registry_discovery_errors"]
    assert result["registry_bootstrap_error"] is None
    assert result["status"] == "selected", result["blockers"]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
