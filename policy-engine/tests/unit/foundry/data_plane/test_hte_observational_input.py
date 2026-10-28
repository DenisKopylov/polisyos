from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.common.canonical_profile import require_declared_profile
from polisyos.core.artifacts import (
    CoreJsonReadBoundsRefusalError,
    CoreJsonReadLimits,
    read_core_json_artifact_bounded,
    read_core_manifest_profile_bounded,
)
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    ArtifactTenantContextInfo,
    CanonInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.foundry.data_plane import (
    HTE_PHYSICAL_SOURCE_BINDING_KIND,
    HTE_PHYSICAL_SOURCE_BINDING_SCHEMA,
    HTEInputLimits,
    HTEInputPreparationRefusal,
    HTEPhysicalSourceMaterializationBinding,
    load_hte_physical_source_materialization_binding,
    prepare_hte_observational_input,
)
from polisyos.foundry.data_plane.bindings import (
    _persist_hte_physical_source_binding,
)
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.ir.observation.bundles import (
    HTE_OBSERVATIONAL_DATA_CONTRACT_ID,
    HTE_OBSERVATIONAL_DATA_TARGET,
    OBSERVATION_METHOD_INPUT_KIND,
    OBSERVATION_METHOD_INPUT_SCHEMA_NAME,
    OBSERVATION_METHOD_INPUT_SCHEMA_VERSION,
    ObservationMethodInputEnvelope,
)

_METHOD_FQN = "causal.treatment_effects.aipw@1.0.0"
_SOURCE_SCHEMA = SchemaInfo(name="polisyos.test.HTEObservations", version="1.0")
_ENVELOPE_SCHEMA = SchemaInfo(
    name=OBSERVATION_METHOD_INPUT_SCHEMA_NAME,
    version=OBSERVATION_METHOD_INPUT_SCHEMA_VERSION,
)
_RESTRICTED = ArtifactGovernanceInfo(classification="restricted")


def _limits(**overrides: int) -> HTEInputLimits:
    values = {
        "max_manifest_bytes": 100_000,
        "max_bytes": 1_000_000,
        "max_depth": 64,
        "max_elements": 100_000,
    }
    values.update(overrides)
    return CoreJsonReadLimits(**values)


def _valid_payload(*, n_obs: int = 40) -> dict[str, Any]:
    return {
        "outcome": [float(index) / 10 for index in range(n_obs)],
        "treatment": [index % 2 for index in range(n_obs)],
        "covariates": [[float(index), float(index % 3)] for index in range(n_obs)],
        "confounders": [[float(index % 5)] for index in range(n_obs)],
        "feature_names": ["age", "baseline"],
        "confounder_names": ["risk"],
        "sample_ids": [f"sample-{index}" for index in range(n_obs)],
        "metadata": {"source": "synthetic_candidate"},
    }


def _put_source(
    store: FileSystemCAS,
    payload: dict[str, Any],
    *,
    kind: str,
    schema: SchemaInfo | None,
    governance: ArtifactGovernanceInfo | None = _RESTRICTED,
    canon_spec: CanonSpec | None = None,
    return_selected_profile: bool = True,
) -> ArtifactRef:
    ref = store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=schema,
            producer=ProducerInfo(
                component="tests.unit.foundry.data_plane.test_hte_observational_input",
                version="1.0",
            ),
            governance=governance,
            tenant_context=ArtifactTenantContextInfo(
                tenant_id="tenant-test",
                cell_id="cell-test",
            ),
        ),
        canon_spec=canon_spec
        or CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False),
        return_selected_profile=return_selected_profile,
    )
    assert isinstance(ref, ArtifactRef)
    return ref


def _envelope_payload(
    payload: dict[str, Any],
    *,
    target: Any = HTE_OBSERVATIONAL_DATA_TARGET,
) -> dict[str, Any]:
    return ObservationMethodInputEnvelope(
        contract_target=target,
        contract_payload=payload,
    ).model_dump(mode="json")


def _prepare(
    store: object,
    ref: ArtifactRef,
    *,
    protocol: str = "method_input_envelope_v1",
    limits: HTEInputLimits | None = None,
    materialization_binding_version: str | None = None,
):
    return prepare_hte_observational_input(
        store=store,  # type: ignore[arg-type]
        source_ref=ref,
        protocol=protocol,  # type: ignore[arg-type]
        method_fqn=_METHOD_FQN,
        limits=limits or _limits(),
        materialization_binding_version=materialization_binding_version,  # type: ignore[arg-type]
    )


def _put_envelope(
    store: FileSystemCAS,
    payload: dict[str, Any] | None = None,
    *,
    target: Any = HTE_OBSERVATIONAL_DATA_TARGET,
    schema: SchemaInfo | None = _ENVELOPE_SCHEMA,
    governance: ArtifactGovernanceInfo | None = _RESTRICTED,
    canon_spec: CanonSpec | None = None,
    return_selected_profile: bool = True,
) -> ArtifactRef:
    body = payload if payload is not None else _envelope_payload(_valid_payload(), target=target)
    return _put_source(
        store,
        body,
        kind=OBSERVATION_METHOD_INPUT_KIND,
        schema=schema,
        governance=governance,
        canon_spec=canon_spec,
        return_selected_profile=return_selected_profile,
    )


def _artifact_id_strings(store: FileSystemCAS) -> set[str]:
    """Return CAS IDs in their stable canonical wire representation."""
    return {str(artifact_id) for artifact_id in store.iter_artifact_ids()}


def test_canonical_envelope_is_materialized_and_reopened_by_fresh_reader(
    tmp_path: Path,
) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root, ownership_enforced=False)
    source_ref = _put_envelope(store)
    ids_before = _artifact_id_strings(store)

    prepared = _prepare(store, source_ref)

    assert isinstance(prepared.data, HTEObservationalData)
    assert prepared.data.n_obs == 40
    assert prepared.data.treatment.tolist() == [index % 2 for index in range(40)]
    assert prepared.submitted_ref == source_ref
    assert prepared.effective_ref == source_ref
    assert prepared.effective_ref.manifest_profile_sha256 == source_ref.manifest_profile_sha256
    assert prepared.effective_artifact_schema == _ENVELOPE_SCHEMA
    assert prepared.source_protocol == "method_input_envelope_v1"
    assert prepared.normalization == "canonical_passthrough"
    assert prepared.contract_target == HTE_OBSERVATIONAL_DATA_TARGET
    assert prepared.method_fqn == _METHOD_FQN
    assert prepared.observed_bytes > 0
    assert prepared.observed_manifest_bytes > 0
    assert prepared.observed_manifest_selection_bytes == prepared.observed_manifest_bytes
    assert prepared.observed_manifest_verification_bytes > 0
    assert prepared.observed_payload_bytes == prepared.observed_bytes
    assert prepared.observed_source_bytes == (
        prepared.observed_manifest_selection_bytes
        + prepared.observed_manifest_verification_bytes
        + prepared.observed_payload_bytes
    )
    assert prepared.payload_integrity_verified is True
    assert prepared.observed_depth > 0
    assert prepared.observed_elements > 0
    assert "candidate_input_not_external_truth" in prepared.limitations
    assert "scientific_validity_not_established" in prepared.limitations
    assert "units_and_context_not_established" in prepared.limitations
    assert prepared.source_governance == _RESTRICTED
    assert prepared.source_tenant_context == ArtifactTenantContextInfo(
        tenant_id="tenant-test",
        cell_id="cell-test",
    )
    assert _artifact_id_strings(store) == ids_before

    fresh_store = FileSystemCAS.open_existing_read_only(cas_root)
    fresh_read = read_core_json_artifact_bounded(
        fresh_store,
        prepared.effective_ref,
        limits=_limits(),
    )
    assert prepared.observed_manifest_bytes == fresh_read.observed_manifest_bytes
    assert (
        prepared.observed_manifest_selection_bytes == fresh_read.observed_manifest_selection_bytes
    )
    assert (
        prepared.observed_manifest_verification_bytes
        == fresh_read.observed_manifest_verification_bytes
    )
    assert prepared.observed_payload_bytes == fresh_read.observed_payload_bytes
    assert prepared.observed_source_bytes == fresh_read.observed_source_bytes
    fresh_payload = require_declared_profile(fresh_read.profile_read)
    assert fresh_payload["schema_version"] == "policyos.ir.observation.method_input_envelope.v1"
    assert fresh_payload["contract_target"]["contract_id"] == HTE_OBSERVATIONAL_DATA_CONTRACT_ID
    fresh_prepared = _prepare(fresh_store, prepared.effective_ref)
    assert fresh_prepared.data.n_obs == 40


def test_explicit_legacy_protocol_writes_profile_bound_envelope_and_fresh_reader_accepts_it(
    tmp_path: Path,
) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root, ownership_enforced=False)
    source_payload = _valid_payload()
    source_payload.update(
        {
            "confounders": None,
            "confounder_names": None,
            "feature_names": None,
            "sample_ids": None,
        }
    )
    source_ref = _put_source(
        store,
        source_payload,
        kind="ir.observational_data",
        schema=None,
    )
    selected_manifest = read_core_manifest_profile_bounded(
        store,
        source_ref,
        max_manifest_bytes=_limits().max_manifest_bytes,
    )
    ids_before = _artifact_id_strings(store)

    prepared = _prepare(store, source_ref, protocol="legacy_hte_json_v1")

    assert prepared.data.n_obs == 40
    assert prepared.submitted_ref == source_ref
    assert prepared.effective_ref != source_ref
    assert prepared.effective_ref.manifest_profile_sha256 is not None
    assert prepared.effective_artifact_schema == _ENVELOPE_SCHEMA
    assert prepared.observed_manifest_bytes == selected_manifest.observed_manifest_bytes
    assert prepared.observed_manifest_selection_bytes == prepared.observed_manifest_bytes
    assert prepared.observed_manifest_verification_bytes > 0
    assert prepared.observed_payload_bytes == prepared.observed_bytes
    assert prepared.observed_source_bytes == (
        prepared.observed_manifest_selection_bytes
        + prepared.observed_manifest_verification_bytes
        + prepared.observed_payload_bytes
    )
    assert prepared.payload_integrity_verified is True
    assert prepared.source_protocol == "legacy_hte_json_v1"
    assert prepared.normalization == "legacy_to_method_input_envelope_v1"
    assert "legacy_hte_json_v1_source_normalized" in prepared.limitations
    assert len(_artifact_id_strings(store) - ids_before) == 1

    fresh_store = FileSystemCAS.open_existing_read_only(cas_root)
    fresh_read = read_core_json_artifact_bounded(
        fresh_store,
        prepared.effective_ref,
        limits=_limits(),
    )
    fresh_payload = require_declared_profile(fresh_read.profile_read)
    assert fresh_payload["contract_payload"]["confounders"] is None
    assert fresh_payload["contract_payload"]["feature_names"] is None
    assert fresh_payload["contract_payload"]["sample_ids"] is None
    assert fresh_read.manifest.artifact_schema == _ENVELOPE_SCHEMA
    assert fresh_read.manifest.governance == _RESTRICTED
    assert fresh_read.manifest.tenant_context == ArtifactTenantContextInfo(
        tenant_id="tenant-test",
        cell_id="cell-test",
    )
    assert fresh_read.manifest.authority is None
    assert (
        InputRef(
            artifact_id=source_ref.artifact_id,
            role="legacy_hte_json_v1_source",
            manifest_profile_sha256=source_ref.manifest_profile_sha256,
        )
        in fresh_read.manifest.inputs
    )

    reparsed = _prepare(fresh_store, prepared.effective_ref)
    assert reparsed.data.n_obs == 40
    assert reparsed.data.confounders is None
    assert reparsed.data.feature_names is None
    assert reparsed.data.confounder_names is None
    assert reparsed.data.sample_ids is None
    assert reparsed.effective_ref == prepared.effective_ref


def test_legacy_source_without_governance_is_not_written_public_by_default(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_source(
        store,
        _valid_payload(),
        kind="ir.observational_data",
        schema=None,
        governance=None,
    )
    ids_before = _artifact_id_strings(store)

    with pytest.raises(HTEInputPreparationRefusal, match="source_governance_unavailable"):
        _prepare(store, source_ref, protocol="legacy_hte_json_v1")

    assert _artifact_id_strings(store) == ids_before


def test_legacy_source_requires_null_artifact_schema(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_source(
        store,
        _valid_payload(),
        kind="ir.observational_data",
        schema=_SOURCE_SCHEMA,
    )

    with pytest.raises(HTEInputPreparationRefusal, match="legacy_hte_schema_must_be_null"):
        _prepare(store, source_ref, protocol="legacy_hte_json_v1")


def test_selected_source_governance_requires_raw_declaration_not_typed_default(
    tmp_path: Path,
) -> None:
    import polisyos.foundry.data_plane.bindings as bindings

    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_source(
        store,
        _valid_payload(),
        kind="ir.observational_data",
        schema=None,
    )
    selected = read_core_json_artifact_bounded(store, source_ref, limits=_limits())
    raw_manifest = json.loads(selected.raw_manifest_bytes)
    raw_manifest["governance"] = {}
    # Isolate the declaration interpreter: this adversarial local value does
    # not stand in for a Core owner receipt or a prepared HTE source.
    materialized = SimpleNamespace(
        manifest=selected.manifest.model_copy(
            update={"governance": ArtifactGovernanceInfo(classification="public")}
        ),
        raw_manifest_bytes=json.dumps(raw_manifest).encode("utf-8"),
    )

    assert bindings._selected_source_governance(materialized) is None


def test_canonical_envelope_preserves_absent_governance_as_absent(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_envelope(store, governance=None)

    prepared = _prepare(store, source_ref)

    assert prepared.source_governance is None
    assert prepared.source_tenant_context == ArtifactTenantContextInfo(
        tenant_id="tenant-test",
        cell_id="cell-test",
    )


def test_protocol_b_does_not_fall_back_to_legacy_raw_payload(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_source(
        store,
        _valid_payload(),
        kind="ir.observational_data",
        schema=None,
    )

    with pytest.raises(HTEInputPreparationRefusal, match="source_protocol_kind_mismatch"):
        _prepare(store, source_ref, protocol="method_input_envelope_v1")


def test_protocol_a_does_not_accept_a_canonical_envelope(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_envelope(store)

    with pytest.raises(HTEInputPreparationRefusal, match="source_protocol_kind_mismatch"):
        _prepare(store, source_ref, protocol="legacy_hte_json_v1")


def test_envelope_body_must_supply_its_discriminator_explicitly(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    payload = _envelope_payload(_valid_payload())
    payload.pop("schema_version")
    source_ref = _put_envelope(store, payload)

    with pytest.raises(
        HTEInputPreparationRefusal,
        match="method_input_envelope_discriminator_required",
    ):
        _prepare(store, source_ref)


@pytest.mark.parametrize(
    ("target", "reason"),
    [
        (
            HTE_OBSERVATIONAL_DATA_TARGET.model_copy(
                update={"contract_id": "foundry.causal.other_data.v1"}
            ),
            "hte_contract_target_mismatch",
        ),
        (
            HTE_OBSERVATIONAL_DATA_TARGET.model_copy(
                update={
                    "contract_fqn": "polisyos.foundry.methods.catalog.causal.protocols.OtherData"
                }
            ),
            "hte_contract_target_mismatch",
        ),
    ],
)
def test_envelope_requires_exact_registered_target_id_and_fqn(
    tmp_path: Path,
    target: Any,
    reason: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_envelope(store, target=target)

    with pytest.raises(HTEInputPreparationRefusal, match=reason):
        _prepare(store, source_ref)


def test_target_does_not_add_a_version_field_to_the_existing_v1_shape() -> None:
    from pydantic import ValidationError

    from polisyos.ir.observation.bundles import ContractCompatibilityTarget

    payload = HTE_OBSERVATIONAL_DATA_TARGET.model_dump()
    payload["version"] = "1"

    with pytest.raises(ValidationError):
        ContractCompatibilityTarget.model_validate(payload)


def test_protocol_b_requires_exact_outer_manifest_schema(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_envelope(
        store,
        schema=SchemaInfo(name="polisyos.ir.ObservationMethodInputEnvelope", version="9.0"),
    )

    with pytest.raises(
        HTEInputPreparationRefusal,
        match="method_input_envelope_schema_mismatch",
    ):
        _prepare(store, source_ref)


def test_a_protocol_requires_an_explicit_selected_manifest_profile(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_source(
        store,
        _valid_payload(),
        kind="ir.observational_data",
        schema=None,
        return_selected_profile=False,
    )
    assert source_ref.manifest_profile_sha256 is None

    with pytest.raises(HTEInputPreparationRefusal, match="selected_manifest_profile_required"):
        _prepare(store, source_ref, protocol="legacy_hte_json_v1")


@pytest.mark.parametrize("protocol", ["method_input_envelope_v1", "legacy_hte_json_v1"])
@pytest.mark.parametrize(
    "limit_name", ["max_manifest_bytes", "max_bytes", "max_depth", "max_elements"]
)
def test_core_resource_policy_limits_refuse_before_hte_materialization(
    tmp_path: Path,
    protocol: str,
    limit_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.foundry.data_plane.bindings as bindings

    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    if protocol == "method_input_envelope_v1":
        source_ref = _put_envelope(store)
    else:
        source_ref = _put_source(
            store,
            _valid_payload(),
            kind="ir.observational_data",
            schema=None,
        )
    ids_before = _artifact_id_strings(store)
    payload_size = len(store.get_bytes(source_ref))
    limits = _limits(**{limit_name: 1})
    monkeypatch.setattr(
        bindings,
        "_materialize_hte_observational_data",
        lambda _payload: (_ for _ in ()).throw(AssertionError("HTE materialization ran")),
    )

    with pytest.raises(
        HTEInputPreparationRefusal,
        match="selected_source_read_refused",
    ) as refusal:
        _prepare(store, source_ref, protocol=protocol, limits=limits)
    assert refusal.value.observed_source_bytes == (
        refusal.value.observed_manifest_selection_bytes
        + refusal.value.observed_manifest_verification_bytes
        + refusal.value.observed_payload_bytes
    )
    if limit_name in {"max_depth", "max_elements"}:
        assert refusal.value.observed_payload_bytes == payload_size
        assert refusal.value.payload_integrity_verified is True
    else:
        assert refusal.value.payload_integrity_verified is False
    assert _artifact_id_strings(store) == ids_before


def test_hte_refusal_preserves_unknown_usage_from_attempted_core_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_envelope(store)

    def fail_after_open_attempt(*_args: Any, **_kwargs: Any) -> Any:
        raise TypeError("injected failure after bounded open was attempted")

    monkeypatch.setattr(FileSystemCAS, "open_member_bounded", fail_after_open_attempt)

    with pytest.raises(HTEInputPreparationRefusal, match="selected_source_read_refused") as error:
        _prepare(store, source_ref)

    refusal = error.value
    assert refusal.observed_manifest_selection_bytes > 0
    assert refusal.observed_manifest_verification_bytes is None
    assert refusal.observed_payload_bytes is None
    assert refusal.observed_source_bytes is None
    assert refusal.source_usage_complete is False
    assert refusal.payload_integrity_verified is False
    assert refusal.original_exception_type == "TypeError"
    assert isinstance(refusal.__cause__, CoreJsonReadBoundsRefusalError)
    assert isinstance(refusal.__cause__.__cause__, TypeError)


def test_hte_semantic_refusal_after_verified_full_read_keeps_usage_without_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.foundry.data_plane.bindings as bindings

    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_envelope(store)
    source_payload = store.get_bytes(source_ref)
    ids_before = _artifact_id_strings(store)

    def refuse_after_core_read(_payload: Any) -> Any:
        raise HTEInputPreparationRefusal("injected_hte_semantic_refusal")

    monkeypatch.setattr(bindings, "_materialize_hte_observational_data", refuse_after_core_read)

    with pytest.raises(HTEInputPreparationRefusal, match="injected_hte_semantic_refusal") as error:
        _prepare(store, source_ref)

    refusal = error.value
    assert refusal.observed_manifest_selection_bytes > 0
    assert refusal.observed_manifest_verification_bytes > 0
    assert refusal.observed_payload_bytes == len(source_payload)
    assert refusal.observed_source_bytes == (
        refusal.observed_manifest_selection_bytes
        + refusal.observed_manifest_verification_bytes
        + len(source_payload)
    )
    assert refusal.payload_integrity_verified is True
    assert refusal.source_usage_complete is True
    assert refusal.failure_stage == "hte_selected_source_validation"
    assert refusal.cleanup_failure_stage is None
    assert refusal.cleanup_exception_type is None
    assert _artifact_id_strings(store) == ids_before


@pytest.mark.parametrize(
    ("source_usage_complete", "expected_source_bytes"),
    [(True, 23), (False, None)],
)
def test_hte_refusal_retains_source_usage_completion_without_inference(
    source_usage_complete: bool,
    expected_source_bytes: int | None,
) -> None:
    refusal = HTEInputPreparationRefusal(
        "injected_source_usage_status",
        observed_manifest_selection_bytes=5,
        observed_manifest_verification_bytes=7,
        observed_payload_bytes=11,
        source_usage_complete=source_usage_complete,
    )

    assert refusal.source_usage_complete is source_usage_complete
    assert refusal.observed_source_bytes == expected_source_bytes


@pytest.mark.parametrize(
    ("mode", "expected_code", "expected_stage"),
    [
        (
            "serialization",
            "legacy_hte_normalization_refused",
            "normalized_hte_input_serialization",
        ),
        (
            "bounds",
            "normalized_hte_input_exceeds_byte_limit",
            "normalized_hte_input_bounds_validation",
        ),
    ],
)
def test_hte_legacy_output_prewrite_refusal_keeps_source_usage_without_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    expected_code: str,
    expected_stage: str,
) -> None:
    import polisyos.foundry.data_plane.bindings as bindings

    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_payload = _valid_payload()
    source_payload.update(
        {
            "confounders": None,
            "confounder_names": None,
            "feature_names": None,
            "sample_ids": None,
        }
    )
    source_ref = _put_source(
        store,
        source_payload,
        kind="ir.observational_data",
        schema=None,
    )
    source_payload_bytes = store.get_bytes(source_ref)
    manifest_bytes = store.get_raw_manifest_bytes(
        source_ref,
        manifest_profile_sha256=source_ref.manifest_profile_sha256,
    )
    ids_before = _artifact_id_strings(store)
    if mode == "serialization":
        serialization_error = ValueError("injected normalized output serialization refusal")

        def refuse_serialization(*args: Any, **kwargs: Any) -> bytes:
            raise serialization_error

        monkeypatch.setattr(bindings, "to_canonical_bytes", refuse_serialization)
        limits = _limits()
    else:
        max_bytes = len(source_payload_bytes) + 1
        limits = _limits(max_bytes=max_bytes)

        def exceed_normalized_bounds(*args: Any, **kwargs: Any) -> bytes:
            return b"x" * (max_bytes + 1)

        monkeypatch.setattr(bindings, "to_canonical_bytes", exceed_normalized_bounds)

    with pytest.raises(HTEInputPreparationRefusal, match=expected_code) as error:
        _prepare(store, source_ref, protocol="legacy_hte_json_v1", limits=limits)

    refusal = error.value
    assert refusal.code == expected_code
    assert refusal.observed_manifest_selection_bytes == len(manifest_bytes)
    assert refusal.observed_manifest_verification_bytes == len(manifest_bytes)
    assert refusal.observed_payload_bytes == len(source_payload_bytes)
    assert refusal.observed_source_bytes == (2 * len(manifest_bytes) + len(source_payload_bytes))
    assert refusal.payload_integrity_verified is True
    assert refusal.failure_stage == expected_stage
    assert refusal.cleanup_failure_stage is None
    assert refusal.cleanup_exception_type is None
    assert refusal.cleanup_exception_code is None
    assert _artifact_id_strings(store) == ids_before
    if mode == "serialization":
        assert refusal.original_exception_type == "ValueError"
        assert isinstance(refusal.__cause__, HTEInputPreparationRefusal)
        assert refusal.__cause__.__cause__ is serialization_error


def test_hte_normalized_output_write_refusal_keeps_source_usage_without_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_payload = _valid_payload()
    source_payload.update(
        {
            "confounders": None,
            "confounder_names": None,
            "feature_names": None,
            "sample_ids": None,
        }
    )
    source_ref = _put_source(
        store,
        source_payload,
        kind="ir.observational_data",
        schema=None,
    )
    source_payload_bytes = store.get_bytes(source_ref)
    manifest_bytes = store.get_raw_manifest_bytes(
        source_ref,
        manifest_profile_sha256=source_ref.manifest_profile_sha256,
    )
    ids_before = _artifact_id_strings(store)
    write_error = OSError("injected normalized output write refusal")

    def refuse_output_write(*args: Any, **kwargs: Any) -> ArtifactRef:
        raise write_error

    monkeypatch.setattr(store, "put_bytes", refuse_output_write)
    with pytest.raises(
        HTEInputPreparationRefusal,
        match="normalized_hte_input_write_refused",
    ) as error:
        _prepare(store, source_ref, protocol="legacy_hte_json_v1")

    refusal = error.value
    assert refusal.observed_manifest_selection_bytes == len(manifest_bytes)
    assert refusal.observed_manifest_verification_bytes == len(manifest_bytes)
    assert refusal.observed_payload_bytes == len(source_payload_bytes)
    assert refusal.observed_source_bytes == (2 * len(manifest_bytes) + len(source_payload_bytes))
    assert refusal.payload_integrity_verified is True
    assert refusal.failure_stage == "normalized_hte_input_write"
    assert refusal.cleanup_failure_stage is None
    assert refusal.cleanup_exception_type is None
    assert refusal.cleanup_exception_code is None
    assert refusal.original_exception_type == "OSError"
    assert isinstance(refusal.__cause__, HTEInputPreparationRefusal)
    assert refusal.__cause__.__cause__ is write_error
    assert _artifact_id_strings(store) == ids_before


def test_hte_normalized_output_profile_refusal_keeps_source_usage_and_nonadmission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_payload = _valid_payload()
    source_payload.update(
        {
            "confounders": None,
            "confounder_names": None,
            "feature_names": None,
            "sample_ids": None,
        }
    )
    source_ref = _put_source(
        store,
        source_payload,
        kind="ir.observational_data",
        schema=None,
    )
    source_payload_bytes = store.get_bytes(source_ref)
    manifest_bytes = store.get_raw_manifest_bytes(
        source_ref,
        manifest_profile_sha256=source_ref.manifest_profile_sha256,
    )
    ids_before = _artifact_id_strings(store)
    real_put_bytes = store.put_bytes

    def omit_selected_output_profile(*args: Any, **kwargs: Any) -> ArtifactRef:
        ref = real_put_bytes(*args, **kwargs)
        return ref.model_copy(update={"manifest_profile_sha256": None})

    monkeypatch.setattr(store, "put_bytes", omit_selected_output_profile)
    with pytest.raises(
        HTEInputPreparationRefusal,
        match="normalized_hte_profile_missing",
    ) as error:
        _prepare(store, source_ref, protocol="legacy_hte_json_v1")

    refusal = error.value
    assert refusal.observed_manifest_selection_bytes == len(manifest_bytes)
    assert refusal.observed_manifest_verification_bytes == len(manifest_bytes)
    assert refusal.observed_payload_bytes == len(source_payload_bytes)
    assert refusal.observed_source_bytes == (2 * len(manifest_bytes) + len(source_payload_bytes))
    assert refusal.payload_integrity_verified is True
    assert refusal.failure_stage == "normalized_hte_input_profile_validation"
    assert refusal.cleanup_failure_stage is None
    assert refusal.cleanup_exception_type is None
    assert refusal.cleanup_exception_code is None
    assert len(_artifact_id_strings(store) - ids_before) == 1


def test_hte_owner_open_partial_failure_keeps_unknown_attempt_usage_and_cause_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.core.artifacts.store as store_module

    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_envelope(store)
    selected_manifest = store.get_raw_manifest_bytes(
        source_ref,
        manifest_profile_sha256=source_ref.manifest_profile_sha256,
    )
    real_fdopen = os.fdopen
    fdopen_calls = 0

    class ReadThenRaise:
        def __init__(self, wrapped: Any) -> None:
            self._wrapped = wrapped

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return self._wrapped.__exit__(exc_type, exc, traceback)

        def close(self) -> None:
            self._wrapped.close()

        def fileno(self) -> int:
            return self._wrapped.fileno()

        def read(self, size: int = -1) -> bytes:
            self._wrapped.read(size)
            raise OSError("injected owner read failure after hidden transfer")

    def fail_during_verification(fd: int, *args: Any, **kwargs: Any) -> Any:
        nonlocal fdopen_calls
        fdopen_calls += 1
        wrapped = real_fdopen(fd, *args, **kwargs)
        return ReadThenRaise(wrapped) if fdopen_calls == 2 else wrapped

    monkeypatch.setattr(store_module.os, "fdopen", fail_during_verification)
    with pytest.raises(HTEInputPreparationRefusal, match="selected_source_read_refused") as error:
        _prepare(store, source_ref)

    refusal = error.value
    assert fdopen_calls == 2
    assert refusal.observed_manifest_selection_bytes == len(selected_manifest)
    assert refusal.observed_manifest_verification_bytes is None
    assert refusal.observed_payload_bytes == 0
    assert refusal.observed_source_bytes is None
    assert refusal.payload_integrity_verified is False
    assert refusal.original_exception_type == "OSError"
    assert isinstance(refusal.__cause__, CoreJsonReadBoundsRefusalError)
    assert refusal.__cause__.observed_manifest_verification_bytes is None
    assert isinstance(refusal.__cause__.__cause__, OSError)


@pytest.mark.parametrize(
    ("cleanup_code", "expected_cleanup_code"),
    [("hte_cleanup_code", "hte_cleanup_code"), (17, None)],
)
def test_hte_refuses_verified_source_when_member_close_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cleanup_code: object,
    expected_cleanup_code: str | None,
) -> None:
    import polisyos.core.artifacts.store as store_module

    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_envelope(store)
    source_payload = store.get_bytes(source_ref)
    ids_before = _artifact_id_strings(store)
    real_fdopen = os.fdopen
    fdopen_calls = 0

    class CloseError(OSError):
        code: object

    close_error = CloseError("injected HTE payload close failure after verification")
    close_error.code = cleanup_code

    class CloseThenRaise:
        def __init__(self, wrapped: Any) -> None:
            self._wrapped = wrapped

        def fileno(self) -> int:
            return self._wrapped.fileno()

        def read(self, size: int = -1) -> bytes:
            return self._wrapped.read(size)

        def close(self) -> None:
            self._wrapped.close()
            raise close_error

    def fail_payload_close(descriptor: int, *args: Any, **kwargs: Any) -> Any:
        nonlocal fdopen_calls
        fdopen_calls += 1
        wrapped = real_fdopen(descriptor, *args, **kwargs)
        return CloseThenRaise(wrapped) if fdopen_calls == 3 else wrapped

    monkeypatch.setattr(store_module.os, "fdopen", fail_payload_close)
    with pytest.raises(HTEInputPreparationRefusal, match="selected_source_read_refused") as error:
        _prepare(store, source_ref)

    refusal = error.value
    assert fdopen_calls == 3
    assert refusal.observed_payload_bytes == len(source_payload)
    assert refusal.payload_integrity_verified is True
    assert refusal.observed_source_bytes == (
        refusal.observed_manifest_selection_bytes
        + refusal.observed_manifest_verification_bytes
        + len(source_payload)
    )
    assert refusal.failure_stage == "bounded_member_close"
    assert refusal.cleanup_failure_stage == "bounded_member_close"
    assert refusal.cleanup_exception_type == "CloseError"
    assert refusal.cleanup_exception_code == expected_cleanup_code
    assert isinstance(refusal.__cause__, CoreJsonReadBoundsRefusalError)
    assert refusal.__cause__.__cause__ is close_error
    assert _artifact_id_strings(store) == ids_before


def test_hte_preserves_primary_read_refusal_and_secondary_close_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.core.artifacts.store as store_module

    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_envelope(store)
    selected_manifest = store.get_raw_manifest_bytes(
        source_ref,
        manifest_profile_sha256=source_ref.manifest_profile_sha256,
    )
    ids_before = _artifact_id_strings(store)
    real_fdopen = os.fdopen
    fdopen_calls = 0
    primary_error = TypeError("injected primary payload read refusal")
    close_error = OSError("injected secondary payload close failure")

    class ReadThenRaiseAndClose:
        def __init__(self, wrapped: Any) -> None:
            self._wrapped = wrapped

        def fileno(self) -> int:
            return self._wrapped.fileno()

        def read(self, size: int = -1) -> bytes:
            self._wrapped.read(size)
            raise primary_error

        def close(self) -> None:
            self._wrapped.close()
            raise close_error

    def fail_payload_read_and_close(descriptor: int, *args: Any, **kwargs: Any) -> Any:
        nonlocal fdopen_calls
        fdopen_calls += 1
        wrapped = real_fdopen(descriptor, *args, **kwargs)
        return ReadThenRaiseAndClose(wrapped) if fdopen_calls == 3 else wrapped

    monkeypatch.setattr(store_module.os, "fdopen", fail_payload_read_and_close)
    with pytest.raises(HTEInputPreparationRefusal, match="selected_source_read_refused") as error:
        _prepare(store, source_ref)

    refusal = error.value
    assert fdopen_calls == 3
    assert refusal.observed_manifest_selection_bytes == len(selected_manifest)
    assert refusal.observed_manifest_verification_bytes == len(selected_manifest)
    assert refusal.observed_payload_bytes is None
    assert refusal.observed_source_bytes is None
    assert refusal.payload_integrity_verified is False
    assert refusal.failure_stage == "bounded_payload_read"
    assert refusal.cleanup_failure_stage == "bounded_member_close"
    assert refusal.cleanup_exception_type == "OSError"
    assert refusal.cleanup_exception_code is None
    assert refusal.original_exception_type == "TypeError"
    assert isinstance(refusal.__cause__, CoreJsonReadBoundsRefusalError)
    assert refusal.__cause__.__cause__ is primary_error
    assert _artifact_id_strings(store) == ids_before


@pytest.mark.parametrize(
    ("mutate", "canon_spec"),
    [
        (
            lambda payload: payload.update(
                {
                    "outcome": [0.0] * 39,
                    "treatment": [index % 2 for index in range(39)],
                    "covariates": [[float(index)] for index in range(39)],
                }
            ),
            None,
        ),
        (
            lambda payload: payload["treatment"].__setitem__(0, 2),
            None,
        ),
        (
            lambda payload: payload["treatment"].pop(),
            None,
        ),
        (
            lambda payload: payload["covariates"].pop(),
            None,
        ),
        (
            lambda payload: payload["confounders"].pop(),
            None,
        ),
        (
            lambda payload: payload["sample_ids"].pop(),
            None,
        ),
        (
            lambda payload: payload["outcome"].__setitem__(0, float("inf")),
            CanonSpec(forbid_floats=False, forbid_nan_inf=False, exclude_none=False),
        ),
        (
            lambda payload: payload["covariates"][0].__setitem__(0, float("nan")),
            CanonSpec(forbid_floats=False, forbid_nan_inf=False, exclude_none=False),
        ),
        (
            lambda payload: payload["confounders"][0].__setitem__(0, float("inf")),
            CanonSpec(forbid_floats=False, forbid_nan_inf=False, exclude_none=False),
        ),
    ],
    ids=[
        "below-minimum-n",
        "nonbinary-treatment",
        "treatment-unmatched",
        "covariate-unmatched",
        "confounder-unmatched",
        "sample-ids-unmatched",
        "nonfinite-outcome",
        "nonfinite-covariate",
        "nonfinite-confounder",
    ],
)
def test_real_producer_rejects_current_hte_semantic_constraints(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
    canon_spec: CanonSpec | None,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    payload = _valid_payload()
    mutate(payload)
    source_ref = _put_envelope(
        store,
        _envelope_payload(payload),
        canon_spec=canon_spec,
    )

    with pytest.raises(HTEInputPreparationRefusal, match="invalid_hte_observational_data"):
        _prepare(store, source_ref)


def test_registry_removal_breaks_real_producer_positive_with_markers_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.foundry.data_plane.bindings as bindings

    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_envelope(store)
    monkeypatch.delitem(
        bindings._METHOD_CONTRACT_ALLOW_REGISTRY,
        HTE_OBSERVATIONAL_DATA_CONTRACT_ID,
    )

    with pytest.raises(HTEInputPreparationRefusal, match="invalid_hte_observational_data"):
        _prepare(store, source_ref)


def test_opt_in_materialization_binding_round_trips_through_fresh_core_reader(
    tmp_path: Path,
) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root, ownership_enforced=False)
    source_ref = _put_envelope(store)
    ids_before = _artifact_id_strings(store)

    prepared = _prepare(
        store,
        source_ref,
        materialization_binding_version="physical_v1",
    )

    assert prepared.materialization_binding_ref is not None
    assert prepared.materialization_binding_ref.kind == HTE_PHYSICAL_SOURCE_BINDING_KIND
    assert prepared.materialization_binding_ref.manifest_profile_sha256 is not None
    assert len(_artifact_id_strings(store) - ids_before) == 1
    binding = load_hte_physical_source_materialization_binding(
        store=FileSystemCAS.open_existing_read_only(cas_root),
        binding_ref=prepared.materialization_binding_ref,
        expected_submitted_ref=source_ref,
        expected_effective_ref=source_ref,
        limits=_limits(),
    )

    assert isinstance(binding, HTEPhysicalSourceMaterializationBinding)
    assert binding.binding_scope == "physical_materialization_only"
    assert binding.semantic_alignment_status == "not_established"
    assert binding.submitted_ref == source_ref
    assert binding.effective_ref == source_ref
    assert binding.observation_count == 40
    assert binding.row_order_basis == "sample_ids"
    assert binding.row_order_pointer == "/contract_payload/sample_ids"
    assert binding.submitted_sample_ids_state == "materialized"
    assert binding.effective_sample_ids_state == "materialized"
    assert binding.submitted_confounders_state == "materialized"
    assert binding.effective_confounders_state == "materialized"
    assert [
        (slot.physical_slot, slot.component_index, slot.payload_pointer) for slot in binding.arrays
    ] == [
        ("outcome_vector", None, "/contract_payload/outcome"),
        ("treatment_vector", None, "/contract_payload/treatment"),
        ("covariate_matrix_column", 0, "/contract_payload/covariates"),
        ("covariate_matrix_column", 1, "/contract_payload/covariates"),
        ("confounder_matrix_column", 0, "/contract_payload/confounders"),
    ]
    assert all(slot.transform == "identity_numpy_materialization_v1" for slot in binding.arrays)
    serialized = binding.model_dump(mode="json")
    assert "feature_names" not in serialized
    assert "confounder_names" not in serialized
    assert "age" not in json.dumps(serialized)
    assert prepared.materialization_binding_ref.manifest_profile_sha256


def test_default_envelope_materialization_emits_no_binding_artifact(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_envelope(store)
    ids_before = _artifact_id_strings(store)

    prepared = _prepare(store, source_ref)

    assert prepared.materialization_binding_ref is None
    assert prepared.effective_ref == source_ref
    assert _artifact_id_strings(store) == ids_before


def test_binding_writer_enforces_selected_core_element_bound_before_cas_write(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_envelope(store)
    prepared = _prepare(
        store,
        source_ref,
        materialization_binding_version="physical_v1",
    )
    assert prepared.materialization_binding_ref is not None
    binding = load_hte_physical_source_materialization_binding(
        store=store,
        binding_ref=prepared.materialization_binding_ref,
        expected_submitted_ref=source_ref,
        expected_effective_ref=prepared.effective_ref,
        limits=_limits(),
        expected_data=prepared.data,
    )
    ids_before = _artifact_id_strings(store)

    with pytest.raises(
        HTEInputPreparationRefusal,
        match="source_binding_exceeds_element_limit",
    ):
        _persist_hte_physical_source_binding(
            store=store,
            binding=binding,
            source_governance=prepared.source_governance,
            tenant_context=prepared.source_tenant_context,
            limits=_limits(max_elements=1),
        )

    assert _artifact_id_strings(store) == ids_before


def test_materialization_binding_opt_in_preserves_legacy_source_lineage(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_source(
        store,
        _valid_payload(),
        kind="ir.observational_data",
        schema=None,
    )

    ordinary = _prepare(
        store,
        source_ref,
        protocol="legacy_hte_json_v1",
    )
    assert ordinary.materialization_binding_ref is None
    ordinary_effective_read = read_core_json_artifact_bounded(
        store,
        ordinary.effective_ref,
        limits=_limits(),
    )
    prepared = _prepare(
        store,
        source_ref,
        protocol="legacy_hte_json_v1",
        materialization_binding_version="physical_v1",
    )

    assert prepared.materialization_binding_ref is not None
    assert prepared.effective_ref != source_ref
    assert prepared.effective_ref == ordinary.effective_ref
    opt_in_effective_read = read_core_json_artifact_bounded(
        store,
        prepared.effective_ref,
        limits=_limits(),
    )
    assert opt_in_effective_read.raw_payload_bytes == ordinary_effective_read.raw_payload_bytes
    binding = load_hte_physical_source_materialization_binding(
        store=store,
        binding_ref=prepared.materialization_binding_ref,
        expected_submitted_ref=source_ref,
        expected_effective_ref=prepared.effective_ref,
        limits=_limits(),
    )
    assert binding.source_protocol == "legacy_hte_json_v1"
    assert binding.normalization == "legacy_to_method_input_envelope_v1"
    assert binding.submitted_ref == source_ref
    assert binding.effective_ref == prepared.effective_ref


@pytest.mark.parametrize(
    ("field_name", "submitted_state_field"),
    [
        ("sample_ids", "submitted_sample_ids_state"),
        ("confounders", "submitted_confounders_state"),
    ],
)
def test_legacy_binding_preserves_absent_vs_null_source_fields(
    tmp_path: Path,
    field_name: str,
    submitted_state_field: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    absent_payload = _valid_payload()
    absent_payload.pop(field_name)
    null_payload = _valid_payload()
    null_payload[field_name] = None
    absent_ref = _put_source(
        store,
        absent_payload,
        kind="ir.observational_data",
        schema=None,
    )
    null_ref = _put_source(
        store,
        null_payload,
        kind="ir.observational_data",
        schema=None,
    )

    absent_prepared = _prepare(
        store,
        absent_ref,
        protocol="legacy_hte_json_v1",
        materialization_binding_version="physical_v1",
    )
    null_prepared = _prepare(
        store,
        null_ref,
        protocol="legacy_hte_json_v1",
        materialization_binding_version="physical_v1",
    )
    assert absent_prepared.materialization_binding_ref is not None
    assert null_prepared.materialization_binding_ref is not None

    absent_binding = load_hte_physical_source_materialization_binding(
        store=store,
        binding_ref=absent_prepared.materialization_binding_ref,
        expected_submitted_ref=absent_ref,
        expected_effective_ref=absent_prepared.effective_ref,
        limits=_limits(),
    )
    null_binding = load_hte_physical_source_materialization_binding(
        store=store,
        binding_ref=null_prepared.materialization_binding_ref,
        expected_submitted_ref=null_ref,
        expected_effective_ref=null_prepared.effective_ref,
        limits=_limits(),
    )
    effective_state_field = submitted_state_field.replace("submitted_", "effective_")
    assert getattr(absent_binding, submitted_state_field) == "absent"
    assert getattr(null_binding, submitted_state_field) == "null"
    assert getattr(absent_binding, effective_state_field) == "null"
    assert getattr(null_binding, effective_state_field) == "null"


def test_legacy_binding_rejects_counterfeit_normalized_effective_input(
    tmp_path: Path,
) -> None:
    from polisyos.foundry.data_plane import bindings as foundry_bindings

    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    submitted_payload = _valid_payload()
    source_ref = _put_source(
        store,
        submitted_payload,
        kind="ir.observational_data",
        schema=None,
    )
    prepared = _prepare(
        store,
        source_ref,
        protocol="legacy_hte_json_v1",
        materialization_binding_version="physical_v1",
    )
    assert prepared.materialization_binding_ref is not None

    selected_effective_read = read_core_json_artifact_bounded(
        store,
        prepared.effective_ref,
        limits=_limits(),
    )
    counterfeit_envelope = json.loads(
        json.dumps(require_declared_profile(selected_effective_read.profile_read))
    )
    counterfeit_envelope["contract_payload"]["outcome"][0] += 100.0
    canon_spec = CanonSpec(
        forbid_floats=False,
        forbid_nan_inf=True,
        exclude_none=False,
        max_depth=_limits().max_depth,
    )
    counterfeit_effective_ref = store.put_bytes(
        to_canonical_bytes(counterfeit_envelope, canon_spec),
        PutOptions(
            kind=OBSERVATION_METHOD_INPUT_KIND,
            media_type="application/json",
            schema=_ENVELOPE_SCHEMA,
            producer=ProducerInfo(
                component=("polisyos.foundry.data_plane.prepare_hte_observational_input"),
                version="1.0.0",
            ),
            inputs=[
                InputRef(
                    artifact_id=source_ref.artifact_id,
                    role="legacy_hte_json_v1_source",
                    manifest_profile_sha256=source_ref.manifest_profile_sha256,
                )
            ],
            canon=CanonInfo.from_spec(canon_spec),
            governance=_RESTRICTED,
            tenant_context=ArtifactTenantContextInfo(
                tenant_id="tenant-test",
                cell_id="cell-test",
            ),
        ),
        return_selected_profile=True,
    )
    assert counterfeit_effective_ref.manifest_profile_sha256 is not None

    counterfeit_data = HTEObservationalData.model_validate(counterfeit_envelope["contract_payload"])
    counterfeit_binding = foundry_bindings._build_hte_physical_source_binding(
        data=counterfeit_data,
        submitted_ref=source_ref,
        effective_ref=counterfeit_effective_ref,
        source_protocol="legacy_hte_json_v1",
        normalization="legacy_to_method_input_envelope_v1",
        contract_target=HTE_OBSERVATIONAL_DATA_TARGET,
        submitted_contract_payload=submitted_payload,
        effective_contract_payload=counterfeit_envelope["contract_payload"],
        effective_payload_bytes=to_canonical_bytes(
            counterfeit_envelope,
            canon_spec,
        ),
        max_depth=_limits().max_depth,
    )
    counterfeit_binding_ref = foundry_bindings._persist_hte_physical_source_binding(
        store=store,
        binding=counterfeit_binding,
        source_governance=_RESTRICTED,
        tenant_context=ArtifactTenantContextInfo(
            tenant_id="tenant-test",
            cell_id="cell-test",
        ),
        limits=_limits(),
    )

    with pytest.raises(
        HTEInputPreparationRefusal,
        match="source_binding_legacy_normalization_mismatch",
    ):
        load_hte_physical_source_materialization_binding(
            store=FileSystemCAS.open_existing_read_only(tmp_path / "cas"),
            binding_ref=counterfeit_binding_ref,
            expected_submitted_ref=source_ref,
            expected_effective_ref=counterfeit_effective_ref,
            limits=_limits(),
        )


def test_binding_rejects_forged_field_map_and_bool_as_integer(
    tmp_path: Path,
) -> None:
    from pydantic import ValidationError

    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_envelope(store)
    prepared = _prepare(
        store,
        source_ref,
        materialization_binding_version="physical_v1",
    )
    assert prepared.materialization_binding_ref is not None
    binding = load_hte_physical_source_materialization_binding(
        store=store,
        binding_ref=prepared.materialization_binding_ref,
        expected_submitted_ref=source_ref,
        expected_effective_ref=source_ref,
        limits=_limits(),
    )
    forged_slots = list(binding.arrays)
    forged_slots[0] = forged_slots[0].model_copy(
        update={"payload_pointer": "/contract_payload/treatment"}
    )
    forged = binding.model_copy(update={"arrays": tuple(forged_slots)})
    spec = CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False)
    forged_ref = store.put_bytes(
        to_canonical_bytes(forged.model_dump(mode="json"), spec),
        PutOptions(
            kind=HTE_PHYSICAL_SOURCE_BINDING_KIND,
            media_type="application/json",
            schema=HTE_PHYSICAL_SOURCE_BINDING_SCHEMA,
            producer=ProducerInfo(
                component="tests.forged_hte_source_binding",
                version="1.0",
            ),
            inputs=[
                InputRef(
                    artifact_id=source_ref.artifact_id,
                    role="materialized_hte_method_input",
                    manifest_profile_sha256=source_ref.manifest_profile_sha256,
                )
            ],
            canon=CanonInfo.from_spec(spec),
            governance=_RESTRICTED,
            tenant_context=ArtifactTenantContextInfo(
                tenant_id="tenant-test",
                cell_id="cell-test",
            ),
        ),
        return_selected_profile=True,
    )

    with pytest.raises(
        HTEInputPreparationRefusal,
        match="source_binding_recomputation_mismatch",
    ):
        load_hte_physical_source_materialization_binding(
            store=store,
            binding_ref=forged_ref,
            expected_submitted_ref=source_ref,
            expected_effective_ref=source_ref,
            limits=_limits(),
        )

    invalid_payload = binding.model_dump(mode="json")
    invalid_payload["observation_count"] = True
    with pytest.raises(ValidationError):
        HTEPhysicalSourceMaterializationBinding.model_validate_json(json.dumps(invalid_payload))


@pytest.mark.parametrize(
    ("field_name", "expected_reason"),
    [
        ("array_dtype", "source_binding_recomputation_mismatch"),
        ("row_order_sha256", "source_binding_recomputation_mismatch"),
        ("effective_payload_sha256", "source_binding_effective_payload_mismatch"),
    ],
    ids=["array-dtype", "row-order", "effective-payload"],
)
def test_fresh_reader_recomputes_persisted_physical_binding_content(
    tmp_path: Path,
    field_name: str,
    expected_reason: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_envelope(store)
    prepared = _prepare(
        store,
        source_ref,
        materialization_binding_version="physical_v1",
    )
    assert prepared.materialization_binding_ref is not None
    binding = load_hte_physical_source_materialization_binding(
        store=FileSystemCAS.open_existing_read_only(tmp_path / "cas"),
        binding_ref=prepared.materialization_binding_ref,
        expected_submitted_ref=source_ref,
        expected_effective_ref=prepared.effective_ref,
        limits=_limits(),
    )
    payload = binding.model_dump(mode="json")
    if field_name == "array_dtype":
        payload["arrays"][0][field_name] = "<f4"
    else:
        payload[field_name] = "sha256:" + "0" * 64
    tampered_binding = HTEPhysicalSourceMaterializationBinding.model_validate_json(
        json.dumps(payload)
    )
    canon_spec = CanonSpec(
        forbid_floats=False,
        forbid_nan_inf=True,
        exclude_none=False,
        max_depth=_limits().max_depth,
    )
    tampered_ref = store.put_bytes(
        to_canonical_bytes(tampered_binding.model_dump(mode="json"), canon_spec),
        PutOptions(
            kind=HTE_PHYSICAL_SOURCE_BINDING_KIND,
            media_type="application/json",
            schema=HTE_PHYSICAL_SOURCE_BINDING_SCHEMA,
            producer=ProducerInfo(
                component="tests.unit.foundry.physical_binding_content_tamper",
                version="1.0",
            ),
            inputs=[
                InputRef(
                    artifact_id=prepared.effective_ref.artifact_id,
                    role="materialized_hte_method_input",
                    manifest_profile_sha256=(prepared.effective_ref.manifest_profile_sha256),
                )
            ],
            canon=CanonInfo.from_spec(canon_spec),
            governance=prepared.source_governance,
            tenant_context=prepared.source_tenant_context,
        ),
        return_selected_profile=True,
    )
    assert tampered_ref.manifest_profile_sha256 is not None

    with pytest.raises(HTEInputPreparationRefusal, match=expected_reason):
        load_hte_physical_source_materialization_binding(
            store=FileSystemCAS.open_existing_read_only(tmp_path / "cas"),
            binding_ref=tampered_ref,
            expected_submitted_ref=source_ref,
            expected_effective_ref=prepared.effective_ref,
            limits=_limits(),
        )


def test_binding_rejects_worker_dto_that_differs_from_selected_source(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_a_payload = _valid_payload()
    source_b_payload = _valid_payload()
    for row in source_b_payload["covariates"]:
        row[0], row[1] = row[1], row[0]
    source_a = _put_envelope(store, _envelope_payload(source_a_payload))
    source_b = _put_envelope(store, _envelope_payload(source_b_payload))
    prepared_a = _prepare(store, source_a, materialization_binding_version="physical_v1")
    prepared_b = _prepare(store, source_b, materialization_binding_version="physical_v1")
    assert prepared_a.materialization_binding_ref is not None
    with pytest.raises(
        HTEInputPreparationRefusal,
        match="source_binding_materialized_data_mismatch",
    ):
        load_hte_physical_source_materialization_binding(
            store=store,
            binding_ref=prepared_a.materialization_binding_ref,
            expected_submitted_ref=source_a,
            expected_effective_ref=source_a,
            limits=_limits(),
            expected_data=prepared_b.data,
        )


@pytest.mark.parametrize("mutation", ["same_names_swapped_columns", "reordered_rows"])
def test_same_labels_do_not_bind_swapped_arrays_or_row_order(
    tmp_path: Path,
    mutation: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_a_payload = _valid_payload()
    source_b_payload = _valid_payload()
    if mutation == "same_names_swapped_columns":
        for row in source_b_payload["covariates"]:
            row[0], row[1] = row[1], row[0]
    else:
        for field_name in (
            "outcome",
            "treatment",
            "covariates",
            "confounders",
            "sample_ids",
        ):
            source_b_payload[field_name].reverse()
    source_a = _put_envelope(store, _envelope_payload(source_a_payload))
    source_b = _put_envelope(store, _envelope_payload(source_b_payload))
    prepared_a = _prepare(store, source_a, materialization_binding_version="physical_v1")
    prepared_b = _prepare(store, source_b, materialization_binding_version="physical_v1")
    assert prepared_a.materialization_binding_ref is not None
    assert prepared_b.materialization_binding_ref is not None
    binding_a = load_hte_physical_source_materialization_binding(
        store=store,
        binding_ref=prepared_a.materialization_binding_ref,
        expected_submitted_ref=source_a,
        expected_effective_ref=source_a,
        limits=_limits(),
    )
    binding_b = load_hte_physical_source_materialization_binding(
        store=store,
        binding_ref=prepared_b.materialization_binding_ref,
        expected_submitted_ref=source_b,
        expected_effective_ref=source_b,
        limits=_limits(),
    )
    assert source_a_payload["feature_names"] == source_b_payload["feature_names"]
    assert binding_a.semantic_alignment_status == "not_established"
    assert binding_b.semantic_alignment_status == "not_established"
    if mutation == "reordered_rows":
        assert binding_a.row_order_sha256 != binding_b.row_order_sha256
    else:
        assert binding_a.row_order_sha256 == binding_b.row_order_sha256
    assert tuple(slot.value_sha256 for slot in binding_a.arrays) != tuple(
        slot.value_sha256 for slot in binding_b.arrays
    )
    with pytest.raises(HTEInputPreparationRefusal, match="source_binding_input_ref_mismatch"):
        load_hte_physical_source_materialization_binding(
            store=store,
            binding_ref=prepared_a.materialization_binding_ref,
            expected_submitted_ref=source_b,
            expected_effective_ref=source_b,
            limits=_limits(),
        )


def test_binding_refuses_an_equal_payload_under_a_foreign_selected_profile(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    payload = _envelope_payload(_valid_payload())
    selected = _put_envelope(store, payload)
    alternate_profile = _put_source(
        store,
        payload,
        kind=OBSERVATION_METHOD_INPUT_KIND,
        schema=_ENVELOPE_SCHEMA,
        governance=ArtifactGovernanceInfo(classification="confidential"),
    )
    assert selected.artifact_id == alternate_profile.artifact_id
    assert selected.manifest_profile_sha256 != alternate_profile.manifest_profile_sha256
    prepared = _prepare(
        store,
        selected,
        materialization_binding_version="physical_v1",
    )
    assert prepared.materialization_binding_ref is not None

    with pytest.raises(HTEInputPreparationRefusal, match="source_binding_input_ref_mismatch"):
        load_hte_physical_source_materialization_binding(
            store=store,
            binding_ref=prepared.materialization_binding_ref,
            expected_submitted_ref=alternate_profile,
            expected_effective_ref=alternate_profile,
            limits=_limits(),
        )
