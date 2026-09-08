"""Read-only registry output-contract map; no method is executed or certified."""

from __future__ import annotations

import inspect
import json

from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.selection.registry import MethodRegistry


def main():
    registry = MethodRegistry.get_instance()
    report = ensure_all_methods_registered(registry)
    primary = {signature.fqn: signature for signature in registry.list_all()}
    secondary = {fqn: registry.get_signature(fqn) for fqn in registry}
    assert set(primary) == set(secondary)
    primary_slots = {
        fqn: frozenset(slot.name for slot in signature.output_slots)
        for fqn, signature in primary.items()
    }
    secondary_slots = {
        fqn: frozenset(slot.name for slot in signature.output_slots)
        for fqn, signature in secondary.items()
    }
    assert primary_slots == secondary_slots
    selected = {
        fqn: slots for fqn, slots in primary_slots.items()
        if {"hte_result", "policy_recommendation"} & slots
    }
    both = sorted(
        fqn for fqn, slots in primary_slots.items()
        if {"hte_result", "policy_recommendation"} <= slots
    )
    print(json.dumps({
        "measurement": "declared_method_output_contracts_only_not_execution",
        "denominator": {"list_all_methods": len(primary), "iteration_signature_lookup": len(secondary)},
        "method_and_slot_identity_sets_equal": True,
        "both_hte_and_recommendation": both,
        "bootstrap_report": report.model_dump(mode="json") if hasattr(report, "model_dump") else str(report),
    }, sort_keys=True))
    for fqn, slots in sorted(selected.items()):
        cls = registry.get(fqn)
        print(json.dumps({
            "fqn": fqn,
            "output_slots": sorted(slots),
            "source": inspect.getsourcefile(cls),
            "source_line": inspect.getsourcelines(cls)[1],
        }, sort_keys=True))


if __name__ == "__main__":
    main()
