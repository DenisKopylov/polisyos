"""Observe complete current staged-ref identities without changing the gate."""

from __future__ import annotations

import hashlib
import json


def main() -> None:
    import pytest

    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.workspace import scientist_node_adapters as adapter
    from tests.unit.runtime.quality import test_workspace_foundry_consumption as cases

    original = cases._staged_method_case
    original_read = adapter._read_binding

    def describe(store, ref):
        typed = ArtifactRef.model_validate(ref)
        raw = store.get_bytes(typed.artifact_id)
        return {
            "offered_ref": typed.model_dump(mode="json"),
            "actual_manifest": store.get_manifest(typed.artifact_id).model_dump(mode="json", by_alias=True),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "raw_byte_size": len(raw),
        }

    def observe_case(*args, **kwargs):
        case = original(*args, **kwargs)
        store, bound, state, _, _ = case
        refs = {"recorded_observations": bound.observational_data_ref,
                "recorded_binding": bound.binding_receipt_ref,
                **{"inputs." + key: value for key, value in state.inputs.items()},
                **{"artifacts_index." + key: value for key, value in state.artifacts_index.items()}}
        print("INTAKE_IDENTITY_OBSERVER " + json.dumps({
            "scope": "every top-level artifact ref in this actual controlled input state plus recorded binding/root",
            "complete_members": {key: describe(store, value) for key, value in refs.items()},
        }, sort_keys=True))
        return case

    def observe_read(store, ref, path):
        try:
            return original_read(store, ref, path)
        except Exception:
            print("INTAKE_READ_FAILURE " + json.dumps({"path": path, **describe(store, ref)}, sort_keys=True))
            raise

    cases._staged_method_case = observe_case
    adapter._read_binding = observe_read
    raise SystemExit(pytest.main([
        "-q", "-s", "--tb=short",
        "tests/unit/runtime/quality/test_workspace_foundry_consumption.py::test_staged_intake_real_owner_is_consumed_without_weakening_measurement",
        "tests/unit/runtime/quality/test_workspace_foundry_consumption.py::test_workspace_phase2_transports_verified_staged_input_owner_refs",
    ]))


if __name__ == "__main__":
    main()
