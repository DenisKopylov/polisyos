from __future__ import annotations

from typing import Any

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_capabilities import (
    _CAUSAL_CAPABILITY_CONTRACT_OWNER,
    CausalCapabilityContract,
    load_causal_capability_contract,
    persist_causal_capability_contract,
)
from polisyos.ir.analytics.dual_certificate import hydrate_bounds_bundle_with_dual_certificate
from polisyos.ir.analytics.partial_identification import BoundsBundle
from polisyos.ir.artifacts import put_json_artifact
from polisyos.ir.artifacts.io import _put_owned_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation
from polisyos.ir.registry.refs import CausalCapabilityContractRef


class _CountingCAS(FileSystemCAS):
    """Count byte reads and JSON writes at the store boundary."""

    def __init__(self, root) -> None:
        super().__init__(root)
        self.payload_reads = 0
        self.json_writes = 0

    def get_bytes(self, artifact_id):
        self.payload_reads += 1
        return super().get_bytes(artifact_id)

    def put_json(
        self,
        obj: object,
        opts: Any,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ):
        self.json_writes += 1
        return super().put_json(
            obj,
            opts,
            canon_spec,
            return_selected_profile=return_selected_profile,
        )


def _capability(*, dependency_fingerprint: str = "unseen-method-instance:runner-v2"):
    return CausalCapabilityContract(dependency_fingerprint=dependency_fingerprint)


def test_owner_family_roundtrip_accepts_unseen_resource_without_resource_registry(
    tmp_path,
) -> None:
    cas_root = tmp_path / "owner-roundtrip"
    store = ensure_ir_artifact_store(_CountingCAS(cas_root))
    source = _capability()

    ref = persist_causal_capability_contract(store, source)
    fresh_store = ensure_ir_artifact_store(FileSystemCAS(cas_root))
    loaded = load_causal_capability_contract(fresh_store, ref)

    assert loaded == source
    assert loaded.dependency_fingerprint == "unseen-method-instance:runner-v2"


def test_owner_write_refuses_malformed_constructed_dto_before_cas(tmp_path) -> None:
    store = _CountingCAS(tmp_path / "invalid-constructed")
    invalid = CausalCapabilityContract.model_construct(schema_version="1.0")

    with pytest.raises(CanonViolation, match="ir_owned_artifact_source_invalid"):
        persist_causal_capability_contract(ensure_ir_artifact_store(store), invalid)

    assert store.json_writes == 0


@pytest.mark.parametrize("bad_version", ["", False, 0, None])
def test_owner_write_does_not_treat_malformed_override_as_absence(
    tmp_path, bad_version: object
) -> None:
    store = _CountingCAS(tmp_path / f"invalid-override-{type(bad_version).__name__}")
    with pytest.raises(CanonViolation, match="ir_owned_artifact_write_override_invalid"):
        persist_causal_capability_contract(
            ensure_ir_artifact_store(store),
            _capability(),
            schema_version=bad_version,  # type: ignore[arg-type]
        )

    assert store.json_writes == 0


@pytest.mark.parametrize("bad_name", ["", False, 0, None])
def test_owner_write_does_not_treat_malformed_schema_name_as_absence(
    tmp_path, bad_name: object
) -> None:
    store = _CountingCAS(tmp_path / f"invalid-schema-name-{type(bad_name).__name__}")
    with pytest.raises(CanonViolation, match="ir_owned_artifact_write_override_invalid"):
        persist_causal_capability_contract(
            ensure_ir_artifact_store(store),
            _capability(),
            schema_name=bad_name,  # type: ignore[arg-type]
        )

    assert store.json_writes == 0


def test_typed_reader_refuses_unregistered_history_before_payload_read(tmp_path) -> None:
    store = _CountingCAS(tmp_path / "unknown-history")
    raw_ref = put_json_artifact(
        ensure_ir_artifact_store(store),
        {"schema_version": "9.0", "dependency_fingerprint": "opaque-history"},
        kind="ir.causal_capability_contract",
        schema_name="ir.causal_capability_contract",
        schema_version="9.0",
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    store.payload_reads = 0

    with pytest.raises(
        CanonViolation,
        match="ir_owned_artifact_representation_unregistered",
    ):
        load_causal_capability_contract(
            ensure_ir_artifact_store(store),
            CausalCapabilityContractRef.model_validate(raw_ref),
        )

    assert store.payload_reads == 0


def test_typed_reader_rejects_wrong_profile_before_payload_and_bad_dto_after_decode(
    tmp_path,
) -> None:
    cas_root = tmp_path / "wrong-profile"
    store = _CountingCAS(cas_root)
    source = _capability()
    wrong_profile_ref = put_json_artifact(
        ensure_ir_artifact_store(store),
        source.model_dump(mode="json"),
        kind="ir.causal_capability_contract",
        schema_name="ir.causal_capability_contract",
        schema_version="1.0",
        canon_spec=CanonSpec(),
        return_selected_profile=True,
    )
    store.payload_reads = 0

    with pytest.raises(CanonViolation, match="ir_owned_artifact_profile_refused"):
        load_causal_capability_contract(
            ensure_ir_artifact_store(store),
            CausalCapabilityContractRef.model_validate(wrong_profile_ref),
        )

    assert store.payload_reads == 0

    malformed_payload_ref = put_json_artifact(
        ensure_ir_artifact_store(store),
        {
            **source.model_dump(mode="json"),
            "unregistered_extra": "must be rejected by the owner DTO",
        },
        kind="ir.causal_capability_contract",
        schema_name="ir.causal_capability_contract",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    store.payload_reads = 0

    with pytest.raises(CanonViolation, match="ir_owned_artifact_source_invalid"):
        load_causal_capability_contract(
            ensure_ir_artifact_store(store),
            CausalCapabilityContractRef.model_validate(malformed_payload_ref),
        )

    assert store.payload_reads == 1


@pytest.mark.parametrize(
    "payload",
    [
        {
            "schema_version": "1.0",
            "dependency_fingerprint": "valid",
            "unregistered_extra": "refuse-before-cas",
        },
        {"schema_version": "1.0"},
    ],
)
def test_owner_write_revalidates_actual_mapping_before_cas(tmp_path, payload) -> None:
    store = _CountingCAS(tmp_path / "malformed-source-mapping")
    with pytest.raises(CanonViolation, match="ir_owned_artifact_source_invalid"):
        _put_owned_json_artifact(
            ensure_ir_artifact_store(store),
            payload,
            owner=_CAUSAL_CAPABILITY_CONTRACT_OWNER,
            schema_name="ir.causal_capability_contract",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
        )

    assert store.json_writes == 0


@pytest.mark.parametrize("bad_inputs", [False, 0])
def test_dual_certificate_intake_does_not_normalize_malformed_inputs_to_absence(
    tmp_path, bad_inputs: object
) -> None:
    raw_store = _CountingCAS(tmp_path / f"invalid-lineage-{type(bad_inputs).__name__}")
    store = ensure_ir_artifact_store(raw_store)
    bundle = BoundsBundle(lower_bound=0.0, upper_bound=1.0)

    with pytest.raises(TypeError):
        hydrate_bounds_bundle_with_dual_certificate(
            store,
            bundle,
            None,
            inputs=bad_inputs,  # type: ignore[arg-type]
        )

    assert raw_store.json_writes == 0
