from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.common.canonical_profile import require_declared_profile
from polisyos.core.artifacts import (
    CoreJsonReadLimits,
    read_core_json_artifact_bounded,
    read_core_manifest_profile_bounded,
)
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    ArtifactTenantContextInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.foundry.data_plane import (
    HTEInputLimits,
    HTEInputPreparationRefusal,
    prepare_hte_observational_input,
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
):
    return prepare_hte_observational_input(
        store=store,  # type: ignore[arg-type]
        source_ref=ref,
        protocol=protocol,  # type: ignore[arg-type]
        method_fqn=_METHOD_FQN,
        limits=limits or _limits(),
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


def test_legacy_source_does_not_treat_typed_public_default_as_raw_declaration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    selected = SimpleNamespace(
        effective_ref=selected.effective_ref,
        manifest=selected.manifest.model_copy(
            update={"governance": ArtifactGovernanceInfo(classification="public")}
        ),
        profile_read=selected.profile_read,
        raw_manifest_bytes=json.dumps(raw_manifest).encode("utf-8"),
        observed_bytes=selected.observed_bytes,
        observed_depth=selected.observed_depth,
        observed_elements=selected.observed_elements,
    )
    monkeypatch.setattr(
        bindings,
        "read_core_json_artifact_bounded",
        lambda *_args, **_kwargs: selected,
    )
    ids_before = _artifact_id_strings(store)

    with pytest.raises(HTEInputPreparationRefusal, match="source_governance_unavailable"):
        _prepare(store, source_ref, protocol="legacy_hte_json_v1")

    assert _artifact_id_strings(store) == ids_before


def test_canonical_envelope_preserves_absent_governance_as_absent(tmp_path: Path) -> None:
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


def test_a_protocol_requires_an_explicit_selected_manifest_profile(tmp_path: Path) -> None:
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
    limits = _limits(**{limit_name: 1})
    monkeypatch.setattr(
        bindings,
        "_materialize_hte_observational_data",
        lambda _payload: (_ for _ in ()).throw(AssertionError("HTE materialization ran")),
    )

    with pytest.raises(HTEInputPreparationRefusal, match="selected_source_read_refused"):
        _prepare(store, source_ref, protocol=protocol, limits=limits)
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
