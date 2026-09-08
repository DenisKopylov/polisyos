"""Complete registry input-contract and native-output identity reconciliation."""
from __future__ import annotations

import json
import typing
from pathlib import Path

from polisyos.foundry.extensions.registry import controlled_builtin_foundry_method_registry_scope
from polisyos.foundry.methods.catalog.snapshot import build_method_catalog_snapshot
from polisyos.foundry.methods.selection.advisor import (
    _catalog_entry_is_value_method, method_accepts_input_contract,
)
from polisyos.runtime.quality import intervention_substrate as owner


def main() -> None:
    root = Path(__file__).resolve().parents[5]
    bundle = owner.load_l6_intervention_substrate(root)
    contracts = {row["family"]: row["target_contract"]["contract_id"]
                 for row in bundle.observation_manifest["routes"]}
    first = {key: set() for key in contracts}
    second = {key: set() for key in contracts}
    ambiguous = []
    with controlled_builtin_foundry_method_registry_scope() as (registry, _report):
        signatures = registry.list_all()
        catalog = build_method_catalog_snapshot(registry=registry)
        native = {entry.fqn for entry in catalog.entries
                  if _catalog_entry_is_value_method(entry, registry=registry)}
        for signature in signatures:
            try:
                method = registry.get(signature.fqn)
            except Exception as exc:
                ambiguous.append({"method": signature.fqn, "reason": str(exc)})
                continue
            ids = {slot.contract_id for slot in method.signature.input_slots if slot.contract_id}
            for function_name, argument in (("materialize_input", "return"), ("pure_step", "state")):
                function = getattr(method, function_name, None)
                if function is None:
                    continue
                try:
                    stack = [typing.get_type_hints(function).get(argument)]
                except (AttributeError, TypeError, NameError) as exc:
                    ambiguous.append({"method": signature.fqn, "function": function_name,
                                      "reason": str(exc)})
                    continue
                while stack:
                    item = stack.pop()
                    if getattr(item, "contract_id", None):
                        ids.add(item.contract_id)
                    stack.extend(typing.get_args(item))
            for family, contract_id in contracts.items():
                if method_accepts_input_contract(method, contract_id):
                    first[family].add(signature.fqn)
                if contract_id in ids:
                    second[family].add(signature.fqn)
        report = {"registry_identity_set": sorted(signature.fqn for signature in signatures),
                  "catalog_identity_set": sorted(entry.fqn for entry in catalog.entries),
                  "native_value_identity_set": sorted(native), "ambiguous": ambiguous,
                  "routes": {family: {"contract_id": contracts[family],
                      "owner_input_method_ids": sorted(first[family]),
                      "independent_input_method_ids": sorted(second[family]),
                      "native_intersection": sorted(first[family] & native),
                      "first_only": sorted(first[family]-second[family]),
                      "second_only": sorted(second[family]-first[family])} for family in contracts}}
        print(json.dumps(report, indent=2))
        assert report["registry_identity_set"] == report["catalog_identity_set"]
        assert first == second


if __name__ == "__main__":
    main()
