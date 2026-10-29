"""Runtime semantics for selected observational inputs and graph origin binding."""

from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.metadata
import json
import os
import sqlite3
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import JsonValue

from polisyos.core.artifacts.canonical_profile import (
    CoreJsonReadLimits,
    read_core_json_artifact_bounded,
    read_core_manifest_profile_bounded,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    ArtifactTenantContextInfo,
    InputRef,
    SchemaInfo,
    artifact_ref_identity_key,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.bounded_liveness import BoundedLivenessConfig
from polisyos.core.contracts.control import (
    _OBSERVATIONAL_INPUT_CONSUMED_REQUEST_FIELDS,
    WorkflowRunRequest,
)
from polisyos.core.contracts.foundry import (
    DerivedArtifact,
    ExecuteResult,
    MethodExecutionBundleRef,
    MethodMetricBindingSetRef,
    SimulationResultRef,
)
from polisyos.core.contracts.runtime import (
    ContentAdmittedObservationalRunIntent,
    DirectMethodExecutionSelection,
    GraphMethodExecutionSelection,
    MethodExecutionProducerDiagnostic,
    MethodExecutionProducerEmissionDiagnostic,
    MethodMetricProjectionSelection,
    ObservationalInputResourcePolicy,
    ObservationalRunIntent,
    _expected_content_admitted_limitations,
)
from polisyos.runtime.http.routes import runs as runs_routes
from polisyos.runtime.http.services.control.run_lifecycle import (
    ControlPlaneService,
    _content_admitted_intent_input_edges,
    _explicit_source_manifest_metadata,
    _has_exact_selected_input_edges,
    _observational_run_intent_input_edges,
    _RuntimeOriginCapturingFoundryPort,
    _scientist_graph_output_refs,
    _selected_graph_source_refs_from_receipt,
    _validate_direct_method_execution_selection_artifacts,
)
from polisyos.runtime.http.services.control.workspace_loop_transition import (
    ControlPlaneWorkspaceLoopTransitionMixin,
    _LegacyScientistWorkflowError,
    _WorkflowExecutionNonAuthorityError,
)
from tests._helpers.observational_source_runtime import (
    scoped_source_runtime as scoped_source_runtime,
)
from tests._helpers.observational_source_runtime import (
    selected_source_runtime_api_env as selected_source_runtime_api_env,
)


def _selected_ref(kind: str, artifact_char: str, profile_char: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate("sha256:" + artifact_char * 64),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + profile_char * 64,
    )


def _input_edge(ref: ArtifactRef, role: str) -> InputRef:
    return InputRef(
        artifact_id=ref.artifact_id,
        role=role,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )


def _put_selected_json(
    store: FileSystemCAS,
    payload: object,
    *,
    kind: str,
    schema: SchemaInfo | None,
    inputs: tuple[InputRef, ...] = (),
    governance: ArtifactGovernanceInfo | None = None,
    tenant_context: ArtifactTenantContextInfo | None = None,
) -> ArtifactRef:
    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=schema,
            inputs=list(inputs),
            governance=governance,
            tenant_context=tenant_context,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _direct_method_cas_case(
    tmp_path: Path,
    *,
    protocol: str = "method_input_envelope_v1",
    wrong_result_schema: bool = False,
    wrong_result_input: bool = False,
    wrong_evidence_input: bool = False,
    wrong_effective_source_input: bool = False,
    wrong_evidence_method_fqn: bool = False,
    wrong_evidence_result_ref: bool = False,
    wrong_evidence_schema: bool = False,
    missing_requested_limitation: bool = False,
    missing_admitted_limitation: bool = False,
    wrong_admitted_target_id: bool = False,
    wrong_admitted_usage_total: bool = False,
    wrong_admitted_usage_limit: bool = False,
    remove_result_governance: bool = False,
    remove_evidence_governance: bool = False,
) -> tuple[FileSystemCAS, DirectMethodExecutionSelection, CoreJsonReadLimits]:
    source_kind = (
        "ir.observation_method_input"
        if protocol == "method_input_envelope_v1"
        else "ir.observational_data"
    )
    envelope_schema = SchemaInfo(
        name="polisyos.ir.ObservationMethodInputEnvelope",
        version="1.0",
    )
    governance = ArtifactGovernanceInfo(classification="public")
    store = FileSystemCAS(tmp_path / "cas").with_ambient_ownership_enforcement()
    source_ref = _put_selected_json(
        store,
        {"schema_version": "candidate-source", "data": [1, 2, 3]},
        kind=source_kind,
        schema=envelope_schema if protocol == "method_input_envelope_v1" else None,
        governance=governance,
    )
    limits = CoreJsonReadLimits(
        max_bytes=1_048_576,
        max_depth=32,
        max_elements=10_000,
        max_manifest_bytes=65_536,
    )
    source_read = read_core_manifest_profile_bounded(
        store,
        source_ref,
        max_manifest_bytes=limits.max_manifest_bytes,
    )
    usage_read = read_core_json_artifact_bounded(store, source_ref, limits=limits)
    source_manifest_sha256 = hashlib.sha256(source_read.raw_manifest_bytes).hexdigest()
    other_source_ref = _put_selected_json(
        store,
        {"schema_version": "candidate-source", "data": [4, 5, 6]},
        kind=source_kind,
        schema=envelope_schema if protocol == "method_input_envelope_v1" else None,
        governance=governance,
    )
    wait_policy = BoundedLivenessConfig().resolve(
        "runtime.observational_method_execution",
        requested_retries=0,
    )
    resource_policy = ObservationalInputResourcePolicy(
        schema_version="polisyos.runtime.observational_input_resource_policy.v3",
        revision="r3",
        max_manifest_bytes=limits.max_manifest_bytes,
        max_bytes=limits.max_bytes,
        max_depth=limits.max_depth,
        max_elements=limits.max_elements,
        method_contract_target=(
            "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
        ),
        required_estimator_n_jobs=1,
        method_execution_wait_policy=wait_policy,
    )
    resource_policy_ref = _put_selected_json(
        store,
        resource_policy.model_dump(mode="json"),
        kind="runtime.observational_input_resource_policy",
        schema=SchemaInfo(
            name="polisyos.runtime.ObservationalInputResourcePolicy",
            version="1.0",
        ),
        inputs=(_input_edge(source_ref, "source"),),
        governance=governance,
    )
    requested_intent = ObservationalRunIntent(
        job_id="job-direct-cas",
        run_id="run-direct-cas",
        requested_source_ref=source_ref,
        source_manifest_sha256=source_manifest_sha256,
        protocol=protocol,
        method_fqn="causal.hte.forest_dr@1.1.0",
        method_version="1.1.0",
        method_abi_digest="a" * 64,
        method_build_digest="b" * 64,
        submitted_params_present=False,
        submitted_params={},
        resolved_params={"n_jobs": 1},
        seed=0,
        resource_policy=resource_policy,
        resource_policy_ref=resource_policy_ref,
        contract_target_id="foundry.causal.hte_observational_data.v1",
        contract_target_fqn=(
            "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
        ),
        resource_policy_digest=resource_policy.digest(),
        source_governance=governance,
        source_access_revalidation_status="not_established",
        limitations=(
            "candidate_input_not_external_truth",
            "scientific_validity_not_established",
            "units_and_context_not_established",
            "source_access_revalidation_not_established",
        ),
    )
    requested_payload = requested_intent.model_dump(mode="json")
    if missing_requested_limitation:
        requested_payload["limitations"] = [
            limitation
            for limitation in requested_payload["limitations"]
            if limitation != "scientific_validity_not_established"
        ]
    requested_input_edges = _observational_run_intent_input_edges(requested_intent)
    requested_intent_ref = _put_selected_json(
        store,
        requested_payload,
        kind="runtime.observational_run_intent",
        schema=SchemaInfo(name="polisyos.runtime.ObservationalRunIntent", version="1.0"),
        inputs=tuple(_input_edge(ref, role) for ref, role in requested_input_edges),
        governance=governance,
    )

    if protocol == "method_input_envelope_v1":
        effective_ref = source_ref
        normalization = "canonical_passthrough"
    else:
        effective_ref = _put_selected_json(
            store,
            {
                "schema_version": "policyos.ir.observation.method_input_envelope.v1",
                "contract_target": ("foundry.causal.hte_observational_data.v1"),
                "observational_data": {"data": [1, 2, 3]},
            },
            kind="ir.observation_method_input",
            schema=envelope_schema,
            inputs=(
                _input_edge(
                    other_source_ref if wrong_effective_source_input else source_ref,
                    "legacy_hte_json_v1_source",
                ),
            ),
            governance=governance,
        )
        normalization = "legacy_to_method_input_envelope_v1"

    admitted_intent = ContentAdmittedObservationalRunIntent(
        job_id="job-direct-cas",
        run_id="run-direct-cas",
        attempt=1,
        requested_intent_ref=requested_intent_ref,
        requested_source_ref=source_ref,
        source_manifest_sha256=source_manifest_sha256,
        resource_policy_ref=resource_policy_ref,
        submitted_input_ref=source_ref,
        effective_input_ref=effective_ref,
        contract_target_id="foundry.causal.hte_observational_data.v1",
        contract_target=("polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"),
        method_fqn="causal.hte.forest_dr@1.1.0",
        source_protocol=protocol,
        normalization=normalization,
        limitations=(
            "candidate_input_not_external_truth",
            "scientific_validity_not_established",
            "units_and_context_not_established",
            "source_access_revalidation_not_established",
            *(
                ("legacy_hte_json_v1_source_normalized",)
                if protocol == "legacy_hte_json_v1"
                else ()
            ),
        ),
        source_governance=governance,
        source_access_revalidation_status="not_established",
        selection_digest=requested_intent.selection_digest(),
        observed_manifest_bytes=usage_read.observed_manifest_bytes,
        observed_manifest_selection_bytes=usage_read.observed_manifest_selection_bytes,
        observed_manifest_verification_bytes=usage_read.observed_manifest_verification_bytes,
        observed_payload_bytes=usage_read.observed_payload_bytes,
        observed_source_bytes=usage_read.observed_source_bytes,
        payload_integrity_verified=usage_read.payload_integrity_verified,
        observed_bytes=usage_read.observed_bytes,
        observed_depth=usage_read.observed_depth,
        observed_elements=usage_read.observed_elements,
        resource_policy_digest=resource_policy.digest(),
    )
    admitted_payload = admitted_intent.model_dump(mode="json")
    if wrong_admitted_target_id:
        admitted_payload["contract_target_id"] = "foundry.causal.hte_observational_data.v0"
    if wrong_admitted_usage_total:
        admitted_payload["observed_source_bytes"] += 1
    if wrong_admitted_usage_limit:
        admitted_payload["observed_payload_bytes"] = limits.max_bytes + 1
        admitted_payload["observed_bytes"] = limits.max_bytes + 1
        admitted_payload["observed_source_bytes"] = (
            admitted_payload["observed_manifest_selection_bytes"]
            + admitted_payload["observed_manifest_verification_bytes"]
            + admitted_payload["observed_payload_bytes"]
        )
    if missing_admitted_limitation:
        admitted_payload["limitations"] = [
            limitation
            for limitation in admitted_payload["limitations"]
            if limitation != "scientific_validity_not_established"
        ]
    admitted_input_edges = _content_admitted_intent_input_edges(admitted_intent)
    content_admitted_ref = _put_selected_json(
        store,
        admitted_payload,
        kind="runtime.content_admitted_observational_run_intent",
        schema=SchemaInfo(
            name="polisyos.runtime.ContentAdmittedObservationalRunIntent",
            version="1.0",
        ),
        inputs=tuple(_input_edge(ref, role) for ref, role in admitted_input_edges),
        governance=governance,
    )

    wrong_ref = _put_selected_json(
        store,
        {"data": [9]},
        kind="ir.observation_method_input",
        schema=envelope_schema,
        governance=governance,
    )
    result_lineage = (
        ("requested_source", source_ref),
        ("observational_run_intent", requested_intent_ref),
        ("content_admitted_intent", content_admitted_ref),
        ("submitted_method_input", source_ref),
        ("effective_method_input", wrong_ref if wrong_result_input else effective_ref),
        ("method_resource_policy", resource_policy_ref),
    )
    result_ref = _put_selected_json(
        store,
        {"result": {"effect": 0.1}},
        kind="scientist.method_result.causal.hte",
        schema=(
            SchemaInfo(name="polisyos.scientist.OtherResult", version="0.1.0")
            if wrong_result_schema
            else SchemaInfo(name="polisyos.scientist.MethodResult", version="0.1.0")
        ),
        inputs=tuple(_input_edge(ref, role) for role, ref in result_lineage),
        governance=None if remove_result_governance else governance,
    )
    evidence_result_ref = wrong_ref if wrong_evidence_result_ref else result_ref
    evidence_payload = {
        "authority_purpose": "method_execution",
        "method_fqn": (
            "causal.hte.other@1.1.0" if wrong_evidence_method_fqn else "causal.hte.forest_dr@1.1.0"
        ),
        "method_version": "1.1.0",
        "method_abi_digest": requested_intent.method_abi_digest,
        "method_build_digest": requested_intent.method_build_digest,
        "method_build_digest_scope": "class_source_only",
        "resource_policy_digest": resource_policy.digest(),
        "resource_policy_ref": resource_policy_ref.model_dump(mode="json"),
        "source_protocol": protocol,
        "normalization": normalization,
        "limitations": list(
            _expected_content_admitted_limitations(
                protocol,
                source_access_revalidation_status=None,
            )
        ),
        "requested_source_ref": source_ref.model_dump(mode="json"),
        "observational_run_intent_ref": requested_intent_ref.model_dump(mode="json"),
        "content_admitted_intent_ref": content_admitted_ref.model_dump(mode="json"),
        "submitted_input_ref": source_ref.model_dump(mode="json"),
        "effective_input_ref": effective_ref.model_dump(mode="json"),
        "result_ref": str(evidence_result_ref.artifact_id),
        "method_result_ref": evidence_result_ref.model_dump(mode="json"),
    }
    evidence_lineage = (("method_result", result_ref), *result_lineage)
    if wrong_evidence_input:
        evidence_lineage = (("method_result", wrong_ref), *result_lineage)
    evidence_ref = _put_selected_json(
        store,
        evidence_payload,
        kind="scientist.method_evidence",
        schema=SchemaInfo(
            name=(
                "polisyos.scientist.OtherMethodEvidence"
                if wrong_evidence_schema
                else "polisyos.scientist.MethodExecutionEvidence"
            ),
            version="0.1.0",
        ),
        inputs=tuple(_input_edge(ref, role) for role, ref in evidence_lineage),
        governance=None if remove_evidence_governance else governance,
    )
    selection = DirectMethodExecutionSelection(
        job_id="job-direct-cas",
        run_id="run-direct-cas",
        attempt=1,
        requested_source_ref=source_ref,
        observational_run_intent_ref=requested_intent_ref,
        content_admitted_intent_ref=content_admitted_ref,
        resource_policy_ref=resource_policy_ref,
        submitted_input_ref=source_ref,
        effective_input_ref=effective_ref,
        method_result_ref=result_ref,
        method_evidence_ref=evidence_ref,
        contract_target_id="foundry.causal.hte_observational_data.v1",
        contract_target=("polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"),
        selection_digest=requested_intent.selection_digest(),
        source_access_revalidation_status="not_established",
        method_fqn="causal.hte.forest_dr@1.1.0",
        method_version="1.1.0",
        method_abi_digest=requested_intent.method_abi_digest,
        method_build_digest=requested_intent.method_build_digest,
        method_build_digest_scope="class_source_only",
        resource_policy_digest=resource_policy.digest(),
        source_protocol=protocol,
        normalization=normalization,
        limitations=admitted_intent.limitations,
        method_dispatch_binding_status="recomputed",
        posterior_summary_refs=(),
    )
    return store, selection, limits


def _shared_guard_vectors() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "envelope_raw_classification_missing_typed_default_public",
            "protocol": "method_input_envelope_v1",
            "selected_raw_manifest_fields": {
                "kind": "ir.observation_method_input",
                "media_type": "application/json",
                "schema": {
                    "name": "polisyos.ir.ObservationMethodInputEnvelope",
                    "version": "1.0",
                },
                "governance": {},
            },
            "parsed_typed_manifest_governance": {"classification": "public"},
            "expected": "refuse_before_enqueue_and_http_post",
        },
        {
            "case_id": "legacy_raw_classification_missing_typed_default_public",
            "protocol": "legacy_hte_json_v1",
            "selected_raw_manifest_fields": {
                "kind": "ir.observational_data",
                "media_type": "application/json",
                "schema": None,
                "governance": {},
            },
            "parsed_typed_manifest_governance": {"classification": "public"},
            "expected": "refuse_before_enqueue_and_http_post",
        },
    ]


@pytest.mark.parametrize(
    ("protocol", "normalization"),
    [
        ("method_input_envelope_v1", "canonical_passthrough"),
        ("legacy_hte_json_v1", "legacy_to_method_input_envelope_v1"),
    ],
)
def test_direct_selection_revalidates_real_cas_manifests_and_result_edges(
    tmp_path: Path,
    protocol: str,
    normalization: str,
) -> None:
    store, selection, limits = _direct_method_cas_case(tmp_path, protocol=protocol)

    assert selection.normalization == normalization
    expected_limitations = (
        "candidate_input_not_external_truth",
        "scientific_validity_not_established",
        "units_and_context_not_established",
        "source_access_revalidation_not_established",
        *(("legacy_hte_json_v1_source_normalized",) if protocol == "legacy_hte_json_v1" else ()),
    )
    assert selection.limitations == expected_limitations
    _validate_direct_method_execution_selection_artifacts(
        store=store,
        selection=selection,
        limits=limits,
    )


@pytest.mark.parametrize("wrong_schema", ["result", "evidence"])
def test_direct_selection_rejects_method_output_with_unowned_schema(
    tmp_path: Path,
    wrong_schema: str,
) -> None:
    store, selection, limits = _direct_method_cas_case(
        tmp_path,
        wrong_result_schema=wrong_schema == "result",
        wrong_evidence_schema=wrong_schema == "evidence",
    )

    with pytest.raises(ValueError, match="direct_method_execution_manifest_contract_mismatch"):
        _validate_direct_method_execution_selection_artifacts(
            store=store,
            selection=selection,
            limits=limits,
        )


@pytest.mark.parametrize("wrong_edge", ["result", "evidence"])
def test_direct_selection_rejects_result_or_evidence_edge_profile_substitution(
    tmp_path: Path,
    wrong_edge: str,
) -> None:
    store, selection, limits = _direct_method_cas_case(
        tmp_path,
        wrong_result_input=wrong_edge == "result",
        wrong_evidence_input=wrong_edge == "evidence",
    )

    with pytest.raises(ValueError, match="direct_method_execution_output_lineage_mismatch"):
        _validate_direct_method_execution_selection_artifacts(
            store=store,
            selection=selection,
            limits=limits,
        )


def test_content_admitted_lineage_recipe_checks_roles_profiles_and_multiplicity() -> None:
    source = _selected_ref("ir.observation_method_input", "1", "a")
    requested = _selected_ref("runtime.observational_run_intent", "2", "b")
    policy = _selected_ref("runtime.observational_input_resource_policy", "3", "c")
    binding = _selected_ref("runtime.search_uncertainty_task_binding", "4", "d")
    projection = _selected_ref("runtime.search_uncertainty_task_projection", "5", "e")
    task_admission = _selected_ref("runtime.search_uncertainty_task_admission", "6", "f")
    task_epoch = _selected_ref("runtime.search_uncertainty_task_epoch", "7", "0")
    owner_context = _selected_ref("runtime.search_uncertainty_owner_context", "8", "1")
    basis = _selected_ref("runtime.search_uncertainty_task_basis", "9", "2")
    inventory = _selected_ref("runtime.search_uncertainty_dependency_inventory", "a", "3")
    intent = SimpleNamespace(
        requested_intent_ref=requested,
        requested_source_ref=source,
        resource_policy_ref=policy,
        submitted_input_ref=source,
        effective_input_ref=source,
        search_binding_admission=SimpleNamespace(
            binding_ref=binding,
            projection_ref=projection,
            task_admission_ref=task_admission,
            task_epoch_ref=task_epoch,
            owner_context_ref=owner_context,
            basis_ref=basis,
            dependency_inventory_ref=inventory,
            source_projection_ref=projection,
        ),
    )

    expected = _content_admitted_intent_input_edges(intent)
    roles = tuple(role for _ref, role in expected)
    assert roles == (
        "observational_run_intent",
        "requested_source",
        "resource_policy",
        "submitted_input",
        "effective_input",
        "search_uncertainty_task_binding",
        "search_uncertainty_task_projection",
        "search_uncertainty_task_admission",
        "search_uncertainty_task_epoch",
        "search_uncertainty_owner_context",
        "search_uncertainty_task_basis",
        "search_uncertainty_dependency_inventory",
        "search_uncertainty_source_projection",
    )
    source_roles = {"requested_source", "submitted_input", "effective_input"}
    assert [ref.artifact_id for ref, role in expected if role in source_roles] == [
        source.artifact_id,
        source.artifact_id,
        source.artifact_id,
    ]
    projection_roles = {
        "search_uncertainty_task_projection",
        "search_uncertainty_source_projection",
    }
    assert [ref.artifact_id for ref, role in expected if role in projection_roles] == [
        projection.artifact_id,
        projection.artifact_id,
    ]

    edges = tuple(_input_edge(ref, role) for ref, role in expected)
    assert _has_exact_selected_input_edges(edges, expected)
    assert _has_exact_selected_input_edges(tuple(reversed(edges)), expected)

    swapped_roles = list(edges)
    swapped_roles[1] = _input_edge(source, "resource_policy")
    swapped_roles[2] = _input_edge(policy, "requested_source")
    assert not _has_exact_selected_input_edges(tuple(swapped_roles), expected)
    assert not _has_exact_selected_input_edges(edges[:-1], expected)
    assert not _has_exact_selected_input_edges((*edges, edges[0]), expected)

    wrong_id = list(edges)
    wrong_id[1] = _input_edge(_selected_ref(source.kind, "b", "a"), "requested_source")
    assert not _has_exact_selected_input_edges(tuple(wrong_id), expected)
    wrong_profile = list(edges)
    wrong_profile[1] = _input_edge(_selected_ref(source.kind, "1", "b"), "requested_source")
    assert not _has_exact_selected_input_edges(tuple(wrong_profile), expected)
    with pytest.raises(ValueError, match="observational_method_resource_policy_ref_missing"):
        _observational_run_intent_input_edges(
            cast(
                "ObservationalRunIntent",
                SimpleNamespace(
                    requested_source_ref=source,
                    resource_policy_ref=None,
                ),
            )
        )


def test_legacy_normalization_requires_exact_full_source_lineage(tmp_path: Path) -> None:
    store, selection, limits = _direct_method_cas_case(
        tmp_path,
        protocol="legacy_hte_json_v1",
        wrong_effective_source_input=True,
    )

    with pytest.raises(
        ValueError, match="direct_method_execution_effective_input_lineage_mismatch"
    ):
        _validate_direct_method_execution_selection_artifacts(
            store=store,
            selection=selection,
            limits=limits,
        )


@pytest.mark.parametrize("mismatch", ["method", "result_ref"])
def test_direct_selection_rechecks_evidence_content_identity(
    tmp_path: Path,
    mismatch: str,
) -> None:
    store, selection, limits = _direct_method_cas_case(
        tmp_path,
        wrong_evidence_method_fqn=mismatch == "method",
        wrong_evidence_result_ref=mismatch == "result_ref",
    )

    with pytest.raises(ValueError, match="direct_method_execution_evidence_content_mismatch"):
        _validate_direct_method_execution_selection_artifacts(
            store=store,
            selection=selection,
            limits=limits,
        )


@pytest.mark.parametrize("removed_output", ["result", "evidence"])
def test_direct_selection_rejects_output_governance_removal(
    tmp_path: Path,
    removed_output: str,
) -> None:
    store, selection, limits = _direct_method_cas_case(
        tmp_path,
        remove_result_governance=removed_output == "result",
        remove_evidence_governance=removed_output == "evidence",
    )

    with pytest.raises(ValueError):
        _validate_direct_method_execution_selection_artifacts(
            store=store,
            selection=selection,
            limits=limits,
        )


@pytest.mark.parametrize("mutation", ["aggregate_mismatch", "limit_exceeded"])
def test_direct_selection_rejects_invalid_measured_read_usage_in_selected_cas(
    tmp_path: Path,
    mutation: str,
) -> None:
    store, selection, limits = _direct_method_cas_case(
        tmp_path,
        wrong_admitted_usage_total=mutation == "aggregate_mismatch",
        wrong_admitted_usage_limit=mutation == "limit_exceeded",
    )

    with pytest.raises(ValueError):
        _validate_direct_method_execution_selection_artifacts(
            store=store,
            selection=selection,
            limits=limits,
        )


def test_direct_selection_rejects_wrong_contract_target_id_in_admitted_cas(
    tmp_path: Path,
) -> None:
    store, selection, limits = _direct_method_cas_case(
        tmp_path,
        wrong_admitted_target_id=True,
    )

    with pytest.raises(ValueError):
        _validate_direct_method_execution_selection_artifacts(
            store=store,
            selection=selection,
            limits=limits,
        )


def test_direct_selection_rejects_missing_requested_limitation_in_selected_cas(
    tmp_path: Path,
) -> None:
    store, selection, limits = _direct_method_cas_case(
        tmp_path,
        missing_requested_limitation=True,
    )

    # Strict Literal validation may reject a missing member before the
    # cross-field model validator supplies its stable diagnostic.
    with pytest.raises(ValueError):
        _validate_direct_method_execution_selection_artifacts(
            store=store,
            selection=selection,
            limits=limits,
        )


def test_direct_selection_rejects_missing_admitted_limitation_in_selected_cas(
    tmp_path: Path,
) -> None:
    store, selection, limits = _direct_method_cas_case(
        tmp_path,
        missing_admitted_limitation=True,
    )

    with pytest.raises(ValueError, match="content_admitted_observational_limitations_invalid"):
        _validate_direct_method_execution_selection_artifacts(
            store=store,
            selection=selection,
            limits=limits,
        )


def test_direct_selection_rejects_stripped_limitations_against_selected_cas(tmp_path: Path) -> None:
    store, selection, limits = _direct_method_cas_case(
        tmp_path,
        protocol="legacy_hte_json_v1",
    )
    stripped_selection = selection.model_copy(
        update={
            "limitations": (
                "candidate_input_not_external_truth",
                "units_and_context_not_established",
                "legacy_hte_json_v1_source_normalized",
            )
        }
    )

    with pytest.raises(ValueError, match="direct_method_execution_intent_lineage_mismatch"):
        _validate_direct_method_execution_selection_artifacts(
            store=store,
            selection=stripped_selection,
            limits=limits,
        )


@pytest.mark.parametrize("output", ["result", "evidence"])
def test_direct_selection_rejects_unrelated_output_kind(
    tmp_path: Path,
    output: str,
) -> None:
    store, selection, limits = _direct_method_cas_case(tmp_path)
    unrelated = _selected_ref("unrelated.output", "f", "f")
    altered = selection.model_copy(
        update={"method_result_ref" if output == "result" else "method_evidence_ref": unrelated}
    )

    with pytest.raises(ValueError):
        _validate_direct_method_execution_selection_artifacts(
            store=store,
            selection=altered,
            limits=limits,
        )


def test_direct_selection_rejects_resource_policy_profile_substitution(tmp_path: Path) -> None:
    store, selection, limits = _direct_method_cas_case(tmp_path)
    substituted_policy_ref = selection.resource_policy_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "f" * 64}
    )
    altered = selection.model_copy(update={"resource_policy_ref": substituted_policy_ref})

    with pytest.raises(ValueError, match="direct_method_execution_intent_lineage_mismatch"):
        _validate_direct_method_execution_selection_artifacts(
            store=store,
            selection=altered,
            limits=limits,
        )


def test_direct_selection_rechecks_requested_method_build_pins(tmp_path: Path) -> None:
    store, selection, limits = _direct_method_cas_case(tmp_path)
    mismatched_selection = selection.model_copy(update={"method_build_digest": "c" * 64})

    with pytest.raises(ValueError, match="direct_method_execution_intent_lineage_mismatch"):
        _validate_direct_method_execution_selection_artifacts(
            store=store,
            selection=mismatched_selection,
            limits=limits,
        )


def test_direct_selection_rejects_a_different_selected_result_profile(tmp_path: Path) -> None:
    store, selection, limits = _direct_method_cas_case(tmp_path)
    substituted_ref = selection.method_result_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "f" * 64}
    )
    substituted_selection = selection.model_copy(update={"method_result_ref": substituted_ref})

    with pytest.raises(ValueError):
        _validate_direct_method_execution_selection_artifacts(
            store=store,
            selection=substituted_selection,
            limits=limits,
        )


def _unconsumed_observational_http_field_cases() -> tuple[tuple[str, object], ...]:
    """Derive the explicit-field rejection cases from the full request model."""
    fields = set(WorkflowRunRequest.model_fields).difference(
        _OBSERVATIONAL_INPUT_CONSUMED_REQUEST_FIELDS
    )
    cases: list[tuple[str, object]] = []
    for name in sorted(fields):
        model_field = WorkflowRunRequest.model_fields[name]
        if name == "registry_bundle_ref":
            cases.append(
                (name, _selected_ref("core.registry_bundle", "c", "d").model_dump(mode="json"))
            )
            continue
        if name == "checkpoint_policy":
            cases.append((name, model_field.default))
            continue
        cases.append((name, "sha256:" + "c" * 64))
        if model_field.default is None:
            cases.append((name, None))
    return tuple(cases)


@pytest.mark.parametrize(
    ("field", "value"),
    _unconsumed_observational_http_field_cases(),
    ids=lambda value: str(value) if value is None else None,
)
def test_http_post_rejects_every_silently_dropped_observational_workflow_field(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    service = runtime_api_env["app"].state._control_service
    launch_calls: list[object] = []

    def record_launch(*args: object, **kwargs: object) -> None:
        launch_calls.append((args, kwargs))

    monkeypatch.setattr(service, "launch_workflow_run", record_launch)
    body: dict[str, object] = {
        "observational_input": {
            "protocol": "method_input_envelope_v1",
            "source_ref": _selected_ref(
                "ir.observation_method_input",
                "a",
                "b",
            ).model_dump(mode="json"),
            "method": {"fqn": "causal.hte.forest_dr@1.0.0"},
        },
        field: value,
    }
    response = runtime_api_env["client"].post("/api/v1/control/runs", json=body)

    assert response.status_code == 422
    assert f"observational_input_unconsumed_request_fields:{field}" in response.text
    assert launch_calls == []


@pytest.mark.parametrize(
    "data_source",
    [
        {},
        {"input_bindings_ref": ""},
        {"data_snapshot_ref": ""},
    ],
)
def test_http_post_rejects_empty_present_observational_data_source(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    data_source: dict[str, str],
) -> None:
    service = runtime_api_env["app"].state._control_service
    launch_calls: list[object] = []

    def record_launch(*args: object, **kwargs: object) -> None:
        launch_calls.append((args, kwargs))

    monkeypatch.setattr(service, "launch_workflow_run", record_launch)
    response = runtime_api_env["client"].post(
        "/api/v1/control/runs",
        json={
            "observational_input": {
                "protocol": "method_input_envelope_v1",
                "source_ref": _selected_ref(
                    "ir.observation_method_input",
                    "a",
                    "b",
                ).model_dump(mode="json"),
                "method": {"fqn": "causal.hte.forest_dr@1.0.0"},
            },
            "data_source": data_source,
        },
    )

    assert response.status_code == 422
    assert "observational_input_data_source_conflict" in response.text
    assert launch_calls == []


def _runtime_hte_source_payload(
    *,
    n_obs: int = 40,
    source_label: str = "synthetic_candidate",
    source_only_sample_id: str | None = None,
) -> dict[str, object]:
    """Build a source payload whose field set follows the actual HTE producer DTO."""
    sample_ids = [f"candidate-{index}" for index in range(n_obs)]
    if source_only_sample_id is not None:
        sample_ids[0] = source_only_sample_id
    payload: dict[str, object] = {
        "outcome": [float(index) / 10 + (index % 2) * 0.5 for index in range(n_obs)],
        "treatment": [index % 2 for index in range(n_obs)],
        "covariates": [[float(index), float(index % 5)] for index in range(n_obs)],
        "confounders": [[float(index % 7)] for index in range(n_obs)],
        "feature_names": ["age", "baseline"],
        "confounder_names": ["risk"],
        "sample_ids": sample_ids,
        "metadata": {"source": source_label},
    }
    from _helpers.hte_privacy import hte_source_data_field_names

    if set(payload) != hte_source_data_field_names():
        raise AssertionError("test_hte_source_fixture_does_not_match_producer_dto")
    return payload


def _put_runtime_observational_source(
    service: Any,
    *,
    classification: str = "public",
    tenant_context: ArtifactTenantContextInfo | None = None,
    owner_scope: tuple[str, str] | None = None,
    source_label: str = "synthetic_candidate",
    n_obs: int = 40,
    inputs: tuple[InputRef, ...] = (),
    source_only_sample_id: str | None = None,
    contract_target_id: str = "foundry.causal.hte_observational_data.v1",
    contract_target_fqn: str = (
        "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
    ),
) -> ArtifactRef:
    contract_payload = _runtime_hte_source_payload(
        source_label=source_label,
        source_only_sample_id=source_only_sample_id,
        n_obs=n_obs,
    )

    def put_source() -> ArtifactRef:
        return _put_selected_json(
            service._artifact_store,
            {
                "schema_version": "policyos.ir.observation.method_input_envelope.v1",
                "contract_target": {
                    "contract_id": contract_target_id,
                    "contract_fqn": contract_target_fqn,
                },
                "contract_payload": contract_payload,
            },
            kind="ir.observation_method_input",
            schema=SchemaInfo(
                name="polisyos.ir.ObservationMethodInputEnvelope",
                version="1.0",
            ),
            inputs=inputs,
            governance=ArtifactGovernanceInfo(classification=classification),
            tenant_context=tenant_context,
        )

    if owner_scope is None:
        return put_source()
    from polisyos.core.security.tenant_context import tenant_scope

    with tenant_scope(None, tenant_id=owner_scope[0], cell_id=owner_scope[1]):
        return put_source()


def _put_runtime_legacy_observational_source(
    service: Any,
    *,
    classification: str = "public",
    tenant_context: ArtifactTenantContextInfo | None = None,
    owner_scope: tuple[str, str] | None = None,
    source_only_sample_id: str | None = None,
) -> ArtifactRef:
    payload = _runtime_hte_source_payload(source_only_sample_id=source_only_sample_id)

    def put_source() -> ArtifactRef:
        return _put_selected_json(
            service._artifact_store,
            payload,
            kind="ir.observational_data",
            schema=None,
            governance=ArtifactGovernanceInfo(classification=classification),
            tenant_context=tenant_context,
        )

    if owner_scope is None:
        return put_source()
    from polisyos.core.security.tenant_context import tenant_scope

    with tenant_scope(None, tenant_id=owner_scope[0], cell_id=owner_scope[1]):
        return put_source()


def _post_runtime_api_as_fixture_owner(
    runtime_api_env: dict[str, Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    from polisyos.core.security.tenant_context import tenant_scope

    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        return runtime_api_env["client"].post(*args, **kwargs)


@pytest.mark.parametrize("cancelled_before_start", [True, False])
def test_bounded_shared_executor_wait_preserves_timeout_disposition(
    cancelled_before_start: bool,
) -> None:
    from polisyos.common.async_tools import SharedExecutorWaitTimeoutError
    from polisyos.core.contracts.bounded_liveness import BoundedLivenessConfig
    from polisyos.runtime.http.services.control.bounded_wait import (
        ControlProducerWaitTimeoutError,
        wait_for_shared_execution,
    )

    resolution = BoundedLivenessConfig(
        default_deadline_s=0.25,
        default_retry_ceiling=0,
    ).resolve("runtime.observational_method_execution", requested_retries=0)

    class TimedOutHandle:
        def result(self, timeout: float | None = None) -> object:
            assert timeout == resolution.deadline_s
            raise SharedExecutorWaitTimeoutError(
                cancelled_before_start=cancelled_before_start,
            )

    with pytest.raises(ControlProducerWaitTimeoutError) as raised:
        wait_for_shared_execution(TimedOutHandle(), resolution)

    assert raised.value.cancelled_before_start is cancelled_before_start
    assert raised.value.running_slot_retained is (not cancelled_before_start)
    assert raised.value.retryable is False
    assert raised.value.diagnostic()["wait_disposition"] == (
        "cancelled_before_start" if cancelled_before_start else "running_slot_retained"
    )


def test_shared_execution_failure_preserves_bounded_identity_without_raw_message() -> None:
    from polisyos.core.contracts.bounded_liveness import BoundedLivenessConfig
    from polisyos.runtime.http.services.control.bounded_wait import (
        ControlProducerExecutionError,
        require_shared_execution_value,
    )

    resolution = BoundedLivenessConfig(
        default_deadline_s=0.25,
        default_retry_ceiling=0,
    ).resolve("runtime.observational_method_execution", requested_retries=0)
    completion = SimpleNamespace(
        status="failed",
        value=None,
        failure=SimpleNamespace(
            exception_type="ValueError",
            code="bounded_method_input_invalid",
            message_excerpt="candidate payload must not enter public progress",
            retryable=False,
        ),
    )

    with pytest.raises(ControlProducerExecutionError) as raised:
        require_shared_execution_value(completion, resolution)

    diagnostic = raised.value.diagnostic()
    assert diagnostic["exception_type"] == "ValueError"
    assert diagnostic["code"] == "bounded_method_input_invalid"
    assert diagnostic["retryable"] is False
    assert "message_excerpt" not in diagnostic
    assert "candidate payload" not in str(diagnostic)


def test_graph_projection_timeout_keeps_exact_source_and_withholds_admission(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.common.async_tools import SharedExecutorWaitTimeoutError
    from polisyos.core.contracts.bounded_liveness import BoundedLivenessConfig

    service = runtime_api_env["app"].state._control_service
    resolution = BoundedLivenessConfig(
        default_deadline_s=0.25,
        default_retry_ceiling=0,
    ).resolve("runtime.method_metric_projection", requested_retries=0)
    service._method_metric_projection_wait_policy = resolution
    submitted: list[object] = []

    class TimedOutHandle:
        def result(self, timeout: float | None = None) -> object:
            assert timeout == resolution.deadline_s
            raise SharedExecutorWaitTimeoutError(cancelled_before_start=False)

    def submit(work: object) -> TimedOutHandle:
        submitted.append(work)
        return TimedOutHandle()

    monkeypatch.setattr(service._method_backend, "submit_method_metric_projection_work", submit)
    source_refs = (
        _selected_ref("foundry.simulation_result", "1", "a"),
        _selected_ref("foundry.method_execution_bundle", "2", "b"),
        _selected_ref("foundry.method_metric_binding_set", "3", "c"),
    )
    job = SimpleNamespace(
        job_id="job-timeout",
        run_id="run-timeout",
        attempt=2,
        lease_owner="lease-timeout",
    )

    admission, diagnostic = service._submit_graph_metric_projection(
        job=job,
        source_refs=source_refs,
    )

    assert admission is None
    assert diagnostic is not None
    assert diagnostic["wait_disposition"] == "running_slot_retained"
    assert len(submitted) == 1
    work = submitted[0]
    assert work.simulation_result_ref == source_refs[0]
    assert work.method_execution_bundle_ref == source_refs[1]
    assert work.method_metric_binding_set_ref == source_refs[2]
    assert work.method_result_ref is None


@pytest.mark.parametrize(
    "scope_kind",
    ["restricted", "foreign_tenant_scoped"],
)
def test_http_post_refuses_restricted_or_foreign_tenant_source_before_enqueue(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    scope_kind: str,
) -> None:
    runtime_api_env = request.getfixturevalue("selected_source_runtime_api_env")
    service = runtime_api_env["app"].state._control_service
    queued: list[object] = []
    monkeypatch.setattr(service, "_enqueue_job", lambda **kwargs: queued.append(kwargs))
    classification = "restricted" if scope_kind == "restricted" else "public"
    owner_scope = (runtime_api_env["tenant_a"], runtime_api_env["cell_a"])
    tenant_context = None
    if scope_kind == "foreign_tenant_scoped":
        owner_scope = ("tenant-private", "cell-private")
        tenant_context = ArtifactTenantContextInfo(
            tenant_id="tenant-private",
            cell_id="cell-private",
        )
    source_ref = _put_runtime_observational_source(
        service,
        classification=classification,
        tenant_context=tenant_context,
        owner_scope=owner_scope,
    )

    response = _post_runtime_api_as_fixture_owner(
        runtime_api_env,
        "/api/v1/control/runs",
        json={
            "observational_input": {
                "protocol": "method_input_envelope_v1",
                "source_ref": source_ref.model_dump(mode="json"),
                "method": {"fqn": "causal.hte.forest_dr@1.1.0"},
            }
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "observational_source_current_access_not_established"
    assert queued == []


def test_http_post_accepts_currently_owned_public_tenant_scoped_source(
    request: pytest.FixtureRequest,
) -> None:
    """The retained Cloud positive uses authenticated scope, not ambient identity."""
    case = request.getfixturevalue("scoped_source_runtime")
    source_ref = _put_runtime_observational_source(
        case["service"],
        owner_scope=(case["tenant_a"], case["cell"]),
        tenant_context=ArtifactTenantContextInfo(tenant_id=case["tenant_a"], cell_id=case["cell"]),
    )
    response = case["client"].post(
        "/api/v1/control/runs",
        headers=case["headers_a"],
        json={
            "observational_input": {
                "protocol": "method_input_envelope_v1",
                "source_ref": source_ref.model_dump(mode="json"),
                "method": {"fqn": "causal.hte.forest_dr@1.1.0"},
            }
        },
    )
    assert response.status_code == 200, response.text


def test_http_post_refuses_source_without_owner_claim_before_enqueue(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_api_env = request.getfixturevalue("selected_source_runtime_api_env")
    service = runtime_api_env["app"].state._control_service
    queued: list[object] = []
    monkeypatch.setattr(service, "_enqueue_job", lambda **kwargs: queued.append(kwargs))
    source_ref = _put_runtime_observational_source(service)
    assert not service._artifact_store._ownership_index.has_any_tenant_claim(source_ref.artifact_id)

    response = _post_runtime_api_as_fixture_owner(
        runtime_api_env,
        "/api/v1/control/runs",
        json={
            "observational_input": {
                "protocol": "method_input_envelope_v1",
                "source_ref": source_ref.model_dump(mode="json"),
                "method": {"fqn": "causal.hte.forest_dr@1.1.0"},
            }
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "observational_source_current_access_not_established"
    assert queued == []


def test_http_post_maps_typed_non_owner_manifest_bounds_refusal_to_422(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.core.artifacts import ArtifactReadBoundsError
    from polisyos.core.artifacts.canonical_profile import CoreJsonReadBoundsRefusalError
    from polisyos.core.security.tenant_context import tenant_scope

    service = runtime_api_env["app"].state._control_service
    queued: list[object] = []
    monkeypatch.setattr(service, "_enqueue_job", lambda **kwargs: queued.append(kwargs))
    owner_scope = (runtime_api_env["tenant_a"], runtime_api_env["cell_a"])
    source_ref = _put_runtime_observational_source(service, owner_scope=owner_scope)

    with tenant_scope(None, tenant_id=owner_scope[0], cell_id=owner_scope[1]):
        _manifest, governance, tenant_context, _sha256 = (
            service._read_observational_source_manifest(source_ref)
        )
    assert governance.classification == "public"
    assert tenant_context is None
    assert service._artifact_store._ownership_index.has_any_tenant_claim(source_ref.artifact_id)

    manifest_path = service._artifact_store._manifest_path_for_ref(
        source_ref.artifact_id,
        source_ref.manifest_profile_sha256,
    )
    selected_manifest = manifest_path.read_bytes()
    limits = service._observational_read_limits()
    assert len(selected_manifest) <= limits.max_manifest_bytes
    manifest_path.write_bytes(
        selected_manifest + b" " * (limits.max_manifest_bytes + 1 - len(selected_manifest))
    )

    with (
        tenant_scope(None, tenant_id=owner_scope[0], cell_id=owner_scope[1]),
        pytest.raises(CoreJsonReadBoundsRefusalError) as caught,
    ):
        service._read_observational_source_manifest(source_ref)
    read_error = caught.value.__cause__
    assert isinstance(read_error, ArtifactReadBoundsError)
    assert read_error.member == "manifest"
    assert read_error.observed_bytes > read_error.max_bytes

    response = _post_runtime_api_as_fixture_owner(
        runtime_api_env,
        "/api/v1/control/runs",
        json={
            "observational_input": {
                "protocol": "method_input_envelope_v1",
                "source_ref": source_ref.model_dump(mode="json"),
                "method": {"fqn": "causal.hte.forest_dr@1.1.0"},
            }
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "observational_source_manifest_not_admitted"
    assert queued == []


def test_bounded_intent_model_hydration_reifies_serialized_search_time(
    runtime_api_env: dict[str, Any],
) -> None:
    from datetime import UTC, datetime

    from polisyos.core.contracts.owned_attempt_anchor import (
        OwnedHTERequestContextV1,
        SelectedArtifactRef,
    )
    from polisyos.core.contracts.runtime import SearchUncertaintyTaskAdmissionSnapshot
    from polisyos.core.security.tenant_context import tenant_scope

    service = runtime_api_env["app"].state._control_service
    owner_scope = (runtime_api_env["tenant_a"], runtime_api_env["cell_a"])
    governance = ArtifactGovernanceInfo(classification="public")

    def persist_selected_fixture_ref(kind: str, label: str) -> ArtifactRef:
        return _put_selected_json(
            service._artifact_store,
            {"fixture": label},
            kind=kind,
            schema=None,
            governance=governance,
        )

    with tenant_scope(None, tenant_id=owner_scope[0], cell_id=owner_scope[1]):
        source_ref = _put_runtime_observational_source(service)
        requested_ref = persist_selected_fixture_ref(
            "runtime.observational_run_intent",
            "requested-intent",
        )
        policy_ref = persist_selected_fixture_ref(
            "runtime.observational_input_resource_policy",
            "resource-policy",
        )
        binding_ref = persist_selected_fixture_ref(
            "scientist.search.uncertainty_task_binding",
            "task-binding",
        )
        projection_ref = persist_selected_fixture_ref(
            "scientist.search.uncertainty_ticket_projection",
            "ticket-projection",
        )
        task_admission_ref = persist_selected_fixture_ref(
            "scientist.search.uncertainty_task_admission",
            "task-admission",
        )
        task_epoch_ref = persist_selected_fixture_ref(
            "scientist.search.uncertainty_task_epoch",
            "task-epoch",
        )
        owner_context_ref = persist_selected_fixture_ref(
            "scientist.search.uncertainty_owner_task_context",
            "owner-context",
        )
        basis_ref = persist_selected_fixture_ref(
            "scientist.search.uncertainty_basis",
            "basis",
        )
        inventory_ref = persist_selected_fixture_ref(
            "scientist.search.uncertainty_input_inventory",
            "dependency-inventory",
        )
        _manifest, _governance, source_tenant_context, source_manifest_sha256 = (
            service._read_observational_source_manifest(source_ref)
        )
    assert source_tenant_context is None
    binding_profile_ref = SelectedArtifactRef.model_validate(binding_ref.model_dump())
    resolved_at = datetime(2026, 10, 23, 5, 50, 1, 87389, tzinfo=UTC)
    method_params: dict[str, JsonValue] = {}
    method_params_sha256 = hashlib.sha256(b"{}").hexdigest()
    snapshot = SearchUncertaintyTaskAdmissionSnapshot(
        binding_ref=binding_ref,
        binding_content_sha256=binding_ref.artifact_id.hex,
        ticket_id="ticket-1",
        ticket_generation=1,
        owner_revision=1,
        projection_revision=1,
        projection_ref=projection_ref,
        task_admission_ref=task_admission_ref,
        task_epoch_ref=task_epoch_ref,
        owner_context_ref=owner_context_ref,
        basis_ref=basis_ref,
        dependency_inventory_ref=inventory_ref,
        dependency_inventory_sha256=hashlib.sha256(b"inventory").hexdigest(),
        source_projection_ref=projection_ref,
        selected_method_fqn="causal.hte.forest_dr@2.0.0",
        selected_method_abi_version="2.0.0",
        selected_method_abi_digest="a" * 64,
        selected_method_params=method_params,
        selected_method_params_sha256=method_params_sha256,
        selected_method_seed=7,
        selected_inference_profile_id="econml.forest_dr.native_mean@2.0",
        selected_method_input_ref=source_ref,
        selected_method_input_content_sha256=source_ref.artifact_id.hex,
        tenant_id=owner_scope[0],
        cell_id=owner_scope[1],
        resolved_at=resolved_at,
    )
    request_context = OwnedHTERequestContextV1(
        request_estimand_status="declared",
        request_estimand="average_treatment_effect",
        request_target_scope_status="declared",
        request_target_scope="sample",
        outcome_variable_status="declared",
        outcome_variable_id="outcome",
        treatment_variable_status="declared",
        treatment_variable_id="treatment",
        contrast_status="declared",
        control_value=0.0,
        treated_value=1.0,
        request_alpha_status="declared",
        requested_alpha=0.05,
        requested_guarantee_status="not_established",
        search_uncertainty_task_binding_ref=binding_profile_ref,
    )
    admitted_intent = ContentAdmittedObservationalRunIntent(
        schema_version="polisyos.runtime.content_admitted_observational_run_intent.v2",
        job_id="job-time-reader",
        run_id="run-time-reader",
        attempt=1,
        requested_intent_ref=requested_ref,
        requested_source_ref=source_ref,
        source_manifest_sha256=source_manifest_sha256,
        resource_policy_ref=policy_ref,
        submitted_input_ref=source_ref,
        effective_input_ref=source_ref,
        contract_target_id="foundry.causal.hte_observational_data.v1",
        contract_target="polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData",
        selection_digest="c" * 64,
        source_access_revalidation_status="not_established",
        method_fqn="causal.hte.forest_dr@2.0.0",
        owned_hte_request_context=request_context,
        search_binding_admission=snapshot,
        search_binding_tenant_id=owner_scope[0],
        search_binding_cell_id=owner_scope[1],
        source_protocol="method_input_envelope_v1",
        normalization="canonical_passthrough",
        limitations=_expected_content_admitted_limitations(
            "method_input_envelope_v1",
            source_access_revalidation_status="not_established",
        ),
        source_governance=ArtifactGovernanceInfo(classification="public"),
        observed_manifest_bytes=0,
        observed_manifest_selection_bytes=0,
        observed_manifest_verification_bytes=0,
        observed_payload_bytes=0,
        observed_source_bytes=0,
        payload_integrity_verified=True,
        observed_bytes=0,
        observed_depth=0,
        observed_elements=0,
        resource_policy_digest="d" * 64,
    )
    payload = admitted_intent.artifact_payload()
    assert payload["search_binding_admission"]["resolved_at"] == "2026-10-23T05:50:01.087389Z"
    with pytest.raises(ValueError):
        ContentAdmittedObservationalRunIntent.model_validate(payload, strict=True)

    input_refs = (
        (requested_ref, "requested_intent"),
        (source_ref, "requested_source"),
        (policy_ref, "resource_policy"),
        (source_ref, "submitted_input"),
        (source_ref, "effective_input"),
        (binding_ref, "search_uncertainty_task_binding"),
        (projection_ref, "search_uncertainty_task_projection"),
        (task_admission_ref, "search_uncertainty_task_admission"),
        (task_epoch_ref, "search_uncertainty_task_epoch"),
        (owner_context_ref, "search_uncertainty_owner_context"),
        (basis_ref, "search_uncertainty_task_basis"),
        (inventory_ref, "search_uncertainty_dependency_inventory"),
        (projection_ref, "search_uncertainty_source_projection"),
    )
    with tenant_scope(None, tenant_id=owner_scope[0], cell_id=owner_scope[1]):
        intent_ref = _put_selected_json(
            service._artifact_store,
            payload,
            kind="runtime.content_admitted_observational_run_intent",
            schema=SchemaInfo(
                name="polisyos.runtime.ContentAdmittedObservationalRunIntent",
                version="2.0",
            ),
            inputs=tuple(_input_edge(ref, role) for ref, role in input_refs),
            governance=ArtifactGovernanceInfo(classification="public"),
        )
        hydrated = service._read_bounded_intent_model(
            intent_ref,
            model=ContentAdmittedObservationalRunIntent,
        )

    assert hydrated.search_binding_admission is not None
    assert hydrated.search_binding_admission.resolved_at == resolved_at
    assert hydrated.search_binding_admission.resolved_at.tzinfo is not None


@pytest.mark.parametrize(
    ("protocol", "normalization"),
    [
        ("method_input_envelope_v1", "canonical_passthrough"),
        ("legacy_hte_json_v1", "legacy_to_method_input_envelope_v1"),
    ],
)
def test_post_worker_fenced_cas_and_fresh_run_get_preserve_candidate_limits(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    protocol: str,
    normalization: str,
) -> None:
    pytest.importorskip("econml")
    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker

    service = runtime_api_env["app"].state._control_service

    def reject_successor_anchor_use(**kwargs: Any) -> Any:
        _ = kwargs
        raise AssertionError("legacy v1 execution must not persist a successor anchor")

    monkeypatch.setattr(
        service,
        "persist_pre_output_owned_attempt_anchor",
        reject_successor_anchor_use,
    )
    monkeypatch.setattr(
        service,
        "persist_pre_output_hte_input_refusal_anchor",
        reject_successor_anchor_use,
    )
    stop_embedded_control_worker(service)
    owner_scope = (runtime_api_env["tenant_a"], runtime_api_env["cell_a"])
    source_only_sample_id = f"hte-source-only::post-worker-get::{protocol}"
    source_payload = _runtime_hte_source_payload(
        source_only_sample_id=source_only_sample_id,
    )
    source_ref = (
        _put_runtime_observational_source(
            service,
            owner_scope=owner_scope,
            source_only_sample_id=source_only_sample_id,
        )
        if protocol == "method_input_envelope_v1"
        else _put_runtime_legacy_observational_source(
            service,
            owner_scope=owner_scope,
            source_only_sample_id=source_only_sample_id,
        )
    )
    response = _post_runtime_api_as_fixture_owner(
        runtime_api_env,
        "/api/v1/control/runs",
        json={
            "observational_input": {
                "protocol": protocol,
                "source_ref": source_ref.model_dump(mode="json"),
                "method": {
                    "fqn": "causal.hte.forest_dr@1.1.0",
                    "params": {"n_estimators": 12, "cv_folds": 2, "subforest_size": 2},
                },
            }
        },
    )

    assert response.status_code == 200
    accepted = response.json()
    assert accepted["status"] == "accepted"
    intent_ref = ArtifactRef.model_validate(accepted["observational_run_intent_ref"])
    from polisyos.core.security.tenant_context import tenant_scope

    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        intent = ObservationalRunIntent.model_validate(
            service._read_bounded_intent_artifact(intent_ref)
        )
    assert accepted["observational_selection_digest"] == intent.selection_digest()
    job = service._control_store.get_job(accepted["job_id"])
    assert job is not None
    assert job.payload_ref is not None
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        payload = service._load_payload_ref(
            job.payload_ref,
            kind=f"runtime.control_job_payload.{job.kind}",
        )
    marker = payload["observational_method_execution"]
    assert ArtifactRef.model_validate(marker["observational_run_intent_ref"]) == intent_ref
    assert marker["observational_selection_digest"] == accepted["observational_selection_digest"]
    created_event = service._control_store.get_job_created_event_payload(accepted["job_id"])
    assert created_event["observational_method_execution"] == marker

    dispatched = dispatch_one_control_job(
        store=service._control_store,
        handler=service._process_control_job,
        expected_job_id=accepted["job_id"],
    )
    assert dispatched == accepted["job_id"]
    completed = service._control_store.get_job(accepted["job_id"])
    assert completed is not None and completed.state == "completed"
    with tenant_scope(
        None, tenant_id=runtime_api_env["tenant_a"], cell_id=runtime_api_env["cell_a"]
    ):
        selection = service.get_method_execution_selection(
            run_id=accepted["run_id"],
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
        )
    assert isinstance(selection, DirectMethodExecutionSelection)
    assert selection.method_version == "1.1.0"
    assert selection.owned_attempt_anchor_ref is None
    assert selection.hte is None
    assert selection.hte_outcome_ref is None
    assert selection.point_result_ref is None
    assert selection.hte_result_ref is None
    assert selection.inference_basis_ref is None
    assert selection.refusal_diagnostic_ref is None
    assert selection.selection_digest == accepted["observational_selection_digest"]
    assert selection.requested_source_ref == source_ref
    assert selection.submitted_input_ref == source_ref
    assert selection.normalization == normalization
    if protocol == "method_input_envelope_v1":
        assert selection.effective_input_ref == source_ref
    else:
        assert selection.effective_input_ref != source_ref
        assert "legacy_hte_json_v1_source_normalized" in selection.limitations
    assert selection.method_result_ref.kind == "scientist.method_result.causal.hte"
    assert selection.method_evidence_ref.kind == "scientist.method_evidence"
    assert selection.candidate_outcome is not None
    altered_candidate_outcome = selection.candidate_outcome.model_copy(
        update={"estimand": "unbound-candidate-summary"}
    )
    altered_selection = selection.model_copy(
        update={"candidate_outcome": altered_candidate_outcome}
    )
    with (
        tenant_scope(
            None,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
        ),
        pytest.raises(
            ValueError,
            match="direct_method_execution_candidate_outcome_mismatch",
        ),
    ):
        service._validate_direct_method_execution_selection_artifacts(altered_selection)
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        admitted_intent = ContentAdmittedObservationalRunIntent.model_validate(
            service._read_bounded_intent_artifact(selection.content_admitted_intent_ref)
        )
    assert admitted_intent.payload_integrity_verified is True
    assert admitted_intent.observed_manifest_bytes == (
        admitted_intent.observed_manifest_selection_bytes
    )
    assert admitted_intent.observed_source_bytes == (
        admitted_intent.observed_manifest_selection_bytes
        + admitted_intent.observed_manifest_verification_bytes
        + admitted_intent.observed_payload_bytes
    )
    assert admitted_intent.observed_source_bytes > 0
    expected_limitations = (
        "candidate_input_not_external_truth",
        "scientific_validity_not_established",
        "units_and_context_not_established",
        "source_access_revalidation_not_established",
        *(("legacy_hte_json_v1_source_normalized",) if protocol == "legacy_hte_json_v1" else ()),
    )
    assert selection.limitations == expected_limitations
    assert admitted_intent.source_protocol == protocol
    assert admitted_intent.normalization == normalization

    def reject_unbounded_job_payload_read(*args: Any, **kwargs: Any) -> Any:
        _ = (args, kwargs)
        raise AssertionError(
            "fresh Run Details must use the persisted event marker, not job payload"
        )

    monkeypatch.setattr(service, "_load_payload_ref", reject_unbounded_job_payload_read)

    fresh = runtime_api_env["client"].get(f"/api/v1/runs/{accepted['run_id']}")
    assert fresh.status_code == 200
    response_wire = fresh.json()
    projection = response_wire["run"]["method_execution_selection"]
    assert projection["status"] == "selected"
    request_summary = projection["request"]
    assert ArtifactRef.model_validate(request_summary["requested_source_ref"]) == source_ref
    assert ArtifactRef.model_validate(request_summary["requested_intent_ref"]) == intent_ref
    assert request_summary["resolved_params_sha256"]
    selected = projection["selection"]
    assert selected["job_id"] == accepted["job_id"]
    assert selected["attempt"] == completed.attempt
    assert (
        ArtifactRef.model_validate(selected["effective_input_ref"]) == selection.effective_input_ref
    )
    assert ArtifactRef.model_validate(selected["method_result_ref"]) == selection.method_result_ref
    assert selected["candidate_outcome"]["candidate_only"] is True
    assert selected["candidate_outcome"]["method"] == "forest_dr"
    assert selected["candidate_outcome"]["status"] in {
        "success",
        "input_invalid",
        "assumption_failed",
        "numerical_failure",
    }
    assert projection["time_roles"]["admitted_at"] is not None
    assert projection["time_roles"]["execution_started_at"] is not None
    assert projection["time_roles"]["execution_finished_at"] is not None
    assert projection["time_roles"]["owner_verified_at"] is not None
    assert projection["time_roles"]["reader_at"] is not None
    from _helpers.hte_privacy import hte_source_privacy_violations

    from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData

    assert selected["contract_target_id"] == HTEObservationalData.contract_id
    assert selected["contract_target"] == (
        f"{HTEObservationalData.__module__}.{HTEObservationalData.__qualname__}"
    )
    assert selected["hte"] is None
    assert selected["hte_outcome_ref"] is None
    assert selected["point_result_ref"] is None
    assert selected["hte_result_ref"] is None
    privacy_violations = hte_source_privacy_violations(
        response_wire,
        source_payload=source_payload,
        source_only_sample_id=source_only_sample_id,
    )
    assert privacy_violations == (), privacy_violations

    metric_projection = runtime_api_env["client"].get(
        f"/api/v1/runs/{accepted['run_id']}/method-metrics"
    )
    assert metric_projection.status_code == 200, metric_projection.text
    assert metric_projection.json()["status"] == "verification_missing"
    assert metric_projection.json()["vector_ref"] is None
    assert metric_projection.json()["observations"] == []
    assert (
        "direct_method_selection_has_no_graph_metric_projection"
        in (metric_projection.json()["limitations"])
    )
    metric_wire = metric_projection.json()
    metric_privacy_violations = hte_source_privacy_violations(
        metric_wire,
        source_payload=source_payload,
        source_only_sample_id=source_only_sample_id,
    )
    assert metric_privacy_violations == (), metric_privacy_violations


def test_method_metric_surface_checks_owner_scope_before_selection_lookup(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from _helpers.runtime_test_identity import fixture_identity_cell

    service = runtime_api_env["app"].state._control_service
    lookups: list[tuple[str, str, str]] = []

    def read_projection(*, run_id: str, tenant_id: str, cell_id: str) -> object:
        lookups.append((run_id, tenant_id, cell_id))
        raise AssertionError("unauthorized request reached the owner reader")

    monkeypatch.setattr(service, "read_current_admitted_method_metric_projection", read_projection)
    monkeypatch.setattr(service, "read_current_completed_ex_ante_candidate_score", read_projection)
    monkeypatch.setattr(service, "read_current_completed_ex_ante_comparison", read_projection)
    for suffix in ("method-metrics", "method-metric-comparison"):
        run_id = runtime_api_env["cross_tenant_run_id"]
        response = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}/{suffix}")
        assert response.status_code in {403, 404}
        assert lookups == []

        with fixture_identity_cell(monkeypatch, cell_id="cell-not-owned-by-run"):
            cell_mismatch = runtime_api_env["client"].get(
                f"/api/v1/runs/{runtime_api_env['core_run_id']}/{suffix}"
            )
        assert cell_mismatch.status_code == 403
        assert lookups == []


@pytest.mark.parametrize("final", ["unchanged", "replaced_profile", "revoked"])
def test_method_metric_score_follows_the_final_selected_projection(
    c48_isolated_runtime_api_env: dict[str, Any], monkeypatch: pytest.MonkeyPatch, final: str
) -> None:
    """A route seam can change while score replay is in flight; stale rows do not escape."""
    runtime_api_env = c48_isolated_runtime_api_env
    from polisyos.core.contracts.runtime import MethodMetricCandidateScore

    service = runtime_api_env["app"].state._control_service
    vector = _selected_ref("scientist.policy_evaluation_vector", "a", "b")
    replacement = _selected_ref("scientist.policy_evaluation_vector", "a", "c")
    candidate = _selected_ref("scientist.policy_design.candidate", "d", "e")
    assert vector.artifact_id == replacement.artifact_id and vector != replacement
    calls = []

    def read_projection(**kwargs: Any) -> object:
        calls.append(kwargs)
        if len(calls) == 1 or final == "unchanged":
            return SimpleNamespace(
                status="selected", vector_ref=vector, observations=({"value": 1},), limitations=()
            )
        if final == "replaced_profile":
            return SimpleNamespace(
                status="selected",
                vector_ref=replacement,
                observations=({"value": 2},),
                limitations=(),
            )
        return SimpleNamespace(
            status="verification_missing",
            vector_ref=None,
            observations=(),
            limitations=("revoked",),
        )

    def read_score(**kwargs: Any) -> MethodMetricCandidateScore:
        return MethodMetricCandidateScore(
            status="selected",
            candidate_ref=candidate,
            source_vector_ref=vector,
            minimized_score=-1.0,
            maximizing_coordinate=1.0,
            comparison_contract_sha256="f" * 64,
        )

    def no_comparison(**kwargs: Any) -> object:
        raise AssertionError("single-source GET must not execute the separate comparison")

    monkeypatch.setattr(service, "read_current_admitted_method_metric_projection", read_projection)
    monkeypatch.setattr(service, "read_current_completed_ex_ante_candidate_score", read_score)
    monkeypatch.setattr(service, "read_current_completed_ex_ante_comparison", no_comparison)
    response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/method-metrics"
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    if final == "unchanged":
        assert payload["status"] == "selected"
        assert payload["candidate_score"]["status"] == "selected"
    elif final == "replaced_profile":
        assert payload["status"] == "selected"
        assert payload["vector_ref"] == replacement.model_dump(mode="json")
        assert payload["observations"] == [{"value": 2}]
        assert payload["candidate_score"]["status"] == "verification_missing"
    else:
        assert payload["status"] == "verification_missing"
        assert payload["vector_ref"] is None and payload["observations"] == []
        assert payload["candidate_score"]["status"] == "verification_missing"
    assert len(calls) == 2


def test_run_details_withholds_method_projection_for_wrong_cell_scope(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from _helpers.runtime_test_identity import fixture_identity_cell

    service = runtime_api_env["app"].state._control_service
    lookups: list[str] = []

    def read_projection(**kwargs: Any) -> object:
        lookups.append(str(kwargs.get("run_id")))
        raise AssertionError("wrong-cell review reached the method execution owner")

    monkeypatch.setattr(service, "get_observational_method_run_projection", read_projection)
    with fixture_identity_cell(monkeypatch, cell_id="cell-not-owned-by-run"):
        response = runtime_api_env["client"].get(f"/api/v1/runs/{runtime_api_env['core_run_id']}")
    assert response.status_code == 200
    projection = response.json()["run"]["method_execution_selection"]
    assert projection["status"] == "withheld"
    assert projection["limitations"] == ["owned_run_cell_scope_required"]
    assert lookups == []


def test_running_method_timeout_cannot_late_publish_after_fenced_failure(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker

    from polisyos.common.async_tools import SharedExecutorWaitTimeoutError
    from polisyos.runtime.http.services.control_plane_store import ControlJobLeaseLostError

    service = runtime_api_env["app"].state._control_service
    stop_embedded_control_worker(service)
    source_ref = _put_runtime_observational_source(
        service,
        owner_scope=(runtime_api_env["tenant_a"], runtime_api_env["cell_a"]),
    )
    response = _post_runtime_api_as_fixture_owner(
        runtime_api_env,
        "/api/v1/control/runs",
        json={
            "observational_input": {
                "protocol": "method_input_envelope_v1",
                "source_ref": source_ref.model_dump(mode="json"),
                "method": {"fqn": "causal.hte.forest_dr@1.1.0"},
            }
        },
    )
    assert response.status_code == 200
    accepted = response.json()
    running_identity: dict[str, object] = {}

    class RunningTimeoutHandle:
        def result(self, timeout: float | None = None) -> object:
            assert timeout is not None and timeout > 0
            current = service._control_store.get_job(accepted["job_id"])
            assert current is not None and current.state == "running"
            running_identity["lease_owner"] = current.lease_owner
            running_identity["attempt"] = current.attempt
            raise SharedExecutorWaitTimeoutError(cancelled_before_start=False)

    monkeypatch.setattr(
        service._method_backend,
        "submit_method_execution_work",
        lambda work: RunningTimeoutHandle(),
    )
    dispatched = dispatch_one_control_job(
        store=service._control_store,
        handler=service._process_control_job,
        expected_job_id=accepted["job_id"],
    )
    assert dispatched == accepted["job_id"]
    failed = service._control_store.get_job(accepted["job_id"])
    assert failed is not None
    assert failed.state == "failed"
    assert failed.method_execution_selection is None
    assert failed.progress["method_execution_wait"]["wait_disposition"] == ("running_slot_retained")

    _, late_selection, _ = _direct_method_cas_case(tmp_path)
    late_selection = late_selection.model_copy(
        update={
            "job_id": accepted["job_id"],
            "run_id": accepted["run_id"],
            "attempt": running_identity["attempt"],
        }
    )
    with pytest.raises(ControlJobLeaseLostError):
        service._control_store.complete_job(
            job_id=accepted["job_id"],
            run_id=accepted["run_id"],
            capability_manifest_ref=None,
            progress={"state": "completed"},
            method_execution_selection=late_selection,
            expected_lease_owner=str(running_identity["lease_owner"]),
            expected_attempt=int(running_identity["attempt"]),
        )
    current = service._control_store.get_job(accepted["job_id"])
    assert current is not None and current.state == "failed"
    assert current.method_execution_selection is None


def test_http_worker_refuses_same_fqn_wrong_target_id_before_dispatch(
    runtime_api_env: dict[str, Any],
) -> None:
    from polisyos.core.security.tenant_context import tenant_scope

    pytest.importorskip("econml")
    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker

    service = runtime_api_env["app"].state._control_service
    stop_embedded_control_worker(service)
    source_only_sample_id = "hte-source-only::wrong-target-refusal::row-0"
    source_payload = _runtime_hte_source_payload(
        source_only_sample_id=source_only_sample_id,
    )
    source_ref = _put_runtime_observational_source(
        service,
        owner_scope=(runtime_api_env["tenant_a"], runtime_api_env["cell_a"]),
        source_only_sample_id=source_only_sample_id,
        contract_target_id="foundry.causal.hte_observational_data.v0",
        contract_target_fqn=(
            "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
        ),
    )
    response = _post_runtime_api_as_fixture_owner(
        runtime_api_env,
        "/api/v1/control/runs",
        json={
            "observational_input": {
                "protocol": "method_input_envelope_v1",
                "source_ref": source_ref.model_dump(mode="json"),
                "method": {"fqn": "causal.hte.forest_dr@1.1.0"},
            }
        },
    )
    assert response.status_code == 200
    accepted = response.json()

    dispatched = dispatch_one_control_job(
        store=service._control_store,
        handler=service._process_control_job,
        expected_job_id=accepted["job_id"],
    )
    assert dispatched == accepted["job_id"]
    record = service._control_store.get_job(accepted["job_id"])
    assert record is not None and record.state == "failed"
    assert record.method_execution_selection is None
    assert record.progress["failure"]["exception_type"] == (
        "polisyos.foundry.data_plane.bindings.HTEInputPreparationRefusal"
    )
    assert record.progress["failure"]["code"] == "observational_input_refused"
    assert record.progress["failure"]["attempt"] == record.attempt
    with tenant_scope(
        None, tenant_id=runtime_api_env["tenant_a"], cell_id=runtime_api_env["cell_a"]
    ):
        assert (
            service.get_method_execution_selection(
                run_id=accepted["run_id"],
                tenant_id=runtime_api_env["tenant_a"],
                cell_id=runtime_api_env["cell_a"],
            )
            is None
        )
    from _helpers.hte_privacy import hte_source_privacy_violations

    progress_privacy_violations = hte_source_privacy_violations(
        record.progress,
        source_payload=source_payload,
        source_only_sample_id=source_only_sample_id,
    )
    assert progress_privacy_violations == (), progress_privacy_violations
    fresh = runtime_api_env["client"].get(f"/api/v1/runs/{accepted['run_id']}")
    assert fresh.status_code == 200, fresh.text
    response_wire = fresh.json()
    projection = response_wire["run"]["method_execution_selection"]
    assert projection["status"] == "input_refused"
    assert projection["refusal_code"] == "observational_input_refused"
    assert projection["request"]["requested_source_ref"] == source_ref.model_dump(mode="json")
    assert projection["selection"] is None
    refusal_privacy_violations = hte_source_privacy_violations(
        response_wire,
        source_payload=source_payload,
        source_only_sample_id=source_only_sample_id,
    )
    assert refusal_privacy_violations == (), refusal_privacy_violations


def test_failed_shared_method_completion_persists_bounded_failure_identity(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker

    service = runtime_api_env["app"].state._control_service
    stop_embedded_control_worker(service)
    source_only_sample_id = "hte-source-only::failed-execution-redaction::row-0"
    source_payload = _runtime_hte_source_payload(
        source_only_sample_id=source_only_sample_id,
    )
    source_ref = _put_runtime_observational_source(
        service,
        owner_scope=(runtime_api_env["tenant_a"], runtime_api_env["cell_a"]),
        source_only_sample_id=source_only_sample_id,
    )
    response = _post_runtime_api_as_fixture_owner(
        runtime_api_env,
        "/api/v1/control/runs",
        json={
            "observational_input": {
                "protocol": "method_input_envelope_v1",
                "source_ref": source_ref.model_dump(mode="json"),
                "method": {"fqn": "causal.hte.forest_dr@1.1.0"},
            }
        },
    )
    assert response.status_code == 200
    accepted = response.json()

    class FailedHandle:
        def result(self, timeout: float | None = None) -> object:
            assert timeout is not None and timeout > 0
            return SimpleNamespace(
                status="failed",
                value=None,
                failure=SimpleNamespace(
                    exception_type="ValueError",
                    code="bounded_method_input_invalid",
                    message_excerpt="candidate payload must not enter public progress",
                    retryable=False,
                ),
            )

    monkeypatch.setattr(
        service._method_backend,
        "submit_method_execution_work",
        lambda work: FailedHandle(),
    )
    dispatched = dispatch_one_control_job(
        store=service._control_store,
        handler=service._process_control_job,
        expected_job_id=accepted["job_id"],
    )
    assert dispatched == accepted["job_id"]
    record = service._control_store.get_job(accepted["job_id"])
    assert record is not None and record.state == "failed"
    assert record.progress["method_execution_failure"]["exception_type"] == "ValueError"
    assert record.progress["method_execution_failure"]["code"] == ("bounded_method_input_invalid")
    assert record.progress["failure"]["code"] == "bounded_method_input_invalid"
    assert record.progress["failure"]["retryable"] is False
    assert "candidate payload" not in str(record.progress)
    from _helpers.hte_privacy import hte_source_privacy_violations

    progress_privacy_violations = hte_source_privacy_violations(
        record.progress,
        source_payload=source_payload,
        source_only_sample_id=source_only_sample_id,
    )
    assert progress_privacy_violations == (), progress_privacy_violations
    fresh = runtime_api_env["client"].get(f"/api/v1/runs/{accepted['run_id']}")
    assert fresh.status_code == 200, fresh.text
    response_wire = fresh.json()
    projection = response_wire["run"]["method_execution_selection"]
    assert projection["status"] == "execution_failed"
    assert projection["refusal_code"] is None
    assert projection["request"]["requested_source_ref"] == source_ref.model_dump(mode="json")
    failure_privacy_violations = hte_source_privacy_violations(
        response_wire,
        source_payload=source_payload,
        source_only_sample_id=source_only_sample_id,
    )
    assert failure_privacy_violations == (), failure_privacy_violations
    assert "candidate payload" not in fresh.text


@pytest.mark.parametrize(
    "drift_kind", ["source_ref", "source_profile", "intent_params", "marker_removed"]
)
def test_worker_refuses_post_to_intent_mapping_drift_before_method_dispatch(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    drift_kind: str,
) -> None:
    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker

    service = runtime_api_env["app"].state._control_service
    stop_embedded_control_worker(service)
    owner_scope = (runtime_api_env["tenant_a"], runtime_api_env["cell_a"])
    source_ref = _put_runtime_observational_source(service, owner_scope=owner_scope)
    response = _post_runtime_api_as_fixture_owner(
        runtime_api_env,
        "/api/v1/control/runs",
        json={
            "observational_input": {
                "protocol": "method_input_envelope_v1",
                "source_ref": source_ref.model_dump(mode="json"),
                "method": {
                    "fqn": "causal.hte.forest_dr@1.1.0",
                    "params": {"n_estimators": 12, "cv_folds": 2, "subforest_size": 2},
                },
            }
        },
    )
    assert response.status_code == 200, response.text
    accepted = response.json()
    job = service._control_store.get_job(accepted["job_id"])
    assert job is not None and job.payload_ref is not None
    original_loader = service._load_payload_ref
    from polisyos.core.security.tenant_context import tenant_scope

    with tenant_scope(
        None,
        tenant_id=owner_scope[0],
        cell_id=owner_scope[1],
    ):
        original_payload = original_loader(
            job.payload_ref,
            kind="runtime.control_job_payload.workflow_run",
        )
    original_marker = original_payload["observational_method_execution"]
    created_event = service._control_store.get_job_created_event_payload(accepted["job_id"])
    assert created_event["observational_method_execution"] == original_marker
    intent_ref = ArtifactRef.model_validate(original_marker["observational_run_intent_ref"])
    with tenant_scope(
        None,
        tenant_id=owner_scope[0],
        cell_id=owner_scope[1],
    ):
        intent = ObservationalRunIntent.model_validate(
            service._read_bounded_intent_artifact(intent_ref)
        )
        selected_source, selected_intent_ref, selected_digest, selected_intent = (
            service._read_validated_observational_method_job_intent(
                job=job,
                payload=original_payload,
            )
        )
    assert artifact_ref_identity_key(selected_source) == artifact_ref_identity_key(source_ref)
    assert artifact_ref_identity_key(selected_intent_ref) == artifact_ref_identity_key(intent_ref)
    assert selected_digest == intent.selection_digest()
    assert selected_intent.resolved_params == intent.resolved_params

    altered_marker = dict(original_marker)
    if drift_kind == "source_ref":
        altered_source_ref = _put_runtime_observational_source(
            service,
            owner_scope=owner_scope,
            source_label="different_candidate_source",
        )
        altered_marker["requested_source_ref"] = altered_source_ref.model_dump(mode="json")
    elif drift_kind == "source_profile":
        from polisyos.core.security.tenant_context import tenant_scope

        with tenant_scope(
            None,
            tenant_id=owner_scope[0],
            cell_id=owner_scope[1],
        ):
            profile_parent = _put_selected_json(
                service._artifact_store,
                {"profile_context": "synthetic test control"},
                kind="runtime.test.profile_context",
                schema=None,
                governance=ArtifactGovernanceInfo(classification="public"),
            )
        altered_source_ref = _put_runtime_observational_source(
            service,
            owner_scope=owner_scope,
            inputs=(_input_edge(profile_parent, "profile_context"),),
        )
        assert altered_source_ref.artifact_id == source_ref.artifact_id
        assert altered_source_ref.manifest_profile_sha256 != source_ref.manifest_profile_sha256
        altered_marker["requested_source_ref"] = altered_source_ref.model_dump(mode="json")
    elif drift_kind == "intent_params":
        original_n_estimators = intent.resolved_params["n_estimators"]
        assert type(original_n_estimators) is int
        altered_params = dict(intent.submitted_params)
        altered_params["n_estimators"] = original_n_estimators + 1
        altered_resolved_params = dict(intent.resolved_params)
        altered_resolved_params["n_estimators"] = original_n_estimators + 1
        altered_intent = intent.model_copy(
            update={
                "submitted_params": altered_params,
                "resolved_params": altered_resolved_params,
            }
        )
        altered_intent = ObservationalRunIntent.model_validate(altered_intent.artifact_payload())
        assert altered_intent.job_id == intent.job_id
        assert altered_intent.run_id == intent.run_id
        assert artifact_ref_identity_key(altered_intent.requested_source_ref) == (
            artifact_ref_identity_key(intent.requested_source_ref)
        )
        assert altered_intent.resolved_params["n_estimators"] == original_n_estimators + 1
        assert altered_intent.selection_digest() != intent.selection_digest()
        assert intent.resource_policy_ref is not None
        with tenant_scope(
            None,
            tenant_id=owner_scope[0],
            cell_id=owner_scope[1],
        ):
            altered_intent_ref = service._put_json_artifact_ref(
                altered_intent.artifact_payload(),
                kind="runtime.observational_run_intent",
                schema_name="polisyos.runtime.ObservationalRunIntent",
                schema_version="1.0",
                tenant_context=intent.source_tenant_context,
                governance=intent.source_governance,
                inputs=[intent.requested_source_ref, intent.resource_policy_ref],
                input_roles=("requested_source", "resource_policy"),
            )
            readback_intent = ObservationalRunIntent.model_validate(
                service._read_bounded_intent_artifact(altered_intent_ref)
            )
        assert readback_intent.selection_digest() == altered_intent.selection_digest()
        altered_marker["observational_run_intent_ref"] = altered_intent_ref.model_dump(mode="json")
        altered_marker["observational_selection_digest"] = altered_intent.selection_digest()

    def tamper_accepted_payload(payload_ref: str, *, kind: str) -> dict[str, Any]:
        loaded = original_loader(payload_ref, kind=kind)
        if payload_ref != job.payload_ref:
            return loaded
        updated = dict(loaded)
        if drift_kind == "marker_removed":
            updated.pop("observational_method_execution", None)
        else:
            updated["observational_method_execution"] = altered_marker
        return updated

    core_attempt_calls: list[object] = []
    submit_calls: list[object] = []

    def reject_core_attempt(**kwargs: object) -> tuple[str, object]:
        core_attempt_calls.append(kwargs)
        raise AssertionError("Core run attempt started before frozen request check")

    def reject_submit(work: object) -> object:
        submit_calls.append(work)
        raise AssertionError("method work submitted before frozen request check")

    monkeypatch.setattr(service, "_load_payload_ref", tamper_accepted_payload)
    monkeypatch.setattr(service, "_start_generation_run_context", reject_core_attempt)
    monkeypatch.setattr(service._method_backend, "submit_method_execution_work", reject_submit)
    dispatched = dispatch_one_control_job(
        store=service._control_store,
        handler=service._process_control_job,
        expected_job_id=accepted["job_id"],
    )

    assert dispatched == accepted["job_id"]
    failed = service._control_store.get_job(accepted["job_id"])
    assert failed is not None and failed.state == "failed"
    expected_error = (
        "observational_method_job_marker_invalid"
        if drift_kind == "marker_removed"
        else "observational_method_job_payload_selection_not_creation_bound"
    )
    assert failed.error_message == expected_error
    assert failed.method_execution_selection is None
    assert core_attempt_calls == []
    assert submit_calls == []


def _post_observational_selection(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    method: dict[str, object],
    *,
    hte_request: dict[str, object] | None = None,
) -> tuple[Any, list[dict[str, Any]]]:
    service = runtime_api_env["app"].state._control_service
    queued: list[dict[str, Any]] = []

    def capture_enqueue(**kwargs: Any) -> None:
        queued.append(kwargs)

    monkeypatch.setattr(service, "_enqueue_job", capture_enqueue)
    observational_input: dict[str, object] = {
        "protocol": "method_input_envelope_v1",
        "source_ref": _put_runtime_observational_source(
            service,
            owner_scope=(runtime_api_env["tenant_a"], runtime_api_env["cell_a"]),
        ).model_dump(mode="json"),
        "method": method,
    }
    if hte_request is not None:
        observational_input["hte_request"] = hte_request
    response = _post_runtime_api_as_fixture_owner(
        runtime_api_env,
        "/api/v1/control/runs",
        json={"observational_input": observational_input},
    )
    return response, queued


@pytest.mark.parametrize(
    ("method", "expected_fqn", "hte_request"),
    [
        (
            {"fqn": "causal.hte.forest_dr@2.0.0"},
            "causal.hte.forest_dr@2.0.0",
            {
                "schema_version": "polisyos.runtime.observational_hte_request.v2",
                "estimand": "conditional_average_treatment_effect",
                "target_scope": "synthetic_test_population",
                "outcome_variable_id": "outcome",
                "treatment_variable_id": "treatment",
                "control_value": 0,
                "treated_value": 1,
                "alpha": 0.05,
            },
        ),
        (
            {"fqn": "causal.hte.forest_dr", "version": "1.1.0"},
            "causal.hte.forest_dr@1.1.0",
            None,
        ),
        ({"fqn": "causal.hte.forest_dr@1.1.0"}, "causal.hte.forest_dr@1.1.0", None),
    ],
)
def test_http_post_resolves_and_persists_exact_bounded_method_version_once(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    method: dict[str, object],
    expected_fqn: str,
    hte_request: dict[str, object] | None,
) -> None:
    response, queued = _post_observational_selection(
        runtime_api_env,
        monkeypatch,
        method,
        hte_request=hte_request,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "accepted"
    assert len(queued) == 1
    marker = queued[0]["payload"]["observational_method_execution"]
    intent_ref = ArtifactRef.model_validate(marker["observational_run_intent_ref"])
    from polisyos.core.security.tenant_context import tenant_scope

    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        intent = ObservationalRunIntent.model_validate(
            runtime_api_env["app"].state._control_service._read_bounded_intent_artifact(intent_ref)
        )
    assert intent.method_fqn == expected_fqn
    expected_version = expected_fqn.rpartition("@")[2]
    assert intent.method_version == expected_version
    assert ArtifactRef.model_validate(response.json()["observational_run_intent_ref"]) == intent_ref
    assert response.json()["observational_selection_digest"] == intent.selection_digest()
    assert marker["observational_selection_digest"] == intent.selection_digest()
    registration = runtime_api_env[
        "app"
    ].state._control_service._observational_method_registrations[expected_fqn]
    assert intent.method_abi_digest == registration.signature.abi_digest()
    expected_abi_digest = (
        "6545daabc7f5354e020bf7a90cc64c858ade7397d249437990be0c19df98c43b"
        if expected_version == "2.0.0"
        else "c47789927627661e4eedd78368cc710181060dc1e705b8484cbf089fe50234e4"
    )
    assert intent.method_abi_digest == expected_abi_digest
    assert intent.method_build_digest == registration.build_digest
    assert intent.method_build_digest_scope == "class_source_only"
    assert intent.resource_policy.revision == ("r5" if expected_version == "2.0.0" else "r3")
    assert intent.resource_policy.method_contract_target == (
        "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
    )
    assert intent.resource_policy.required_estimator_n_jobs == 1
    assert type(intent.resolved_params["n_jobs"]) is int
    assert intent.resolved_params["n_jobs"] == 1


def test_http_post_omitted_version_persists_latest_available_v1_registration(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = runtime_api_env["app"].state._control_service
    monkeypatch.setattr(
        service._method_registry,
        "list_versions",
        lambda base_name: ["1.0.0", "1.1.0"],
    )

    response, queued = _post_observational_selection(
        runtime_api_env,
        monkeypatch,
        {"fqn": "causal.hte.forest_dr"},
    )

    assert response.status_code == 200, response.text
    assert len(queued) == 1
    marker = queued[0]["payload"]["observational_method_execution"]
    intent_ref = ArtifactRef.model_validate(marker["observational_run_intent_ref"])
    from polisyos.core.security.tenant_context import tenant_scope

    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        intent = ObservationalRunIntent.model_validate(
            service._read_bounded_intent_artifact(intent_ref)
        )
    assert intent.method_fqn == "causal.hte.forest_dr@1.1.0"
    assert intent.method_version == "1.1.0"
    assert marker["observational_selection_digest"] == intent.selection_digest()


def test_http_post_refuses_unbounded_legacy_method_before_durable_enqueue(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, queued = _post_observational_selection(
        runtime_api_env,
        monkeypatch,
        {"fqn": "causal.hte.forest_dr@1.0.0"},
    )

    assert response.status_code == 422
    assert "observational_method_resource_profile_not_supported" in response.text
    assert queued == []


@pytest.mark.parametrize("n_jobs", [2, True])
def test_http_post_refuses_invalid_estimator_parallelism_before_enqueue(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    n_jobs: int | bool,
) -> None:
    response, queued = _post_observational_selection(
        runtime_api_env,
        monkeypatch,
        {"fqn": "causal.hte.forest_dr@1.1.0", "params": {"n_jobs": n_jobs}},
    )

    assert response.status_code == 422
    assert queued == []


def test_latest_v1_0_refuses_bounded_profile_instead_of_upgrading(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = runtime_api_env["app"].state._control_service
    monkeypatch.setattr(service._method_registry, "list_versions", lambda base_name: ["1.0.0"])

    registration = service._resolve_observational_method_registration(
        fqn="causal.hte.forest_dr",
        version=None,
    )
    assert registration.signature.fqn == "causal.hte.forest_dr@1.0.0"
    with pytest.raises(ValueError, match="observational_method_resource_profile_not_supported"):
        service._require_observational_method_resource_profile(registration, {})


def test_dml_v2_profile_uses_fixed_producer_config_not_an_unexposed_parameter(
    runtime_api_env: dict[str, Any],
) -> None:
    """The DML producer fixes use_ray=False internally; it is not a runtime input."""
    service = runtime_api_env["app"].state._control_service
    registration = service._resolve_observational_method_registration(
        fqn="causal.hte.double_ml@2.0.0",
        version=None,
    )
    parameter_names = {item.name for item in registration.signature.parameters}
    assert "use_ray" not in parameter_names
    assert registration.method_profile_id == "econml.dml.point_only@2.0"
    assert registration.execution_scope == "producer_scoped_joblib_parallelism_one"
    service._require_observational_method_resource_profile(registration, {})


def test_latest_method_resolution_fails_closed_when_newer_registry_entry_is_unsupported(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = runtime_api_env["app"].state._control_service
    monkeypatch.setattr(
        service._method_registry,
        "list_versions",
        lambda base_name: ["1.0.0", "1.1.0", "2.0.0"],
    )

    with pytest.raises(ValueError, match="observational_method_registration_not_supported"):
        service._resolve_observational_method_registration(
            fqn="causal.hte.forest_dr",
            version=None,
        )


@pytest.mark.parametrize("vector", _shared_guard_vectors(), ids=lambda row: row["case_id"])
def test_shared_raw_governance_guard_rejects_typed_default_for_each_protocol(
    vector: dict[str, Any],
) -> None:
    selected_fields = vector["selected_raw_manifest_fields"]
    raw_manifest_bytes = json.dumps(selected_fields, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    typed_governance = ArtifactGovernanceInfo.model_validate(
        vector["parsed_typed_manifest_governance"]
    )

    assert vector["expected"] == "refuse_before_enqueue_and_http_post"
    with pytest.raises(ValueError, match="observational_source_governance_not_explicit"):
        _explicit_source_manifest_metadata(
            raw_manifest_bytes=raw_manifest_bytes,
            typed_governance=typed_governance,
            tenant_context=None,
        )


def test_explicit_governance_guard_pins_exact_selected_raw_manifest_bytes() -> None:
    initial_bytes = json.dumps(
        {"governance": {"classification": "public"}, "byte_size": 17},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    governance, tenant_context, selected_sha256 = _explicit_source_manifest_metadata(
        raw_manifest_bytes=initial_bytes,
        typed_governance=ArtifactGovernanceInfo(classification="public"),
        tenant_context=None,
    )

    assert governance.classification == "public"
    assert tenant_context is None
    assert len(selected_sha256) == 64

    changed_same_typed_metadata = json.dumps(
        {"governance": {"classification": "public"}, "byte_size": 18},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    with pytest.raises(ValueError, match="observational_source_manifest_pin_drift"):
        _explicit_source_manifest_metadata(
            raw_manifest_bytes=changed_same_typed_metadata,
            typed_governance=governance,
            tenant_context=None,
            expected_sha256=selected_sha256,
        )

    typed_default_after_raw_governance_removal = json.dumps(
        {"governance": {}, "byte_size": 17}, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    with pytest.raises(ValueError, match="observational_source_governance_not_explicit"):
        _explicit_source_manifest_metadata(
            raw_manifest_bytes=typed_default_after_raw_governance_removal,
            typed_governance=governance,
            tenant_context=None,
            expected_sha256=selected_sha256,
        )


class _FoundryDelegate:
    def __init__(self, result: Any) -> None:
        self._result = result

    def compile(self, store: Any, request: Any) -> Any:
        return None

    def execute(self, store: Any, request: Any) -> Any:
        return self._result


def test_runtime_graph_origin_receipt_rejects_cas_valid_state_ref_swap() -> None:
    selected_refs = (
        SimulationResultRef.model_validate(
            _selected_ref("foundry.simulation_result", "a", "1").model_dump(mode="python")
        ),
        MethodExecutionBundleRef.model_validate(
            _selected_ref("foundry.method_execution_bundle", "b", "2").model_dump(mode="python")
        ),
        MethodMetricBindingSetRef.model_validate(
            _selected_ref("foundry.method_metric_binding_set", "c", "3").model_dump(mode="python")
        ),
    )
    base_refs = tuple(
        ArtifactRef.model_validate(ref.model_dump(mode="python")) for ref in selected_refs
    )
    result = SimpleNamespace(
        ok=True,
        simulation_result_ref=selected_refs[0],
        method_execution_bundle_ref=selected_refs[1],
        derived_refs=[
            SimpleNamespace(role="method_execution_bundle", ref=base_refs[1]),
            SimpleNamespace(role="method_metric_binding_set", ref=base_refs[2]),
        ],
    )
    capture = _RuntimeOriginCapturingFoundryPort(
        delegate=_FoundryDelegate(result),
        job_id="job-current",
        run_id="run-current",
        attempt=4,
        lease_owner="lease-current",
    )
    assert capture.execute(store=object(), request=object()) is result
    receipt = capture.producer_receipt()
    assert receipt is not None
    assert receipt.diagnostics[0].output_ref_status == "complete"
    assert len(receipt.emissions) == 1

    state: dict[str, Any] = {
        "params": {"candidate_only_state_payload": ["retained only until refs are extracted"]},
        "artifacts_index": {
            "simulation_result_ref": selected_refs[0].model_dump(mode="json"),
            "method_execution_bundle_ref": selected_refs[1].model_dump(mode="json"),
            "method_metric_binding_set_ref": selected_refs[2].model_dump(mode="json"),
        },
    }
    graph_output_refs = _scientist_graph_output_refs(state)
    reparsed_refs = (
        graph_output_refs.simulation_result_ref,
        graph_output_refs.method_execution_bundle_ref,
        graph_output_refs.method_metric_binding_set_ref,
    )
    assert tuple(artifact_ref_identity_key(ref) for ref in reparsed_refs) == tuple(
        artifact_ref_identity_key(ref) for ref in selected_refs
    )
    assert not hasattr(graph_output_refs, "params")
    source = _selected_graph_source_refs_from_receipt(
        graph_output_refs=graph_output_refs,
        receipt=receipt,
        job_id="job-current",
        run_id="run-current",
        attempt=4,
        lease_owner="lease-current",
    )
    assert source is not None
    assert tuple(artifact_ref_identity_key(ref) for ref in source) == tuple(
        artifact_ref_identity_key(ref) for ref in selected_refs
    )

    profile_changed_state = {"artifacts_index": dict(state["artifacts_index"])}
    profile_changed_state["artifacts_index"]["simulation_result_ref"] = (
        graph_output_refs.simulation_result_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "f" * 64}
        ).model_dump(mode="json")
    )
    assert (
        _selected_graph_source_refs_from_receipt(
            graph_output_refs=_scientist_graph_output_refs(profile_changed_state),
            receipt=receipt,
            job_id="job-current",
            run_id="run-current",
            attempt=4,
            lease_owner="lease-current",
        )
        is None
    )

    typed_duplicate = SimpleNamespace(
        ok=True,
        simulation_result_ref=selected_refs[0],
        method_execution_bundle_ref=selected_refs[1],
        derived_refs=[
            SimpleNamespace(role="method_execution_bundle", ref=selected_refs[1]),
            SimpleNamespace(role="method_metric_binding_set", ref=selected_refs[2]),
        ],
    )
    duplicate_capture = _RuntimeOriginCapturingFoundryPort(
        delegate=_FoundryDelegate(typed_duplicate),
        job_id="job-current",
        run_id="run-current",
        attempt=4,
        lease_owner="lease-current",
    )
    duplicate_capture.execute(store=object(), request=object())
    duplicate_capture._capture_execute_result(
        SimpleNamespace(
            ok=True,
            simulation_result_ref=base_refs[0],
            method_execution_bundle_ref=base_refs[1],
            derived_refs=[
                SimpleNamespace(role="method_execution_bundle", ref=base_refs[1]),
                SimpleNamespace(role="method_metric_binding_set", ref=base_refs[2]),
            ],
        )
    )
    assert len(duplicate_capture.producer_receipt().emissions) == 1

    swapped_state = {"artifacts_index": dict(state["artifacts_index"])}
    swapped_state["artifacts_index"]["simulation_result_ref"] = _selected_ref(
        "foundry.simulation_result", "d", "4"
    ).model_dump(mode="json")
    swapped_output_refs = _scientist_graph_output_refs(swapped_state)
    assert (
        _selected_graph_source_refs_from_receipt(
            graph_output_refs=swapped_output_refs,
            receipt=receipt,
            job_id="job-current",
            run_id="run-current",
            attempt=4,
            lease_owner="lease-current",
        )
        is None
    )

    assert (
        _selected_graph_source_refs_from_receipt(
            graph_output_refs=graph_output_refs,
            receipt=receipt,
            job_id="job-current",
            run_id="run-current",
            attempt=4,
            lease_owner="lease-replaced",
        )
        is None
    )


def test_actual_execute_result_survives_later_scientist_node_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.scientist import api as scientist_api
    from polisyos.scientist.adapters import foundry_bridge

    simulation_ref = _selected_ref("foundry.simulation_result", "a", "1")
    bundle_ref = _selected_ref("foundry.method_execution_bundle", "b", "2")
    binding_ref = _selected_ref("foundry.method_metric_binding_set", "c", "3")
    execute_result = ExecuteResult(
        ok=True,
        simulation_result_ref=simulation_ref,
        derived_refs=[
            DerivedArtifact(role="method_execution_bundle", ref=bundle_ref),
            DerivedArtifact(role="method_metric_binding_set", ref=binding_ref),
        ],
    )

    class _ExecuteResultPort:
        def compile(self, store: object, request: object) -> None:
            _ = (store, request)
            return None

        def execute(self, store: object, request: object) -> ExecuteResult:
            return execute_result

    monkeypatch.setattr(
        foundry_bridge,
        "DefaultFoundryPort",
        lambda: _ExecuteResultPort(),
    )

    supplied_owners: list[object] = []

    def _fail_after_simulation(
        _state_payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        supplied_owners.append(kwargs["method_metric_selection_owner"])
        foundry = kwargs["foundry"]
        foundry.execute(store=kwargs["store"], request=object())
        raise RuntimeError("later_scientist_node_failed")

    monkeypatch.setattr(scientist_api, "run_experiment", _fail_after_simulation)
    job = SimpleNamespace(
        job_id="job-later-node-failure",
        run_id="run-later-node-failure",
        attempt=3,
        lease_owner="lease-later-node-failure",
        kind="workflow_run",
    )

    class _TransitionFixture(ControlPlaneWorkspaceLoopTransitionMixin):
        _artifact_store = object()
        _epoch_certificate_issuance_owner = None
        _evaluation_safety_admission_verifier = None

        def resolve_completed_method_metric_selection(
            self,
            *,
            source_run_id: str,
            candidate_ref: ArtifactRef,
            tenant_id: str,
            cell_id: str | None,
        ) -> None:
            _ = (source_run_id, candidate_ref, tenant_id, cell_id)
            return None

        def _run_legacy_scientist_workflow(
            self,
            state_payload: dict[str, Any],
            *,
            job: object,
        ) -> object:
            return ControlPlaneService._run_legacy_scientist_workflow(
                self,
                state_payload,
                job=job,
            )

        @staticmethod
        def _workflow_failure_progress(
            *,
            job: object,
            phase: str,
            reason: str,
            failure_code: str,
            failure_message: str,
        ) -> dict[str, Any]:
            _ = job
            return {
                "state": "failed",
                "phase": phase,
                "authority_result": "repair_required",
                "failure": {"code": failure_code, "message": failure_message},
            }

    transition = _TransitionFixture()
    with pytest.raises(_WorkflowExecutionNonAuthorityError) as caught:
        transition._execute_legacy_shadow_workflow(
            {},
            "strict",
            job=job,
        )

    from polisyos.scientist.orchestration.engine.context import (
        CompletedMethodMetricSelectionOwner,
    )

    assert supplied_owners == [transition]
    assert isinstance(supplied_owners[0], CompletedMethodMetricSelectionOwner)
    cause = caught.value.__cause__
    assert type(cause) is _LegacyScientistWorkflowError
    diagnostic = caught.value.progress["method_execution_producer_diagnostic"]
    assert diagnostic["authority_status"] == "candidate_only"
    assert diagnostic["emissions"][0]["execute_result_status"] == "ok"
    assert diagnostic["emissions"][0]["simulation_result_ref"] == simulation_ref.model_dump(
        mode="json"
    )
    assert diagnostic["emissions"][0]["method_execution_bundle_refs"] == [
        bundle_ref.model_dump(mode="json")
    ]
    assert diagnostic["emissions"][0]["method_metric_binding_set_refs"] == [
        binding_ref.model_dump(mode="json")
    ]


def test_failed_execute_result_bundle_and_binding_survive_bounded_diagnostic_readback() -> None:
    bundle_ref = _selected_ref("foundry.method_execution_bundle", "e", "5")
    binding_ref = _selected_ref("foundry.method_metric_binding_set", "f", "6")
    failed_result = SimpleNamespace(
        ok=False,
        simulation_result_ref=None,
        method_execution_bundle_ref=bundle_ref,
        derived_refs=[
            SimpleNamespace(role="method_execution_bundle", ref=bundle_ref),
            SimpleNamespace(role="method_metric_binding_set", ref=binding_ref),
        ],
    )
    capture = _RuntimeOriginCapturingFoundryPort(
        delegate=_FoundryDelegate(failed_result),
        job_id="job-failed",
        run_id="run-failed",
        attempt=2,
        lease_owner="lease-failed",
    )
    capture.execute(store=object(), request=object())
    receipt = capture.producer_receipt()
    assert receipt is not None
    assert receipt.emissions == ()

    diagnostic = receipt.diagnostic_model()
    assert diagnostic.authority_status == "candidate_only"
    assert diagnostic.job_id == "job-failed"
    assert diagnostic.run_id == "run-failed"
    assert diagnostic.attempt == 2
    assert len(diagnostic.emissions) == 1
    emitted = diagnostic.emissions[0]
    assert emitted.execute_result_status == "failed"
    assert emitted.output_ref_status == "partial"
    assert emitted.simulation_result_ref is None
    assert emitted.method_execution_bundle_refs == (bundle_ref,)
    assert emitted.method_metric_binding_set_refs == (binding_ref,)
    assert diagnostic.limitations == (
        "producer_diagnostic_only",
        "workflow_authority_not_established",
        "scientific_validity_not_established",
    )

    state = {
        "artifacts_index": {
            "simulation_result_ref": _selected_ref(
                "foundry.simulation_result", "a", "1"
            ).model_dump(mode="json"),
            "method_execution_bundle_ref": bundle_ref.model_dump(mode="json"),
            "method_metric_binding_set_ref": binding_ref.model_dump(mode="json"),
        }
    }
    assert (
        _selected_graph_source_refs_from_receipt(
            graph_output_refs=_scientist_graph_output_refs(state),
            receipt=receipt,
            job_id="job-failed",
            run_id="run-failed",
            attempt=2,
            lease_owner="lease-failed",
        )
        is None
    )


def test_failed_producer_diagnostic_is_read_from_current_tenant_scoped_job_progress() -> None:
    bundle_ref = _selected_ref("foundry.method_execution_bundle", "e", "5")
    binding_ref = _selected_ref("foundry.method_metric_binding_set", "f", "6")
    capture = _RuntimeOriginCapturingFoundryPort(
        delegate=_FoundryDelegate(
            SimpleNamespace(
                ok=False,
                simulation_result_ref=None,
                method_execution_bundle_ref=bundle_ref,
                derived_refs=[
                    SimpleNamespace(role="method_execution_bundle", ref=bundle_ref),
                    SimpleNamespace(role="method_metric_binding_set", ref=binding_ref),
                ],
            )
        ),
        job_id="job-current",
        run_id="run-current",
        attempt=5,
        lease_owner="lease-current",
    )
    capture.execute(store=object(), request=object())
    diagnostic = capture.producer_receipt().diagnostic_model()
    persisted = diagnostic.model_dump(mode="json")
    record = SimpleNamespace(
        job_id="job-current",
        kind="workflow_run",
        run_id="run-current",
        attempt=5,
        state="completed",
        progress={
            "authority_path": "legacy_shadow",
            "method_execution_producer_diagnostic": persisted,
        },
    )

    class _ControlStore:
        def get_job_created_event_payload(self, job_id: str) -> dict[str, Any]:
            assert job_id == "job-current"
            return {
                "job_id": "job-current",
                "run_id": "run-current",
                "job_kind": "workflow_run",
                "execution_scope": {"tenant_id": "tenant-current", "cell_id": "cell-current"},
            }

    class _ReadService:
        _control_store = _ControlStore()

        @staticmethod
        def get_latest_job_for_run(run_id: str) -> Any:
            assert run_id == "run-current"
            return record

    selected = ControlPlaneService.get_method_execution_producer_diagnostic(
        _ReadService(),
        run_id="run-current",
        tenant_id="tenant-current",
        cell_id="cell-current",
    )
    assert selected == diagnostic
    assert selected.emissions[0].method_execution_bundle_refs == (bundle_ref,)

    assert (
        ControlPlaneService.get_method_execution_producer_diagnostic(
            _ReadService(),
            run_id="run-current",
            tenant_id="tenant-other",
            cell_id="cell-current",
        )
        is None
    )


def test_graph_origin_receipt_withholds_selection_after_bounded_inventory_truncates() -> None:
    selected_refs = (
        _selected_ref("foundry.simulation_result", "a", "1"),
        _selected_ref("foundry.method_execution_bundle", "b", "2"),
        _selected_ref("foundry.method_metric_binding_set", "c", "3"),
    )
    result = SimpleNamespace(
        ok=True,
        simulation_result_ref=selected_refs[0],
        method_execution_bundle_ref=selected_refs[1],
        derived_refs=[
            SimpleNamespace(role="method_execution_bundle", ref=selected_refs[1]),
            SimpleNamespace(role="method_metric_binding_set", ref=selected_refs[2]),
        ],
    )
    capture = _RuntimeOriginCapturingFoundryPort(
        delegate=_FoundryDelegate(result),
        job_id="job-bounded",
        run_id="run-bounded",
        attempt=3,
        lease_owner="lease-bounded",
    )
    for _ in range(17):
        capture.execute(store=object(), request=object())
    receipt = capture.producer_receipt()
    assert receipt is not None
    assert len(receipt.diagnostics) == 16
    assert receipt.inventory_truncated is True
    assert len(receipt.diagnostic_model().emissions) == 16

    state = {
        "artifacts_index": {
            "simulation_result_ref": selected_refs[0].model_dump(mode="json"),
            "method_execution_bundle_ref": selected_refs[1].model_dump(mode="json"),
            "method_metric_binding_set_ref": selected_refs[2].model_dump(mode="json"),
        }
    }
    assert (
        _selected_graph_source_refs_from_receipt(
            graph_output_refs=_scientist_graph_output_refs(state),
            receipt=receipt,
            job_id="job-bounded",
            run_id="run-bounded",
            attempt=3,
            lease_owner="lease-bounded",
        )
        is None
    )


def test_authorized_run_details_surfaces_only_the_bounded_candidate_diagnostic(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_ref = _selected_ref("foundry.method_execution_bundle", "e", "5")
    binding_ref = _selected_ref("foundry.method_metric_binding_set", "f", "6")
    diagnostic = MethodExecutionProducerDiagnostic(
        job_id="job-surface",
        run_id=str(runtime_api_env["core_run_id"]),
        attempt=1,
        emissions=(
            MethodExecutionProducerEmissionDiagnostic(
                emission_index=0,
                execute_result_status="failed",
                output_ref_status="partial",
                method_execution_bundle_refs=(bundle_ref,),
                method_metric_binding_set_refs=(binding_ref,),
            ),
        ),
    )

    class _DiagnosticService:
        def get_method_execution_producer_diagnostic(
            self,
            *,
            run_id: str,
            tenant_id: str,
            cell_id: str | None,
        ) -> MethodExecutionProducerDiagnostic:
            assert run_id == runtime_api_env["core_run_id"]
            assert tenant_id == runtime_api_env["tenant_a"]
            assert cell_id == runtime_api_env["cell_a"]
            return diagnostic

    monkeypatch.setattr(
        runs_routes,
        "_control_service_from_request",
        lambda request: _DiagnosticService(),
    )
    response = runtime_api_env["client"].get(f"/api/v1/runs/{runtime_api_env['core_run_id']}")
    assert response.status_code == 200
    observed = response.json()["run"]["method_execution_producer_diagnostic"]
    assert observed["authority_status"] == "candidate_only"
    assert observed["emissions"][0]["execute_result_status"] == "failed"
    assert observed["emissions"][0]["simulation_result_ref"] is None
    assert observed["emissions"][0]["method_execution_bundle_refs"] == [
        bundle_ref.model_dump(mode="json")
    ]
    assert observed["emissions"][0]["method_metric_binding_set_refs"] == [
        binding_ref.model_dump(mode="json")
    ]
    assert "data" not in observed


def _graph_selection(
    *,
    candidate_ref: ArtifactRef | None,
    run_id: str = "run-owner",
) -> GraphMethodExecutionSelection:
    return GraphMethodExecutionSelection(
        job_id="job-owner",
        run_id=run_id,
        attempt=7,
        method_result_ref=None,
        source_experiment_state_ref=_selected_ref("scientist.experiment_state", "1", "1"),
        simulation_result_ref=_selected_ref("foundry.simulation_result", "2", "2"),
        method_execution_bundle_ref=_selected_ref("foundry.method_execution_bundle", "3", "3"),
        method_metric_binding_set_ref=_selected_ref("foundry.method_metric_binding_set", "4", "4"),
        source_candidate_ref=candidate_ref,
        metric_verification_status=(
            "verified" if candidate_ref is not None else "verification_missing"
        ),
        method_metric_projection=(
            MethodMetricProjectionSelection(
                vector_ref=_selected_ref("scientist.policy_evaluation_vector", "5", "5"),
                verifier_revision="1.0",
                verifier_implementation_sha256="sha256:" + "6" * 64,
            )
            if candidate_ref is not None
            else None
        ),
    )


def test_completed_method_metric_lookup_joins_exact_candidate_and_owner_selection() -> None:
    candidate_ref = _selected_ref("scientist.policy_design.candidate", "7", "7")
    selection = _graph_selection(candidate_ref=candidate_ref)

    class _OwnerService:
        @staticmethod
        def get_method_execution_selection(
            *, run_id: str, tenant_id: str, cell_id: str | None
        ) -> GraphMethodExecutionSelection:
            assert (run_id, tenant_id, cell_id) == (
                "run-owner",
                "tenant-owner",
                "cell-owner",
            )
            return selection

    resolved = ControlPlaneService.resolve_completed_method_metric_selection(
        _OwnerService(),
        source_run_id="run-owner",
        candidate_ref=candidate_ref,
        tenant_id="tenant-owner",
        cell_id="cell-owner",
    )
    assert resolved is not None
    assert resolved.source_run_id == "run-owner"
    assert resolved.source_candidate_ref == candidate_ref
    assert resolved.source_experiment_state_ref == selection.source_experiment_state_ref
    assert resolved.selection == selection

    same_artifact_different_selected_profile = _selected_ref(
        "scientist.policy_design.candidate", "7", "8"
    )
    assert (
        ControlPlaneService.resolve_completed_method_metric_selection(
            _OwnerService(),
            source_run_id="run-owner",
            candidate_ref=same_artifact_different_selected_profile,
            tenant_id="tenant-owner",
            cell_id="cell-owner",
        )
        is None
    )

    unverified_selection = _graph_selection(candidate_ref=None)

    class _UnverifiedOwnerService:
        @staticmethod
        def get_method_execution_selection(
            *, run_id: str, tenant_id: str, cell_id: str | None
        ) -> GraphMethodExecutionSelection:
            return unverified_selection

    assert (
        ControlPlaneService.resolve_completed_method_metric_selection(
            _UnverifiedOwnerService(),
            source_run_id="run-owner",
            candidate_ref=candidate_ref,
            tenant_id="tenant-owner",
            cell_id="cell-owner",
        )
        is None
    )


def test_completed_selection_resolves_only_terminal_finalization_state_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.core import artifacts as artifacts_module
    from polisyos.core.artifacts import canonical_profile
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.runtime.http.services.adapters import core_run as core_run_adapter
    from polisyos.scientist.orchestration.engine.finalization import (
        FINALIZATION_KIND,
        FINALIZATION_SCHEMA_NAME,
        FINALIZATION_SCHEMA_VERSION,
        WorkflowStateFinalization,
    )

    finalization_ref = _selected_ref("scientist.workflow_state_finalization", "9", "9")
    selected_state_ref = _selected_ref("scientist.experiment_state", "a", "b")
    prior_state_ref = _selected_ref("scientist.experiment_state", "c", "d")
    terminal = SimpleNamespace(
        run_id="run-owner",
        tenant_id="tenant-owner",
        cell_id="cell-owner",
        workflow_finalization_ref=finalization_ref,
        manifest=SimpleNamespace(
            run_id="run-owner",
            control_job_id="job-owner",
            tenant_id="tenant-owner",
            cell_id="cell-owner",
            outputs=[prior_state_ref, selected_state_ref, finalization_ref],
        ),
    )
    finalization = WorkflowStateFinalization(
        run_id="run-owner",
        workflow_id="workflow-owner",
        workflow_spec_ref=_selected_ref("scientist.workflow_spec", "e", "e"),
        prior_state_ref=prior_state_ref,
        final_state_ref=selected_state_ref,
    )
    bounded_manifest = SimpleNamespace(
        kind=FINALIZATION_KIND,
        media_type="application/json",
        artifact_schema=SchemaInfo(
            name=FINALIZATION_SCHEMA_NAME,
            version=FINALIZATION_SCHEMA_VERSION,
        ),
    )
    bounded_holder = {
        "value": SimpleNamespace(
            effective_ref=finalization_ref,
            manifest=bounded_manifest,
        )
    }
    finalization_holder = {"value": finalization}
    reader_calls: list[tuple[Any, ArtifactRef]] = []

    def read_bounded(store: Any, selected_ref: ArtifactRef, *, limits: Any) -> Any:
        assert store is service._artifact_store
        assert limits.max_manifest_bytes > 0
        reader_calls.append((store, selected_ref))
        return bounded_holder["value"]

    def validate_bounded(model_type: Any, bounded: Any) -> Any:
        assert model_type is WorkflowStateFinalization
        assert bounded is bounded_holder["value"]
        return finalization_holder["value"]

    monkeypatch.setattr(
        core_run_adapter,
        "load_terminal_core_run_source",
        lambda **_: terminal,
    )
    monkeypatch.setattr(artifacts_module, "read_core_json_artifact_bounded", read_bounded)
    monkeypatch.setattr(
        canonical_profile,
        "validate_core_model_bounded_read",
        validate_bounded,
    )
    service = SimpleNamespace(
        _artifact_store=object(),
        _core_runs_root=Path("/runtime/core-runs"),
    )

    selected = ControlPlaneService._terminal_experiment_state_ref_for_control_job(
        service,
        job_id="job-owner",
        run_id="run-owner",
        tenant_id="tenant-owner",
        cell_id="cell-owner",
    )
    assert selected == selected_state_ref
    assert reader_calls == [(service._artifact_store, finalization_ref)]

    terminal.workflow_finalization_ref = None
    assert (
        ControlPlaneService._terminal_experiment_state_ref_for_control_job(
            service,
            job_id="job-owner",
            run_id="run-owner",
            tenant_id="tenant-owner",
            cell_id="cell-owner",
        )
        is None
    )
    terminal.workflow_finalization_ref = finalization_ref

    terminal.manifest.outputs = [prior_state_ref, selected_state_ref]
    assert (
        ControlPlaneService._terminal_experiment_state_ref_for_control_job(
            service,
            job_id="job-owner",
            run_id="run-owner",
            tenant_id="tenant-owner",
            cell_id="cell-owner",
        )
        is None
    )
    terminal.manifest.outputs = [prior_state_ref, selected_state_ref, finalization_ref]

    terminal.manifest.outputs.append(selected_state_ref)
    assert (
        ControlPlaneService._terminal_experiment_state_ref_for_control_job(
            service,
            job_id="job-owner",
            run_id="run-owner",
            tenant_id="tenant-owner",
            cell_id="cell-owner",
        )
        is None
    )
    terminal.manifest.outputs = [prior_state_ref, selected_state_ref, finalization_ref]

    bounded_holder["value"] = SimpleNamespace(
        effective_ref=_selected_ref("scientist.workflow_state_finalization", "9", "8"),
        manifest=bounded_manifest,
    )
    assert (
        ControlPlaneService._terminal_experiment_state_ref_for_control_job(
            service,
            job_id="job-owner",
            run_id="run-owner",
            tenant_id="tenant-owner",
            cell_id="cell-owner",
        )
        is None
    )
    bounded_holder["value"] = SimpleNamespace(
        effective_ref=finalization_ref,
        manifest=SimpleNamespace(
            kind="wrong.kind",
            media_type="application/json",
            artifact_schema=bounded_manifest.artifact_schema,
        ),
    )
    assert (
        ControlPlaneService._terminal_experiment_state_ref_for_control_job(
            service,
            job_id="job-owner",
            run_id="run-owner",
            tenant_id="tenant-owner",
            cell_id="cell-owner",
        )
        is None
    )
    bounded_holder["value"] = SimpleNamespace(
        effective_ref=finalization_ref,
        manifest=SimpleNamespace(
            kind=FINALIZATION_KIND,
            media_type="application/json",
            artifact_schema=SchemaInfo(
                name=FINALIZATION_SCHEMA_NAME,
                version="wrong-version",
            ),
        ),
    )
    assert (
        ControlPlaneService._terminal_experiment_state_ref_for_control_job(
            service,
            job_id="job-owner",
            run_id="run-owner",
            tenant_id="tenant-owner",
            cell_id="cell-owner",
        )
        is None
    )
    bounded_holder["value"] = SimpleNamespace(
        effective_ref=finalization_ref,
        manifest=bounded_manifest,
    )

    finalization_holder["value"] = finalization.model_copy(update={"run_id": "run-other"})
    assert (
        ControlPlaneService._terminal_experiment_state_ref_for_control_job(
            service,
            job_id="job-owner",
            run_id="run-owner",
            tenant_id="tenant-owner",
            cell_id="cell-owner",
        )
        is None
    )
    finalization_holder["value"] = finalization.model_copy(
        update={"final_state_ref": _selected_ref("scientist.experiment_state", "a", "c")}
    )
    assert (
        ControlPlaneService._terminal_experiment_state_ref_for_control_job(
            service,
            job_id="job-owner",
            run_id="run-owner",
            tenant_id="tenant-owner",
            cell_id="cell-owner",
        )
        is None
    )


def test_completed_method_metric_consumer_uses_runtime_owner_and_fails_closed_for_missing_source(
    runtime_api_env: dict[str, Any],
) -> None:
    """The Scientist reader receives the real Runtime owner, not caller refs."""
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        CompletedMethodMetricSelectionOwner as ConsumerOwner,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        read_completed_admitted_method_metric_projection,
    )

    service = runtime_api_env["app"].state._control_service
    assert isinstance(service, ConsumerOwner)
    candidate_ref = _selected_ref("scientist.policy_design.candidate", "d", "e")
    projection = read_completed_admitted_method_metric_projection(
        service._artifact_store,
        owner=service,
        source_run_id=runtime_api_env["core_run_id"],
        candidate_ref=candidate_ref,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )

    assert projection.status == "verification_missing"
    assert projection.vector_ref is None
    assert projection.observations == ()
    assert projection.limitations == ("completed_method_metric_source_not_established",)

    wrong_scope = read_completed_admitted_method_metric_projection(
        service._artifact_store,
        owner=service,
        source_run_id=runtime_api_env["core_run_id"],
        candidate_ref=candidate_ref,
        tenant_id="tenant-not-owned",
        cell_id=runtime_api_env["cell_a"],
    )
    assert wrong_scope.status == "verification_missing"
    assert wrong_scope.vector_ref is None
    assert wrong_scope.observations == ()
    assert wrong_scope.limitations == ("completed_method_metric_source_not_established",)


def test_synthetic_graph_capture_remains_limited_under_cold_protected_get(
    runtime_api_env: dict[str, Any],
) -> None:
    """A cold GET rechecks the persisted attempt and terminal Core state."""
    from polisyos.core.artifacts import artifact_ref_for_manifest
    from polisyos.core.artifacts.manifest import ProducerInfo
    from polisyos.core.run.context import RunContext
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.scientist.orchestration.engine.finalization import (
        FINALIZATION_KIND,
        FINALIZATION_SCHEMA_NAME,
        FINALIZATION_SCHEMA_VERSION,
        WorkflowStateFinalization,
    )

    app = runtime_api_env["app"]
    service = app.state._control_service
    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    run_id = "R_e02_graph_metric_current_get"
    job_id = "job_e02_graph_metric_current_get"
    store = service._artifact_store
    registry_ref = runtime_api_env["registry_bundle_ref"]
    state_ref = artifact_ref_for_manifest(
        store.get_manifest(
            ArtifactID.model_validate(runtime_api_env["experiment_state_artifact_id"])
        )
    )
    workflow_spec_ref = artifact_ref_for_manifest(
        store.get_manifest(ArtifactID.model_validate(runtime_api_env["workflow_spec_artifact_id"]))
    )
    graph_refs = tuple(
        _put_selected_json(
            store,
            {"fixture": "bounded-graph-output"},
            kind=kind,
            schema=SchemaInfo(name=f"e02.{kind}", version="1.0"),
        )
        for kind in (
            "foundry.simulation_result",
            "foundry.method_execution_bundle",
            "foundry.method_metric_binding_set",
        )
    )

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        service._control_store.create_job(
            job_id=job_id,
            kind="workflow_run",
            run_id=run_id,
            pipeline_id=None,
            requested_execution_profile=None,
            effective_execution_profile="governed",
            policy_flags={},
            capability_manifest_ref=None,
            payload_ref=None,
            submitted_by="e02-composed-source-test",
            creation_event_payload={
                "job_id": job_id,
                "run_id": run_id,
                "job_kind": "workflow_run",
                "execution_scope": {"tenant_id": tenant_id, "cell_id": cell_id},
            },
        )
        service._control_store.mark_running(
            job_id=job_id,
            worker_id="e02-composed-source-test",
            lease_seconds=120,
        )
        current_job = service._control_store.get_job(job_id)
        assert current_job is not None
        assert current_job.lease_owner is not None
        execute_result = ExecuteResult(
            ok=True,
            simulation_result_ref=graph_refs[0],
            derived_refs=[
                DerivedArtifact(role="method_execution_bundle", ref=graph_refs[1]),
                DerivedArtifact(role="method_metric_binding_set", ref=graph_refs[2]),
            ],
        )
        foundry_capture = _RuntimeOriginCapturingFoundryPort(
            delegate=_FoundryDelegate(execute_result),
            job_id=job_id,
            run_id=run_id,
            attempt=current_job.attempt,
            lease_owner=current_job.lease_owner,
        )
        assert foundry_capture.execute(store=store, request=object()) is execute_result
        producer_receipt = foundry_capture.producer_receipt()
        assert producer_receipt is not None
        graph_output_refs = _scientist_graph_output_refs(
            {
                "artifacts_index": {
                    "simulation_result_ref": graph_refs[0].model_dump(mode="json"),
                    "method_execution_bundle_ref": graph_refs[1].model_dump(mode="json"),
                    "method_metric_binding_set_ref": graph_refs[2].model_dump(mode="json"),
                }
            }
        )
        captured_source_refs = _selected_graph_source_refs_from_receipt(
            graph_output_refs=graph_output_refs,
            receipt=producer_receipt,
            job_id=job_id,
            run_id=run_id,
            attempt=current_job.attempt,
            lease_owner=current_job.lease_owner,
        )
        assert captured_source_refs == graph_refs
        assert (
            _selected_graph_source_refs_from_receipt(
                graph_output_refs=graph_output_refs,
                receipt=producer_receipt,
                job_id=job_id,
                run_id=run_id,
                attempt=current_job.attempt + 1,
                lease_owner=current_job.lease_owner,
            )
            is None
        )
        assert (
            _selected_graph_source_refs_from_receipt(
                graph_output_refs=graph_output_refs,
                receipt=producer_receipt,
                job_id=job_id,
                run_id=run_id,
                attempt=current_job.attempt,
                lease_owner="replaced-lease-owner",
            )
            is None
        )
        selection = GraphMethodExecutionSelection(
            job_id=job_id,
            run_id=run_id,
            attempt=current_job.attempt,
            source_experiment_state_ref=state_ref,
            simulation_result_ref=captured_source_refs[0],
            method_execution_bundle_ref=captured_source_refs[1],
            method_metric_binding_set_ref=captured_source_refs[2],
            source_candidate_ref=None,
            metric_verification_status="verification_missing",
            method_metric_projection=None,
        )
        workflow_finalization = WorkflowStateFinalization(
            run_id=run_id,
            workflow_id="e02-composed-source-test",
            workflow_spec_ref=workflow_spec_ref,
            prior_state_ref=state_ref,
            final_state_ref=state_ref,
        )
        finalization_ref = _put_selected_json(
            store,
            workflow_finalization.model_dump(mode="json"),
            kind=FINALIZATION_KIND,
            schema=SchemaInfo(
                name=FINALIZATION_SCHEMA_NAME,
                version=FINALIZATION_SCHEMA_VERSION,
            ),
        )
        run = RunContext.start(
            store=store,
            registry_bundle=registry_ref,
            producer=ProducerInfo(
                component="polisyos.tests.e02.graph_metric_current_get",
                version="1.0.0",
            ),
            run_dir=service._core_runs_root / run_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        run.run_manifest.control_job_id = job_id
        run.add_output(state_ref)
        run.add_output(finalization_ref)
        run.finalize(status="completed", workflow_finalization_ref=finalization_ref)
        service._control_store.complete_job(
            job_id=job_id,
            run_id=run_id,
            method_execution_selection=selection,
            expected_lease_owner="e02-composed-source-test",
            expected_attempt=current_job.attempt,
        )

    runtime_context = getattr(app.state, "runtime_api_ctx", None)
    if runtime_context is None:
        runtime_context = app.state.runtime_container.runtime_api_context
    runtime_context.run_index.refresh(force=True)

    assert (
        service.get_method_execution_selection(
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        == selection
    )
    fresh = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}/method-metrics")
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["status"] == "verification_missing"
    assert fresh.json()["vector_ref"] is None
    assert fresh.json()["observations"] == []
    assert fresh.json()["limitations"] == ["runtime_owner_has_no_verified_method_metric_projection"]

    # The same HTTP route must see a later attempt as current and withhold the old row.
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        service._control_store.mark_running(
            job_id=job_id,
            worker_id="e02-revocation-probe",
            lease_seconds=120,
        )
    revoked = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}/method-metrics")
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["status"] == "verification_missing"
    assert revoked.json()["vector_ref"] is None
    assert revoked.json()["observations"] == []
    assert revoked.json()["limitations"] == ["current_method_metric_selection_not_established"]


@pytest.mark.parametrize(
    ("capture_only", "root_graph_outputs"),
    [(False, True), (True, True), (True, False)],
    ids=("explicit-scalar-rooted", "capture-only-rooted", "capture-only-unrooted"),
)
def test_registered_public_graph_execute_reaches_runtime_owner_and_cold_metric_get(
    runtime_api_env: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capture_only: bool,
    root_graph_outputs: bool,
    request: pytest.FixtureRequest,
) -> None:
    """Carry actual Foundry refs through test-built Core ownership to a cold Runtime GET."""
    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
    from unit.scientist.nodes.builtins.decide.test_policy_runtime_method_metrics import (
        _exercise_public_execute_method_metric_source,
    )

    from polisyos.core.artifacts import artifact_ref_for_manifest, validate_core_model_json_artifact
    from polisyos.core.artifacts.manifest import ProducerInfo
    from polisyos.core.contracts.control import WorkflowRunRequest
    from polisyos.core.run.context import RunContext
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.foundry.methods.registry import MethodRegistry
    from polisyos.ir.kernel.method_metrics import METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID
    from polisyos.runtime.http.execution_policy import RuntimePrincipal
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        read_completed_admitted_method_metric_projection,
    )
    from polisyos.scientist.orchestration.engine.executor import (
        NodeRunRecord,
        _selected_successful_node_output_refs,
    )
    from polisyos.scientist.orchestration.engine.finalization import (
        FINALIZATION_KIND,
        FINALIZATION_SCHEMA_NAME,
        FINALIZATION_SCHEMA_VERSION,
        WorkflowStateFinalization,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

    service = runtime_api_env["app"].state._control_service
    stop_embedded_control_worker(service)
    store = service._artifact_store
    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]

    principal = RuntimePrincipal(
        subject="e02-public-execute-origin-test",
        tenant_id=tenant_id,
        cell_id=cell_id,
        roles=frozenset({"analyst"}),
        authenticated=True,
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        launch = service.launch_workflow_run(
            WorkflowRunRequest(
                data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
                params={"control_plane_transition": "legacy_shadow"},
            ),
            principal=principal,
        )
    job_id = launch.job_id
    run_id = launch.run_id
    observed: dict[str, Any] = {}
    producer_receipts: list[Any] = []
    original_producer_receipt = _RuntimeOriginCapturingFoundryPort.producer_receipt

    def capture_runtime_receipt(port: _RuntimeOriginCapturingFoundryPort) -> Any:
        receipt = original_producer_receipt(port)
        producer_receipts.append(receipt)
        return receipt

    monkeypatch.setattr(
        _RuntimeOriginCapturingFoundryPort,
        "producer_receipt",
        capture_runtime_receipt,
    )

    def execute_registered_graph(
        state: dict[str, Any],
        *,
        store: Any,
        foundry: Any,
        method_metric_selection_owner: Any,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        assert store is service._artifact_store
        assert method_metric_selection_owner is service
        producer = _exercise_public_execute_method_metric_source(
            tmp_path,
            monkeypatch,
            artifact_store=store,
            foundry_port=foundry,
            job_id=job_id,
            run_id=run_id,
            attempt=1,
            capture_only=capture_only,
            request=request,
        )
        execute_result = producer["execute_result"]
        if capture_only:
            assert producer["compiled_program_graph_ref"] is not None
            assert producer["compiled_exec_plan_ref"] is not None
            assert producer["selected_method_plan_ref"] is not None
            assert producer["binding_ref"].manifest_profile_sha256 is not None
            assert producer["method_fqn"] == "tests.capture_only.runtime_unseen_probe@1.0.0"
            computed = producer["computed_method_outputs"]
            assert len(computed) == 1
            assert computed[0]["result"]["mean_change"] == pytest.approx(1.0)
            assert computed[0]["result"]["n_agents"] == 3
        observed["producer"] = producer
        graph_refs = {
            "simulation_result_ref": execute_result.simulation_result_ref,
            "method_execution_bundle_ref": producer["bundle_ref"],
            "method_metric_binding_set_ref": producer["binding_ref"],
        }
        final_state = ExperimentState.model_validate(state)
        final_state.control_job_id = job_id
        final_state.artifacts_index.update(graph_refs)
        observed["final_state"] = final_state.model_dump(mode="json")
        state_ref = _put_selected_json(
            store,
            final_state.model_dump(mode="json"),
            kind="scientist.experiment_state",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.ExperimentState",
                version=final_state.schema_version,
            ),
        )
        observed["experiment_state_ref"] = state_ref
        workflow_spec_ref = artifact_ref_for_manifest(
            store.get_manifest(
                ArtifactID.model_validate(runtime_api_env["workflow_spec_artifact_id"])
            )
        )
        workflow_finalization = WorkflowStateFinalization(
            run_id=run_id,
            workflow_id="e02-public-execute-origin-test",
            workflow_spec_ref=workflow_spec_ref,
            prior_state_ref=state_ref,
            final_state_ref=state_ref,
        )
        finalization_ref = _put_selected_json(
            store,
            workflow_finalization.model_dump(mode="json"),
            kind=FINALIZATION_KIND,
            schema=SchemaInfo(
                name=FINALIZATION_SCHEMA_NAME,
                version=FINALIZATION_SCHEMA_VERSION,
            ),
        )
        run = RunContext.start(
            store=store,
            registry_bundle=runtime_api_env["registry_bundle_ref"],
            producer=ProducerInfo(
                component="polisyos.tests.e02.public_execute_runtime_method_metric",
                version="1.0.0",
            ),
            run_dir=service._core_runs_root / run_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        run.run_manifest.control_job_id = job_id
        run.add_output(state_ref)
        run.add_output(finalization_ref)
        # This test stubs run_experiment, so model the normal executor's selected
        # successful-output rooting over the three actual Foundry refs explicitly.
        graph_record = NodeRunRecord(
            alias="fixture_method_simulation",
            node_id="fixture_foundry_execute",
            status="ok",
            duration_ms=0,
            artifacts=list(graph_refs.values()),
        )
        selected_graph_outputs = _selected_successful_node_output_refs(
            [graph_record],
            selected_artifacts=final_state.artifacts_index.values(),
            existing_outputs=run.run_manifest.outputs,
        )
        assert tuple(artifact_ref_identity_key(ref) for ref in selected_graph_outputs) == tuple(
            artifact_ref_identity_key(ref) for ref in graph_refs.values()
        )
        if root_graph_outputs:
            for output_ref in selected_graph_outputs:
                run.add_output(output_ref)
        run.finalize(status="completed", workflow_finalization_ref=finalization_ref)
        return final_state.model_dump(mode="json")

    monkeypatch.setattr("polisyos.scientist.api.run_experiment", execute_registered_graph)
    dispatched = dispatch_one_control_job(
        store=service._control_store,
        handler=service._process_control_job,
        expected_job_id=job_id,
    )
    assert dispatched == job_id
    current_job = service._control_store.get_job(job_id)
    assert current_job is not None
    assert current_job.run_id == run_id
    assert current_job.attempt == 1
    assert current_job.state == "completed"
    producer = observed["producer"]
    execute_result = producer["execute_result"]
    assert execute_result is not None
    assert execute_result.ok is True
    simulation_ref = execute_result.simulation_result_ref
    assert simulation_ref is not None
    bundle_ref = producer["bundle_ref"]
    binding_ref = producer["binding_ref"]
    candidate_ref = producer["candidate_ref"]
    assert isinstance(bundle_ref, ArtifactRef)
    assert isinstance(binding_ref, ArtifactRef)
    assert isinstance(candidate_ref, ArtifactRef)
    experiment_state_ref = observed["experiment_state_ref"]
    assert isinstance(experiment_state_ref, ArtifactRef)
    assert len(producer_receipts) == 1
    producer_receipt = producer_receipts[0]
    graph_output_refs = _scientist_graph_output_refs(observed["final_state"])
    source_refs = _selected_graph_source_refs_from_receipt(
        graph_output_refs=graph_output_refs,
        receipt=producer_receipt,
        job_id=job_id,
        run_id=run_id,
        attempt=current_job.attempt,
        lease_owner=producer_receipt.lease_owner,
    )
    assert source_refs is not None
    assert tuple(artifact_ref_identity_key(ref) for ref in source_refs) == tuple(
        artifact_ref_identity_key(ref) for ref in (simulation_ref, bundle_ref, binding_ref)
    )
    assert (
        _selected_graph_source_refs_from_receipt(
            graph_output_refs=graph_output_refs,
            receipt=producer_receipt,
            job_id=job_id,
            run_id=run_id,
            attempt=current_job.attempt + 1,
            lease_owner=producer_receipt.lease_owner,
        )
        is None
    )
    assert (
        _selected_graph_source_refs_from_receipt(
            graph_output_refs=graph_output_refs,
            receipt=producer_receipt,
            job_id=job_id,
            run_id=run_id,
            attempt=current_job.attempt,
            lease_owner="replaced-lease-owner",
        )
        is None
    )

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        selection = service.get_method_execution_selection(
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
    assert isinstance(selection, GraphMethodExecutionSelection)
    if capture_only:
        assert selection.source_candidate_ref is None
    else:
        assert selection.source_candidate_ref is not None
        assert artifact_ref_identity_key(selection.source_candidate_ref) == (
            artifact_ref_identity_key(candidate_ref)
        )
    assert selection.job_id == job_id
    assert selection.run_id == run_id
    assert selection.attempt == current_job.attempt
    selection_source_refs = (
        selection.simulation_result_ref,
        selection.method_execution_bundle_ref,
        selection.method_metric_binding_set_ref,
        selection.source_experiment_state_ref,
    )
    expected_source_refs = (
        simulation_ref,
        bundle_ref,
        binding_ref,
        experiment_state_ref,
    )
    assert tuple(artifact_ref_identity_key(ref) for ref in selection_source_refs) == tuple(
        artifact_ref_identity_key(ref) for ref in expected_source_refs
    )
    if capture_only:
        assert selection.metric_verification_status == "verification_missing"
        assert selection.method_metric_projection is None
    else:
        assert selection.metric_verification_status == "verified"
        assert selection.method_metric_projection is not None
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            admitted_vector = validate_core_model_json_artifact(
                PolicyEvaluationVector,
                store,
                selection.method_metric_projection.vector_ref,
            )
        assert len(admitted_vector.method_metric_observations) == 1
        observation = admitted_vector.method_metric_observations[0]
        assert observation.value == pytest.approx(1.0)
        assert observation.law_id == METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID
        assert observation.objective_id == "objective_ex_ante_mean_change"
        assert observation.metric_id == "metric_ex_ante_mean_change"
        assert observation.metric_unit_id == "value"
        assert observation.quantity_role == "scenario_delta"
        assert observation.time_role == "pre_dispatch_state"
        assert observation.population_id == "captured_model_input_rows"
        assert observation.axes == ("n_agents",)
        assert observation.denominator_id == "n_agents"
        assert "external_causal_validity_not_established" in observation.limitations
        assert "external_legal_permission_not_established" in observation.limitations

    runtime_context = getattr(runtime_api_env["app"].state, "runtime_api_ctx", None)
    if runtime_context is None:
        runtime_context = runtime_api_env["app"].state.runtime_container.runtime_api_context
    # Each parameter case gets a fresh function-scoped Runtime fixture; force a full
    # rebuild to test the removal case without a cached tenant mapping.
    runtime_context.run_index.refresh(force=True)
    indexed_run = runtime_context.run_index.get_run(run_id)
    assert indexed_run is not None
    indexed_root_identities = {
        artifact_ref_identity_key(ref) for ref in indexed_run.details.root_artifacts
    }
    for graph_ref in (simulation_ref, bundle_ref, binding_ref):
        assert (
            artifact_ref_identity_key(graph_ref) in indexed_root_identities
        ) is root_graph_outputs
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        persisted_selection = service.get_method_execution_selection(
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
    assert persisted_selection == selection

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        fresh = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}/method-metrics")
        if capture_only:
            run_details = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}")
            content = runtime_api_env["client"].get(
                f"/api/v1/artifacts/{bundle_ref.artifact_id}/content",
                params={"manifest_profile_sha256": bundle_ref.manifest_profile_sha256},
            )
    assert fresh.status_code == 200, fresh.text
    payload = fresh.json()
    if capture_only:
        assert payload["status"] == "verification_missing"
        assert payload["vector_ref"] is None
        assert payload["observations"] == []
        assert run_details.status_code == 200, run_details.text
        diagnostic = run_details.json()["run"]["method_execution_producer_diagnostic"]
        assert diagnostic["authority_status"] == "candidate_only"
        assert diagnostic["run_id"] == run_id
        assert diagnostic["attempt"] == current_job.attempt
        assert diagnostic["emissions"]
        assert diagnostic["emissions"][0]["method_execution_bundle_refs"] == [
            bundle_ref.model_dump(mode="json")
        ]
        assert diagnostic["emissions"][0]["method_metric_binding_set_refs"] == [
            binding_ref.model_dump(mode="json")
        ]
        if root_graph_outputs:
            # Candidate facts are exposed through the owner-backed run diagnostic
            # above. The artifact content route must withhold candidate bytes absent
            # an admitted artifact-purpose surface signal.
            assert content.status_code == 409, content.text
            refusal = content.json()
            assert refusal["code"] == "authority_surface_admission_blocked"
            decision = refusal["extensions"]["authority_surface_decision"]
            assert decision["surface"] == "artifact"
            assert decision["purpose"] == "runtime_closeout_authority"
            assert decision["status"] == "blocked"
            assert decision["reason"] == "authority_surface_signal_missing"
            assert decision["blocking"] is True
            assert decision["integrity_status"] == "verified"
        else:
            assert content.status_code == 403, content.text
            assert content.json()["code"] == "artifact_tenant_unscoped"
    else:
        assert payload["status"] == "selected"
        assert payload["vector_ref"] == selection.method_metric_projection.vector_ref.model_dump(
            mode="json"
        )
        assert len(payload["observations"]) == 1
        surfaced_observation = payload["observations"][0]
        assert surfaced_observation["value"] == pytest.approx(1.0)
        assert surfaced_observation["law_id"] == METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID
        assert surfaced_observation["objective_id"] == "objective_ex_ante_mean_change"
        assert surfaced_observation["metric_unit_id"] == "value"
        # This is the existing test-built Core-owner scaffold. It witnesses the
        # authorized current GET and score replay, not a full engine execution.
        candidate_score = payload["candidate_score"]
        assert candidate_score["status"] == "selected"
        assert candidate_score["authority_status"] == "candidate_only"
        assert candidate_score["revalidation_required"] is True
        assert candidate_score["maximizing_coordinate"] == pytest.approx(1.0)
        assert candidate_score["candidate_ref"] == candidate_ref.model_dump(mode="json")

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        consumer_projection = read_completed_admitted_method_metric_projection(
            store,
            owner=service,
            source_run_id=run_id,
            candidate_ref=candidate_ref,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
    if capture_only:
        assert consumer_projection.status == "verification_missing"
        assert consumer_projection.basis is None
    else:
        assert consumer_projection.status == "selected"
        assert consumer_projection.basis is not None
        assert consumer_projection.basis.observations == (observation,)

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        resolved = service.resolve_completed_method_metric_selection(
            source_run_id=run_id,
            candidate_ref=candidate_ref,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
    if capture_only:
        # The completion resolver requires an owner-selected, verified AD01
        # projection and its candidate ref; capture-only rows have neither.
        assert resolved is None
    else:
        assert resolved is not None
        assert resolved.selection == selection

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        service._control_store.mark_running(
            job_id=job_id,
            worker_id="e02-public-execute-revocation-probe",
            lease_seconds=120,
        )
        revoked = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}/method-metrics")
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["status"] == "verification_missing"
    assert revoked.json()["candidate_score"] is None
    assert revoked.json()["vector_ref"] is None
    assert revoked.json()["observations"] == []
    assert revoked.json()["limitations"] == ["current_method_execution_selection_not_established"]
    if capture_only:
        assert MethodRegistry.get_instance().get_signature(producer["method_fqn"]) is not None


def _post_v2_hte_alpha_selection(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    *,
    method_fqn: str,
    request_alpha: float = 0.07,
    method_params: dict[str, object] | None = None,
) -> tuple[Any, list[dict[str, Any]], Any]:
    """Post one selected HTE request and retain the exact queued owner payload."""
    service = runtime_api_env["app"].state._control_service
    queued: list[dict[str, Any]] = []
    monkeypatch.setattr(service, "_enqueue_job", lambda **kwargs: queued.append(kwargs))
    method: dict[str, object] = {"fqn": method_fqn}
    if method_params is not None:
        method["params"] = method_params
    from polisyos.core.security.tenant_context import tenant_scope

    # Produce the candidate under the owner that the request fixture actually uses.
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        source_ref = _put_runtime_observational_source(service)
    payload = {
        "observational_input": {
            "protocol": "method_input_envelope_v1",
            "source_ref": source_ref.model_dump(mode="json"),
            "method": method,
            "hte_request": {
                "schema_version": "polisyos.runtime.observational_hte_request.v2",
                "estimand": "mean_effect_over_selected_x",
                "target_scope": "selected_evaluation_rows",
                "outcome_variable_id": "outcome.effect",
                "treatment_variable_id": "treatment.policy",
                "control_value": 0.0,
                "treated_value": 1.0,
                "requested_guarantee": "candidate_point",
                "alpha": request_alpha,
            },
        },
    }
    # HTTPX's `json=` rejects non-finite floats before the request reaches the API.
    # Raw JSON bytes exercise the real authorization/canonicalization boundary.
    response = _post_runtime_api_as_fixture_owner(
        runtime_api_env,
        "/api/v1/control/runs",
        content=json.dumps(payload, allow_nan=True, separators=(",", ":")),
        headers={"content-type": "application/json"},
    )
    return response, queued, service


def _read_v2_hte_alpha_intent(
    runtime_api_env: dict[str, Any],
    service: Any,
    response: Any,
) -> tuple[ArtifactRef, ObservationalRunIntent]:
    """Read the accepted intent under the exact tenant/cell fixture owner."""
    from polisyos.core.security.tenant_context import tenant_scope

    intent_ref = ArtifactRef.model_validate(response.json()["observational_run_intent_ref"])
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        intent = ObservationalRunIntent.model_validate(
            service._read_bounded_intent_artifact(intent_ref)
        )
    return intent_ref, intent


@pytest.mark.parametrize(
    ("method_fqn", "factory_alpha"),
    [
        ("causal.hte.causal_forest@2.0.0", 0.1),
        ("causal.hte.double_ml@2.0.0", 0.05),
        ("causal.hte.meta_learner@2.0.0", 0.05),
        ("causal.hte.forest_dr@2.0.0", 0.05),
    ],
)
def test_v2_hte_request_alpha_replaces_only_omitted_method_default(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    method_fqn: str,
    factory_alpha: float,
) -> None:
    """Freeze request alpha into the selected signature's effective params."""
    response, queued, service = _post_v2_hte_alpha_selection(
        runtime_api_env,
        monkeypatch,
        method_fqn=method_fqn,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "accepted"
    assert len(queued) == 1
    registration = service._observational_method_registrations[method_fqn]
    signature_alpha = next(
        spec.default for spec in registration.signature.parameters if spec.name == "alpha"
    )
    assert signature_alpha == factory_alpha
    intent_ref, intent = _read_v2_hte_alpha_intent(runtime_api_env, service, response)
    assert intent.submitted_params_present is False
    assert intent.submitted_params == {}
    assert intent.resolved_params["alpha"] == 0.07
    assert intent.resolved_params["alpha"] != factory_alpha
    if method_fqn == "causal.hte.meta_learner@2.0.0":
        # Tuple defaults cross the typed intent boundary in their JSON array form.
        assert intent.resolved_params["base_model_candidates"] == []
    assert intent.owned_hte_request_context is not None
    assert intent.owned_hte_request_context.requested_alpha == 0.07
    assert intent.resource_policy.method_fqn == method_fqn
    assert intent.resource_policy_digest == intent.resource_policy.digest()
    assert response.json()["observational_selection_digest"] == intent.selection_digest()
    marker = queued[0]["payload"]["observational_method_execution"]
    assert ArtifactRef.model_validate(marker["observational_run_intent_ref"]) == intent_ref
    assert marker["observational_selection_digest"] == intent.selection_digest()


def test_v2_hte_request_alpha_accepts_matching_explicit_method_alpha(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preserve explicit caller input when it agrees with immutable request intent."""
    response, queued, service = _post_v2_hte_alpha_selection(
        runtime_api_env,
        monkeypatch,
        method_fqn="causal.hte.causal_forest@2.0.0",
        method_params={"alpha": 0.07},
    )

    assert response.status_code == 200, response.text
    assert len(queued) == 1
    _intent_ref, intent = _read_v2_hte_alpha_intent(runtime_api_env, service, response)
    assert intent.submitted_params_present is True
    assert intent.submitted_params == {"alpha": 0.07}
    assert intent.resolved_params["alpha"] == 0.07
    assert intent.owned_hte_request_context is not None
    assert intent.owned_hte_request_context.requested_alpha == 0.07


def test_v2_hte_request_alpha_refuses_conflicting_explicit_method_alpha(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not silently rewrite a submitted method alpha that conflicts with the request."""
    response, queued, _service = _post_v2_hte_alpha_selection(
        runtime_api_env,
        monkeypatch,
        method_fqn="causal.hte.causal_forest@2.0.0",
        method_params={"alpha": 0.05},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "observational_hte_method_alpha_conflict"
    assert queued == []


@pytest.mark.parametrize("malformed_alpha", ["0.07", float("nan"), float("inf")])
def test_v2_hte_request_alpha_does_not_treat_malformed_explicit_as_omitted(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    malformed_alpha: object,
) -> None:
    """Malformed or non-finite explicit values remain a typed refusal."""
    response, queued, _service = _post_v2_hte_alpha_selection(
        runtime_api_env,
        monkeypatch,
        method_fqn="causal.hte.causal_forest@2.0.0",
        method_params={"alpha": malformed_alpha},
    )

    if type(malformed_alpha) is float:
        # NaN/Infinity are not JSON numbers; the real auth body canonicalizer
        # refuses them before typed method-parameter resolution.
        assert response.status_code == 400, response.text
        assert response.json()["code"] == "authorization_binding_body_invalid"
    else:
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "observational_method_parameters_invalid"
    assert queued == []


@pytest.mark.parametrize(
    ("policy_change", "invalid_value"),
    [
        ("max_jobs", 2),
        ("method_profile_id", "econml.dml.point_only@2.0"),
        ("execution_scope", "estimator_n_jobs_one"),
        ("required_estimator_n_jobs", 1),
    ],
)
def test_meta_learner_v2_resource_profile_rejects_policy_drift(
    runtime_api_env: dict[str, Any],
    policy_change: str,
    invalid_value: object,
) -> None:
    """Keep producer scope and profile pins load-bearing without a foreign knob."""
    service = runtime_api_env["app"].state._control_service
    registration = service._resolve_observational_method_registration(
        fqn="causal.hte.meta_learner@2.0.0",
        version=None,
    )
    parameter_names = {item.name for item in registration.signature.parameters}
    assert "bootstrap_n_jobs" not in parameter_names
    assert "n_jobs" not in parameter_names
    assert registration.n_jobs_parameter is None

    policy = service._resource_policy_for_registration(registration)
    assert policy.method_fqn == "causal.hte.meta_learner@2.0.0"
    assert policy.method_profile_id == "econml.meta_learner.point_only@2.0"
    assert policy.execution_scope == "producer_scoped_joblib_parallelism_one"
    assert policy.required_estimator_n_jobs is None
    assert policy.max_jobs == 1
    service._require_observational_method_resource_profile(registration, {}, resource_policy=policy)

    corrupted_policy = policy.model_copy(update={policy_change: invalid_value})
    with pytest.raises(ValueError, match="observational_method_resource_profile_not_supported"):
        service._require_observational_method_resource_profile(
            registration, {}, resource_policy=corrupted_policy
        )


@pytest.mark.parametrize("undeclared_knob", ["bootstrap_n_jobs", "n_jobs"])
def test_meta_learner_v2_refuses_unexposed_parallelism_knobs_before_enqueue(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    undeclared_knob: str,
) -> None:
    """Do not accept a stale or unexposed estimator-parallelism input."""
    response, queued, _service = _post_v2_hte_alpha_selection(
        runtime_api_env,
        monkeypatch,
        method_fqn="causal.hte.meta_learner@2.0.0",
        method_params={undeclared_knob: 1},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "observational_method_parameters_invalid"
    assert queued == []


def _exercise_two_real_completed_ex_ante_sources_and_fresh_planner(
    runtime_api_env: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """Real Runtime/Scientist/Foundry path; input fixture does not execute or finalize."""
    from _helpers.completed_ex_ante_runtime import (
        launch_completed_ex_ante_source,
        reconcile_observed_method_occurrence,
    )
    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
    from unit.scientist.nodes.builtins.decide.test_policy_runtime_method_metrics import (
        _exercise_public_execute_method_metric_source,
    )

    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.contracts.control import WorkflowRunRequest
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.execution_policy import RuntimePrincipal
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    service = runtime_api_env["app"].state._control_service
    stop_embedded_control_worker(service)
    store = service._artifact_store
    tenant_id, cell_id = runtime_api_env["tenant_a"], runtime_api_env["cell_a"]
    from polisyos.runtime.http.security import build_fixture_identity_claims

    claims = build_fixture_identity_claims()
    principal = RuntimePrincipal.from_user_claims(claims)
    assert principal.authenticated and principal.fixture_identity
    assert (principal.tenant_id, principal.cell_id) == (tenant_id, cell_id)
    sources = []
    source_job_ids = []
    prepared_sources = []
    for name, scenario in (("a", (11.0, 18.0, 44.0)), ("b", (12.0, 20.0, 44.0))):
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            prepared = _exercise_public_execute_method_metric_source(
                tmp_path / name,
                monkeypatch,
                artifact_store=store,
                scenario_values=scenario,
                prepare_only=True,
            )
        completed = launch_completed_ex_ante_source(service, prepared, principal)
        launch = completed["launch"]
        sources.append({"source_run_id": launch.run_id, "candidate_ref": prepared["candidate_ref"]})
        source_job_ids.append(launch.job_id)
        prepared_sources.append(prepared)

    # Deliberately relabel B's source with A's candidate; the real Runtime owner
    # must not admit this as a score for A.
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        assert (
            service.resolve_completed_method_metric_selection(
                source_run_id=sources[1]["source_run_id"],
                candidate_ref=sources[0]["candidate_ref"],
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            is None
        )
        assert (
            service.resolve_completed_method_metric_selection(
                source_run_id=sources[0]["source_run_id"],
                candidate_ref=sources[0]["candidate_ref"],
                tenant_id=tenant_id,
                cell_id="different-cell",
            )
            is None
        )

    first = prepared_sources[0]
    planner_request = WorkflowRunRequest(
        data_source={"data_snapshot_ref": first["data_snapshot_ref"].model_dump(mode="json")},
        trinity_bundle_ref=first["trinity_ref"],
        registry_bundle_ref=first["registry_ref"],
        params={
            "control_plane_transition": "legacy_shadow",
            "workflow_id": "scientist_policy_design",
            "policy_candidate_schema": first["candidate"].model_dump(mode="json"),
            "policy_search_completed_ex_ante_comparison": {
                "sources": [
                    {
                        "source_run_id": source["source_run_id"],
                        "candidate_ref": source["candidate_ref"].model_dump(mode="json"),
                    }
                    for source in sources
                ]
            },
        },
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        planner = service.launch_workflow_run(planner_request, principal=principal)
    assert (
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=planner.job_id,
        )
        == planner.job_id
    )
    planner_job = service._control_store.get_job(planner.job_id)
    assert planner_job is not None and planner_job.state == "completed", planner_job
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        state_ref = service._legacy_scientist_final_state_ref(job=planner_job)
        assert state_ref is not None
        state = validate_core_model_json_artifact(ExperimentState, store, state_ref)
    comparison = state.params["policy_search_result"]["completed_ex_ante_candidate_comparison"]
    assert comparison["status"] == "complete", comparison
    assert comparison["authority_status"] == "candidate_only"
    assert comparison["revalidation_required"] is True
    assert [row["maximizing_coordinate"] for row in comparison["observations"]] == pytest.approx(
        [1.0, 2.0]
    )
    assert comparison["frontier_candidate_hashes"] == [
        prepared_sources[1]["candidate"].candidate_hash()
    ]

    runtime_context = getattr(runtime_api_env["app"].state, "runtime_api_ctx", None)
    if runtime_context is None:
        runtime_context = runtime_api_env["app"].state.runtime_container.runtime_api_context
    runtime_context.run_index.refresh(force=True)
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        fresh = runtime_api_env["client"].get(
            f"/api/v1/runs/{planner.run_id}/method-metric-comparison"
        )
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["candidate_comparison"]["status"] == "complete"
    assert fresh.json()["candidate_comparison"]["frontier_candidate_hashes"] == [
        prepared_sources[1]["candidate"].candidate_hash()
    ]

    # Independent oracle and source-custody checks over the two real completed
    # jobs.  The expected means use the explicit integer paired differences:
    # A: (1 - 2 + 4) / 3 = 1; B: (2 + 0 + 4) / 3 = 2.
    from polisyos.core.contracts.foundry import MethodExecutionBundle
    from polisyos.scientist.nodes.builtins.decide import policy_runtime_method_metrics

    assert len(set(source_job_ids)) == len({source["source_run_id"] for source in sources}) == 2
    assert sources[0]["candidate_ref"] != sources[1]["candidate_ref"]
    expected_values = (1.0, 2.0)
    scores = []
    observed_sources = []
    dispatch_profiles = []
    environment_plan_refs = []
    for index, expected in enumerate(expected_values):
        source = sources[index]
        job = service._control_store.get_job(source_job_ids[index])
        assert job is not None and job.state == "completed"
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            selected = service.get_method_execution_selection(
                run_id=source["source_run_id"], tenant_id=tenant_id, cell_id=cell_id
            )
            score = service.read_current_completed_ex_ante_candidate_score(
                run_id=source["source_run_id"], tenant_id=tenant_id, cell_id=cell_id
            )
            projection = service.read_current_admitted_method_metric_projection(
                run_id=source["source_run_id"], tenant_id=tenant_id, cell_id=cell_id
            )
            assert isinstance(selected, GraphMethodExecutionSelection)
            bundle = validate_core_model_json_artifact(
                MethodExecutionBundle, store, selected.method_execution_bundle_ref
            )
            environment_ref = bundle.environment_manifest_ref
            assert environment_ref is not None
            environment_manifest = store.get_manifest(environment_ref)
            environment_payload = json.loads(store.get_bytes(environment_ref))
            plan_edges = [edge for edge in environment_manifest.inputs if edge.role == "exec_plan"]
            assert len(plan_edges) == 1
            assert plan_edges[0].artifact_id == bundle.exec_plan_ref.artifact_id
            assert (
                plan_edges[0].manifest_profile_sha256
                == bundle.exec_plan_ref.manifest_profile_sha256
            )
            assert environment_payload["custom_metadata"]["exec_plan_id"] == str(
                bundle.exec_plan_ref.artifact_id
            )
            environment_plan_refs.append(bundle.exec_plan_ref.model_dump(mode="json"))
        assert selected.job_id == source_job_ids[index]
        assert selected.run_id == source["source_run_id"] and selected.attempt == job.attempt
        assert selected.metric_verification_status == "verified"
        assert selected.source_candidate_ref == source["candidate_ref"]
        assert selected.method_metric_projection is not None
        assert selected.method_metric_projection.verifier_revision == "1.0"
        verifier_bytes = Path(policy_runtime_method_metrics.__file__).read_bytes()
        verifier_digest = "sha256:" + hashlib.sha256(verifier_bytes).hexdigest()
        assert selected.method_metric_projection.verifier_implementation_sha256 == verifier_digest
        assert score.status == "selected" and score.authority_status == "candidate_only"
        assert score.revalidation_required is True
        assert score.candidate_ref == source["candidate_ref"]
        assert score.source_vector_ref == selected.method_metric_projection.vector_ref
        assert score.minimized_score == pytest.approx(-expected)
        assert score.maximizing_coordinate == pytest.approx(expected)
        assert projection.status == "selected" and len(projection.observations) == 1
        assert projection.vector_ref is not None
        assert projection.vector_ref.model_dump(mode="json") == score.source_vector_ref.model_dump(
            mode="json"
        )
        observation = projection.observations[0]
        assert observation.source_status == "observed"
        assert observation.objective_id == "objective_ex_ante_mean_change"
        assert observation.metric_id == "metric_ex_ante_mean_change"
        assert observation.value == pytest.approx(expected)
        assert observation.input_capture_ref is not None
        assert observation.environment_manifest_ref is not None
        assert observation.verifier_code_digest == verifier_digest
        assert bundle.environment_manifest_ref is not None
        occurrence = reconcile_observed_method_occurrence(
            store, bundle, occurrence_id=observation.occurrence_id
        )
        assert occurrence.node_id == "ex_ante_node" and occurrence.status == "succeeded"
        assert occurrence.method_fqn == "policy.evaluation.ex_ante_simulation@1.0.0"
        assert occurrence.method_version == "1.0.0"
        assert occurrence.method_build_digest_scope == "class_source_only"
        assert occurrence.method_build_digest is not None
        dispatch = occurrence.dispatch
        assert dispatch is not None and dispatch.outcome == "succeeded"
        assert dispatch.method_metric_input_capture_status == "captured"
        assert dispatch.parameter_resolution_status == "captured"
        assert [(p.name, p.status, p.value) for p in dispatch.parameter_values] == [
            ("poverty_line", "captured", None)
        ]
        assert set(dispatch.signature_input_slot_ids) == {"baseline", "scenario"}
        assert dispatch.seed_status == "reconciled"
        assert dispatch.backend_identity_status == "reconciled"
        assert dispatch.backend_trace_status == "captured"
        assert dispatch.fallback_status == "not_fell_back"
        assert dispatch.selected_backend == dispatch.actual_backend == "numpy"
        scores.append(score)
        observed_sources.append(
            {
                "source_run_id": source["source_run_id"],
                "selection": selected.model_dump(mode="json"),
                "candidate_score": score.model_dump(mode="json"),
                "observation": observation.model_dump(mode="json"),
                "dispatch": dispatch.model_dump(mode="json"),
                "environment_ref": bundle.environment_manifest_ref.model_dump(mode="json"),
            }
        )
        dispatch_profiles.append(
            (
                dispatch.root_seed,
                dispatch.step,
                dispatch.method_key_words,
                dispatch.method_seed,
                dispatch.reproducibility_seed,
                dispatch.requested_backend,
                dispatch.selected_backend,
                dispatch.actual_backend,
                tuple(p.model_dump_json() for p in dispatch.parameter_values),
            )
        )
    assert environment_plan_refs[0] != environment_plan_refs[1]
    assert dispatch_profiles[0] == dispatch_profiles[1]
    assert scores[0].comparison_contract_sha256 == scores[1].comparison_contract_sha256
    assert scores[0].comparison_contract_sha256 is not None
    expected_sources = [
        {
            "source_run_id": source["source_run_id"],
            "candidate_ref": source["candidate_ref"].model_dump(mode="json"),
        }
        for source in sources
    ]
    expected_hashes = [prepared["candidate"].candidate_hash() for prepared in prepared_sources]
    for current_comparison in (comparison, fresh.json()["candidate_comparison"]):
        assert current_comparison["status"] == "complete"
        assert current_comparison["authority_status"] == "candidate_only"
        assert current_comparison["revalidation_required"] is True
        assert (
            current_comparison["comparison_contract_sha256"] == scores[0].comparison_contract_sha256
        )
        assert [row["source"] for row in current_comparison["observations"]] == expected_sources
        assert [
            row["candidate_hash"] for row in current_comparison["observations"]
        ] == expected_hashes
        assert [
            row["minimized_score"] for row in current_comparison["observations"]
        ] == pytest.approx([-1.0, -2.0])
        assert [
            row["maximizing_coordinate"] for row in current_comparison["observations"]
        ] == pytest.approx([1.0, 2.0])
        assert current_comparison["frontier_candidate_hashes"] == [expected_hashes[1]]

    # This test-local index helps locate retained real CAS/owner records. It is
    # diagnostic data, not an issuer or substitute for reopening those records.
    observed = {
        "schema": "c48.real_completed_sources_pilot.observed.v1",
        "identity": {
            "subject": principal.subject,
            "tenant_id": tenant_id,
            "cell_id": cell_id,
            "roles": sorted(principal.roles),
            "fixture_identity": principal.fixture_identity,
        },
        "sources": observed_sources,
        "planner_run_id": planner.run_id,
        "planner_job_id": planner.job_id,
        "planner_final_state_ref": state_ref.model_dump(mode="json"),
        "fresh_comparison": fresh.json()["candidate_comparison"],
    }
    (tmp_path / "c48-pilot-observed.json").write_text(json.dumps(observed, indent=2) + "\n")

    return {
        "service": service,
        "store": store,
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "principal": principal,
        "source_job_ids": source_job_ids,
        "planner_request": planner_request,
        "planner": planner,
    }


@pytest.fixture
def c48_isolated_runtime_api_env(tmp_path: Path):
    """Use only the existing test-owned selected Catalog and synthetic owner roots."""
    from _helpers.runtime_http import build_runtime_api_env, close_runtime_api_env
    from unit.runtime.quality.test_catalog_source_identity import _selected_fixture

    from polisyos.runtime.quality.substrate_registry import CatalogServingSourceSelection

    code_root, owner_root, selected = _selected_fixture(tmp_path / "c48-catalog")
    selection = CatalogServingSourceSelection(
        snapshot_root=selected.snapshot_root,
        source_owner_root=owner_root,
        database_relative_path=selected.database_relative_path,
        catalog_run_profile="prod_full",
    )
    env = build_runtime_api_env(
        tmp_path / "c48-runtime",
        include_test_client=True,
        app_kwargs={"repo_root": code_root, "catalog_source_selection": selection},
    )
    try:
        service = env["app"].state._control_service
        source = service._catalog_serving_source
        assert source.selection_basis == "explicit_path_candidate_only"
        assert source.repo_root == code_root.resolve()
        assert source.source_owner_root == owner_root.resolve()
        assert source.snapshot_root == selected.snapshot_root
        assert source.database_path == selected.database_path
        assert source.substrate_paths.production_root.is_relative_to(owner_root.resolve())
        yield env
    finally:
        close_runtime_api_env(env)


def test_two_real_completed_ex_ante_sources_produce_fresh_candidate_comparison(
    c48_isolated_runtime_api_env: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run only two source workflows and one separate real planner plus fresh GET."""
    _exercise_two_real_completed_ex_ante_sources_and_fresh_planner(
        c48_isolated_runtime_api_env, tmp_path, monkeypatch
    )


def test_two_real_completed_ex_ante_sources_are_reselected_by_fresh_planner(
    c48_isolated_runtime_api_env: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retain the original post-search and later fresh-GET revocation witness."""
    runtime_api_env = c48_isolated_runtime_api_env
    from _helpers.control_worker import dispatch_one_control_job

    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    completed = _exercise_two_real_completed_ex_ante_sources_and_fresh_planner(
        runtime_api_env, tmp_path, monkeypatch
    )
    service = completed["service"]
    store = completed["store"]
    tenant_id = completed["tenant_id"]
    cell_id = completed["cell_id"]
    principal = completed["principal"]
    source_job_ids = completed["source_job_ids"]
    planner_request = completed["planner_request"]
    planner = completed["planner"]
    # Revoke the real source while a second actual planner executes; do not
    # replace its search or result with a fake. The post-search emission must
    # reselect rather than keeping a pre-search complete comparison.
    from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
        HierarchicalPolicySearchAdapter,
    )

    original_run_search = HierarchicalPolicySearchAdapter.run_search
    revoked_during_search = []

    def revoke_then_run(adapter, *args, **kwargs):
        service._control_store.mark_running(
            job_id=source_job_ids[0], worker_id="candidate-comparison-revocation", lease_seconds=120
        )
        revoked_during_search.append(True)
        return original_run_search(adapter, *args, **kwargs)

    monkeypatch.setattr(HierarchicalPolicySearchAdapter, "run_search", revoke_then_run)
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        second_planner = service.launch_workflow_run(planner_request, principal=principal)
    assert (
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=second_planner.job_id,
        )
        == second_planner.job_id
    )
    second_job = service._control_store.get_job(second_planner.job_id)
    assert revoked_during_search == [True]
    assert second_job is not None and second_job.state == "completed", second_job
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        second_ref = service._legacy_scientist_final_state_ref(job=second_job)
        assert second_ref is not None
        second_state = validate_core_model_json_artifact(ExperimentState, store, second_ref)
        second_comparison = second_state.params["policy_search_result"][
            "completed_ex_ante_candidate_comparison"
        ]
        revoked = runtime_api_env["client"].get(
            f"/api/v1/runs/{planner.run_id}/method-metric-comparison"
        )
    assert second_comparison["status"] == "verification_missing"
    assert second_comparison["frontier_candidate_hashes"] == []
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["candidate_comparison"]["status"] == "verification_missing"
    assert revoked.json()["candidate_comparison"]["frontier_candidate_hashes"] == []


_R4_JOB_SNAPSHOT_ROW_CAP = 1024


def _r4_json_value(value: Any) -> Any:
    """Convert persisted rows and typed refs to bounded JSON values."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    raise TypeError(f"unsupported R4 evidence value: {type(value).__name__}")


def _r4_snapshot(reader: Any, job_id: str) -> dict[str, Any]:
    """Read one complete SQLite job row plus its event and outbox rows."""
    db_path = Path(reader._sqlite_path).resolve()
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")
        job = conn.execute(
            "SELECT * FROM control_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        progress = conn.execute(
            "SELECT * FROM control_job_progress WHERE job_id = ? ORDER BY job_id LIMIT ?",
            (job_id, _R4_JOB_SNAPSHOT_ROW_CAP + 1),
        ).fetchall()
        events = conn.execute(
            "SELECT * FROM control_job_events WHERE job_id = ? ORDER BY event_id LIMIT ?",
            (job_id, _R4_JOB_SNAPSHOT_ROW_CAP + 1),
        ).fetchall()
        outbox = conn.execute(
            "SELECT * FROM control_outbox_events WHERE job_id = ? ORDER BY event_id LIMIT ?",
            (job_id, _R4_JOB_SNAPSHOT_ROW_CAP + 1),
        ).fetchall()
    if any(len(rows) > _R4_JOB_SNAPSHOT_ROW_CAP for rows in (progress, events, outbox)):
        raise RuntimeError("r4_job_snapshot_row_cap_exceeded")
    return {
        "job_row": None if job is None else dict(job),
        "progress": [dict(row) for row in progress],
        "events": [dict(row) for row in events],
        "outbox": [dict(row) for row in outbox],
    }


def _r4_snapshot_hash(snapshot: dict[str, Any]) -> str:
    """Hash the exact agreed snapshot JSON encoding."""
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _r4_response_body(response: Any) -> tuple[Any, str]:
    """Preserve decoded JSON when possible and exact response text in all cases."""
    try:
        return response.json(), response.text
    except ValueError:
        return {"non_json": response.text}, response.text


def _r4_run_selection(response_body: Any) -> Any:
    """Extract, without inventing a value, the public selected-run projection."""
    try:
        return response_body["run"]["method_execution_selection"]
    except (KeyError, TypeError):
        return None


def _r4_module_readset() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Hash only actually loaded modules in the named numerical backend families."""
    python_rows: list[dict[str, Any]] = []
    native_rows: list[dict[str, Any]] = []
    families = (
        "econml",
        "sklearn",
        "numpy",
        "scipy",
        "joblib",
        "threadpoolctl",
        "numba",
        "lightgbm",
    )
    native_suffixes = (*importlib.machinery.EXTENSION_SUFFIXES, ".dylib", ".so")
    for name, module in sorted(sys.modules.items()):
        if not any(name == family or name.startswith(family + ".") for family in families):
            continue
        origin = getattr(getattr(module, "__spec__", None), "origin", None)
        if not isinstance(origin, str):
            continue
        path = Path(origin).resolve()
        is_native = str(path).endswith(native_suffixes)
        if not is_native and path.suffix != ".py" and not path.name.endswith(".pyc"):
            continue
        try:
            digest = hashlib.sha256()
            count = 0
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    count += len(block)
                    digest.update(block)
            row = {
                "name": name,
                "origin": str(path),
                "sha256": digest.hexdigest(),
                "bytes": count,
            }
        except OSError as exc:
            row = {
                "name": name,
                "origin": str(path),
                "sha256": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        (native_rows if is_native else python_rows).append(row)
    return python_rows, native_rows


def _r4_mach_nested_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """Keep raw Mach return codes/times and a recomputable CPU total."""
    return {
        "monotonic_ns": sample.get("monotonic_ns"),
        "return_code": sample.get("return_code"),
        "returned_count": sample.get("returned_count"),
        "user_time": {
            "seconds": sample.get("user_time_seconds"),
            "microseconds": sample.get("user_time_microseconds"),
        },
        "system_time": {
            "seconds": sample.get("system_time_seconds"),
            "microseconds": sample.get("system_time_microseconds"),
        },
        "thread_cpu_microseconds": sample.get("thread_cpu_microseconds"),
        "struct_size_bytes": sample.get("struct_size_bytes"),
        "error": sample.get("error"),
    }


def _r4_native_inflight_classification(record: dict[str, Any]) -> str:
    """Classify only from native origins, paired fit events, and persisted timings."""
    native = record.get("native", {})
    cancel = record.get("cancel", {})
    executor = record.get("executor", {})
    worker = executor.get("occupied_worker", {})
    events = native.get("grf_tree_fit_events", [])
    entries = [event for event in events if event.get("kind") == "fit_enter"]
    returns = [
        event
        for event in events
        if event.get("kind") == "fit_return" and event.get("success") is True
    ]
    started = cancel.get("post_start_ns")
    ended = cancel.get("post_end_ns")
    if type(started) is not int or type(ended) is not int or not events:
        return "INCONCLUSIVE"
    paired_spans = any(
        entry.get("fit_call_id") == returned.get("fit_call_id")
        and entry.get("tree_identity") == returned.get("tree_identity")
        and entry.get("pid") == worker.get("pid")
        and entry.get("thread_id") == worker.get("thread_id")
        and entry.get("native_thread_id") == worker.get("native_thread_id")
        and entry.get("monotonic_ns", 0) < started
        and returned.get("monotonic_ns", 0) > ended
        for entry in entries
        for returned in returns
    )
    before_return = any(event.get("monotonic_ns", 0) < started for event in returns)
    after_return = any(event.get("monotonic_ns", 0) > ended for event in returns)
    outer_returns = [
        event
        for event in native.get("forest_dr_fit_events", [])
        if event.get("kind") == "fit_return" and event.get("success") is True
    ]
    readback_at = cancel.get("fresh_sqlite_readback", {}).get("monotonic_ns")
    outer_after_readback = any(
        event.get("monotonic_ns", 0) > (readback_at or 0) for event in outer_returns
    )
    native_bound = bool(native.get("loaded_native_modules")) and bool(
        native.get("fit_original", {}).get("source_sha256")
    )
    if not (
        native_bound
        and paired_spans
        and before_return
        and after_return
        and cancel.get("future_unfinished_at_response") is True
        and outer_after_readback
    ):
        return "INCONCLUSIVE"
    bracket = cancel.get("worker_cpu_bracket", {})
    delta = bracket.get("thread_cpu_delta_microseconds")
    if bracket.get("available") is True and type(delta) is int and delta > 0:
        return "PASS"
    return "BOUNDED_NATIVE_IN_FLIGHT"


def _r4_durable_cancel_signature(record: dict[str, Any]) -> tuple[Any, ...]:
    """Recompute durable cancellation from persisted rows, independent of native facts."""
    snapshot = record.get("final", {}).get("snapshot", {})
    job = snapshot.get("job_row") or {}
    events = snapshot.get("events", [])
    outbox = snapshot.get("outbox", [])
    return (
        job.get("state"),
        sum(row.get("event_type") == "job_cancelled" for row in events),
        sum(row.get("topic") == "control.job.cancelled" for row in outbox),
        sum(row.get("event_type") in {"job_completed", "job_failed"} for row in events),
        job.get("method_execution_selection_json"),
    )


def test_real_forest_fit_progress_spans_durable_cancel_post(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Observe real served ForestDR native work across an authorized cancel POST."""
    import pytest

    case_id = "policyos.e02.r4.native_forest_fit_cancel.v1"
    nodeid = (
        "tests/unit/runtime/http/test_observational_method_runtime.py::"
        "test_real_forest_fit_progress_spans_durable_cancel_post"
    )
    evidence_root_raw = os.environ.get("POLISYOS_C96_EVIDENCE_DIR", "")
    evidence_root = Path(evidence_root_raw).expanduser().resolve() if evidence_root_raw else None
    native_dir = evidence_root / "native" if evidence_root is not None else tmp_path / "native"
    native_dir.mkdir(parents=True, exist_ok=True)
    observation_path = native_dir / "fixture-observation.json"
    observation: dict[str, Any] = {
        "schema": case_id,
        "case": {
            "test_nodeid": nodeid,
            "stage": "starting",
            "verdict": {
                "backend_load": "UNRUN",
                "method_execution": "UNRUN",
                "durable_cancel": "UNRUN",
                "bounded_native_in_flight": "UNRUN",
                "native_activity": "UNRUN",
            },
        },
        "process": {
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "executable": sys.executable,
            "argv": list(sys.argv),
            "source": {
                "head": os.environ.get("POLISYOS_C96_EXPECTED_HEAD", ""),
                "tree": os.environ.get("POLISYOS_C96_EXPECTED_TREE", ""),
                "test_path": Path(__file__)
                .resolve()
                .relative_to(Path(__file__).resolve().parents[5])
                .as_posix(),
                "test_sha256": hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest(),
                "loaded_python_readset_path": str(native_dir / "loaded-python-readset.json"),
                "loaded_python_readset_sha256": "",
            },
        },
        "sqlite": {"database_path": "", "path_is_under_case_sandbox": False},
        "input": {
            "source_ref": {},
            "cas_root": "",
            "payload_path": "",
            "payload_file_bytes": 0,
            "payload_file_sha256": "",
            "manifest_path": "",
            "manifest_sha256": "",
            "manifest_profile_sha256": "",
            "source_kind": "ir.observation_method_input",
            "rows": 2000,
            "source_authority": "fixture_synthetic_candidate",
            "sample_ids_unique": False,
        },
        "method": {
            "requested_fqn": "causal.hte.forest_dr@1.1.0",
            "effective_fqn": "",
            "effective_params": {},
            "resource_policy_ref": {},
            "resource_policy_digest": "",
            "admission_binding_status": "",
            "dispatch_binding_status": "",
            "job_id": "",
            "run_id": "",
            "attempt": 0,
            "lease_owner": "",
            "lease_expires_at": "",
            "intent_cas": {},
            "launch": {},
            "observational_run_intent_artifact": {},
            "work_descriptor": {
                "job_id": "",
                "run_id": "",
                "attempt": 0,
                "requested_source_ref": {},
                "observational_run_intent_ref": {},
            },
        },
        "executor": {
            "profile": {"capacity": 2, "queue_capacity": 2, "revision": ""},
            "object_type": "",
            "object_id": 0,
            "submit_owner": {},
            "occupied_worker": {
                "pid": 0,
                "thread_id": 0,
                "native_thread_id": 0,
                "thread_name": "",
                "is_current_shared_executor_worker": False,
                "mach_thread_port": None,
            },
            "nonnumeric_peer": {
                "mode": "event_wait",
                "numeric_work": False,
                "enter_ns": None,
                "release_ns": None,
                "exit_ns": None,
                "pid": None,
                "thread_id": None,
                "native_thread_id": None,
                "is_current_shared_executor_worker": False,
                "release_observed": None,
            },
            "shared_execution_handle": {
                "captured": False,
                "type": "",
                "future_id": 0,
                "done_at_post_end": None,
                "completion_status": "UNRUN",
                "typed_outcome": None,
            },
            "queue": {
                "follower_future_type": "",
                "follower_future_id": 0,
                "pending_when_fit_active": False,
                "overflow_error_code": "",
                "overflow_capacity": 0,
                "overflow_queue_capacity": 0,
                "overflow_queue_depth": 0,
                "body_entered_before_fit_return": False,
                "full_observed_ns": None,
                "physical_workers": None,
                "queued_jobs": None,
                "outstanding_jobs": None,
                "follower_events": [],
            },
        },
        "native": {
            "econml_version": "",
            "econml_module_origin": "",
            "econml_module_sha256": "",
            "forest_dr_class": "econml.dr.ForestDRLearner",
            "forest_dr_module_origin": "",
            "forest_dr_module_sha256": "",
            "grftree_class": "econml.grf._base_grftree.GRFTree",
            "forest_dr_defining_class": "",
            "forest_dr_public_import_alias": "econml.dr.ForestDRLearner",
            "grftree_module_origin": "",
            "grftree_module_sha256": "",
            "loaded_native_modules": [],
            "fit_original": {},
            "forest_dr_fit_original": {},
            "forest_dr_fit_events": [],
            "grf_tree_fit_events": [],
        },
        "lease": {"initial_readback": {}, "renewals": []},
        "negatives": [],
        "cancel": {
            "current_authority_at_entry": False,
            "authorized": False,
            "post_start_ns": 0,
            "post_end_ns": 0,
            "actual_store_cancel_entry_ns": 0,
            "status_code": 0,
            "url": "",
            "request_url": "",
            "request_body": {},
            "body": {},
            "response_body": {},
            "request_wire_utf8": "",
            "response_text": "",
            "authority": {},
            "authorized_actor": "",
            "tenant_id": "",
            "cell_id": "",
            "actual_store_cancel_body_called_at_ns": 0,
            "worker_cpu_bracket": {
                "method": "mach_THREAD_BASIC_INFO",
                "available": False,
                "pid": 0,
                "thread_id": 0,
                "native_thread_id": 0,
                "mach_thread_port": None,
                "flavor": 3,
                "count": 10,
                "struct_size_bytes": 40,
                "resolution_microseconds": 1,
                "before": {},
                "after": {},
                "thread_cpu_delta_microseconds": None,
                "error": None,
            },
            "future_unfinished_at_response": None,
            "database_path": "",
            "fresh_sqlite_readback": {
                "monotonic_ns": 0,
                "snapshot": {},
                "snapshot_sha256": "",
                "verified_cancelled_record": False,
            },
            "fresh_http_get": {
                "method": "GET",
                "url": "",
                "request_url": "",
                "monotonic_ns": 0,
                "status_code": 0,
                "body": {},
                "response_text": "",
            },
            "fresh_run_get": {
                "method": "GET",
                "url": "",
                "request_url": "",
                "monotonic_ns": 0,
                "status_code": 0,
                "body": {},
                "response_text": "",
            },
            "retry": {
                "method": "POST",
                "url": "",
                "request_url": "",
                "monotonic_ns": 0,
                "status_code": 0,
                "request_body": {},
                "request_wire_utf8": "",
                "body": {},
                "response_text": "",
            },
            "selection_snapshot": None,
        },
        "result": {
            "fit_natural_return_ns": None,
            "method_work_return_ns": None,
            "handler_disposition": "",
            "handler_errors": [],
            "shared_execution_failure": None,
            "shared_execution_outcome": None,
            "candidate_outcome": None,
            "method_result_ref": None,
            "method_evidence_ref": None,
            "cas_readback_status": "not_observed",
            "selection_status": "withheld_or_absent",
            "selection_attempt": None,
            "fresh_get_status": None,
            "fresh_get_selection": None,
            "semantic_estimate_valid": False,
        },
        "final": {
            "fresh_sqlite_readback_monotonic_ns": 0,
            "database_path": "",
            "snapshot": {},
            "snapshot_sha256": "",
            "cancel_event_count": 0,
            "cancel_outbox_count": 0,
            "completed_or_failed_terminal_count": 0,
            "selection_status": "withheld_or_absent",
            "selection_attempt": None,
            "stale_write_refused": {
                "progress": False,
                "manifest": False,
                "terminal": False,
            },
            "stale_write_results": {
                key: {
                    "called": False,
                    "refused": False,
                    "exception_type": None,
                    "exception_message": None,
                    "body_entered": False,
                }
                for key in ("progress", "manifest", "terminal")
            },
            "queued_body_entered_after_fit_return": False,
            "queued_body_entered_after_peer_release": False,
        },
        "errors": [],
    }

    env: dict[str, Any] | None = None
    reader: Any = None
    client: Any = None
    client_lifespan_entered = False
    service: Any = None
    raw_store: Any = None
    worker: Any = None
    dispatch_thread: threading.Thread | None = None
    queue_future: Any = None
    queue_future2: Any = None
    peer_future: Any = None
    peer_started = threading.Event()
    peer_release = threading.Event()
    method_handle: Any = None
    test_started_monotonic = time.monotonic()
    observer: Any = None
    native_events: list[dict[str, Any]] = []
    sample_before: dict[str, Any] = {}
    sample_after: dict[str, Any] = {}
    renewals_lock = threading.Lock()
    control_calls: list[dict[str, Any]] = []
    worker_errors: list[dict[str, Any]] = []
    queued_body_returns: list[dict[str, int]] = []
    module_readset_cache: tuple[list[dict[str, Any]], list[dict[str, Any]]] | None = None
    source_ref: Any = None
    job_id = ""
    run_id = ""
    worker_id = "r4-native-control-worker"
    attempt = 0
    lease_owner = ""
    fit_return_event: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal module_readset_cache
        if observer is not None:
            while True:
                try:
                    native_events.append(observer.events.get_nowait())
                except Exception:
                    break
            worker_identity = observer.worker
            if isinstance(worker_identity, dict):
                observation["executor"]["occupied_worker"].update(
                    {
                        key: worker_identity.get(key)
                        for key in (
                            "pid",
                            "thread_id",
                            "native_thread_id",
                            "thread_name",
                            "is_current_shared_executor_worker",
                            "mach_thread_port",
                        )
                    }
                )
            observation["native"]["forest_dr_fit_events"] = [
                event
                for event in native_events
                if event.get("kind") in {"fit_enter", "fit_return"}
                and event.get("fit_layer") == "forest_dr"
            ]
            observation["native"]["grf_tree_fit_events"] = [
                event
                for event in native_events
                if event.get("kind") in {"fit_enter", "fit_return"}
                and event.get("fit_layer") == "grf_tree"
            ]
        try:
            if module_readset_cache is None:
                module_readset_cache = _r4_module_readset()
            python_modules, native_modules = module_readset_cache
            readset_path = Path(observation["process"]["source"]["loaded_python_readset_path"])
            readset_bytes = json.dumps(
                {
                    "pid": os.getpid(),
                    "scope": "loaded Python modules in econml/sklearn/numpy/scipy/joblib/threadpoolctl/numba/lightgbm families only",
                    "modules": python_modules,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            readset_path.write_bytes(readset_bytes)
            observation["process"]["source"]["loaded_python_readset_sha256"] = hashlib.sha256(
                readset_bytes
            ).hexdigest()
            observation["native"]["loaded_native_modules"] = native_modules
        except Exception as exc:
            observation["errors"].append(
                {
                    "stage": "module_readset",
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
            )
        if reader is not None:
            try:
                db_path = Path(reader._sqlite_path).resolve()
                observation["sqlite"]["database_path"] = str(db_path)
                observation["sqlite"]["path_is_under_case_sandbox"] = bool(
                    evidence_root is not None and db_path.is_relative_to(evidence_root)
                )
            except Exception as exc:
                observation["errors"].append(
                    {
                        "stage": "sqlite_path",
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
        try:
            observation_path.write_text(
                json.dumps(observation, sort_keys=True, indent=2, default=_r4_json_value) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            # The runner will preserve stdout/stderr if the case-owned filesystem itself failed.
            observation["errors"].append(
                {
                    "stage": "evidence_write",
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
            )

    def _release_peer() -> None:
        if not peer_release.is_set():
            observation["executor"]["nonnumeric_peer"]["release_ns"] = time.monotonic_ns()
            peer_release.set()

    @contextmanager
    def _draining_client(selected_client: Any) -> Any:
        """Keep the real app alive until its observed worker settles naturally."""
        with selected_client:
            try:
                yield
            finally:
                _release_peer()
                observation["teardown"] = {
                    "drain_started_ns": time.monotonic_ns(),
                    "outcome": "waiting",
                }
                # The reviewed outer supervisor starts before this test and
                # terminates the isolated process tree at its 600-second cap.
                # The later internal bound also protects an unsupervised run.
                end = test_started_monotonic + 600.0
                while True:
                    dispatch_alive = dispatch_thread is not None and dispatch_thread.is_alive()
                    method_busy = method_handle is not None and not method_handle.done()
                    queued_busy = any(
                        future is not None and not future.done()
                        for future in (queue_future, queue_future2)
                    )
                    peer_busy = peer_future is not None and not peer_future.done()
                    if not (dispatch_alive or method_busy or queued_busy or peer_busy):
                        _capture_completed_method_failure()
                        observation["result"]["handler_errors"] = list(worker_errors)
                        observation["teardown"].update(
                            {
                                "outcome": "naturally_settled",
                                "drain_finished_ns": time.monotonic_ns(),
                                "dispatch_alive": False,
                                "method_busy": False,
                                "queued_busy": False,
                                "peer_busy": False,
                            }
                        )
                        break
                    if time.monotonic() >= end:
                        observation["case"]["stage"] = "drain_timeout"
                        observation["errors"].append(
                            {
                                "stage": "client_drain",
                                "type": "TimeoutError",
                                "message": "active worker did not settle before isolated test deadline",
                            }
                        )
                        observation["teardown"].update(
                            {
                                "outcome": "ERROR_active_worker_at_deadline",
                                "drain_finished_ns": time.monotonic_ns(),
                                "dispatch_alive": dispatch_alive,
                                "method_busy": method_busy,
                                "queued_busy": queued_busy,
                                "peer_busy": peer_busy,
                            }
                        )
                        _save()
                        sys.stderr.write(
                            "R4 native witness: active worker did not settle within isolated bound\n"
                        )
                        sys.stderr.flush()
                        os._exit(124)
                    time.sleep(0.05)

    def _next_native_event(timeout_s: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_s
        while True:
            remaining = deadline - time.monotonic()
            if dispatch_done.is_set() and method_handle is None:
                observation["result"]["handler_errors"] = list(worker_errors)
                observation["result"]["handler_disposition"] = "dispatch_returned_without_handle"
                _skip_with_partial(
                    "dispatch_finished_without_method",
                    "dispatch ended before a method handle was captured; native witness is unrun",
                )
            if method_handle is not None and method_handle.done():
                _skip_with_partial(
                    "method_finished_before_tree",
                    "the method completed without an observed GRFTree entry",
                )
            if remaining <= 0:
                _skip_with_partial(
                    "tree_entry_not_observed",
                    "real GRFTree.fit entry was not observed in bound",
                )
            try:
                event = observer.events.get(timeout=min(remaining, 0.2))
            except __import__("queue").Empty:
                continue
            native_events.append(event)
            if event.get("kind") == "fit_enter" and event.get("fit_layer") == "grf_tree":
                return event

    def _selection_get(
        selected_client: Any, selected_headers: dict[str, str]
    ) -> tuple[Any, str, int]:
        url = f"/api/v1/runs/{run_id}"
        response = selected_client.get(url, headers=selected_headers)
        body, raw_text = _r4_response_body(response)
        return (
            {
                "method": "GET",
                "url": url,
                "request_url": str(response.request.url),
                "status_code": response.status_code,
                "body": body,
                "response_text": raw_text,
            },
            raw_text,
            response.status_code,
        )

    def _capture_negative(
        *,
        kind: str,
        selected_client: Any,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"/api/v1/control/jobs/{job_id}/cancel"
        selection_before, _, _ = _selection_get(selected_client, headers)
        before = _r4_snapshot(reader, job_id)
        start_ns = time.monotonic_ns()
        response = selected_client.post(url, json=body, headers=headers)
        end_ns = time.monotonic_ns()
        response_body, response_text = _r4_response_body(response)
        after = _r4_snapshot(reader, job_id)
        selection_after, _, _ = _selection_get(selected_client, headers)
        before_row = before.get("job_row") or {}
        after_row = after.get("job_row") or {}
        # A legitimate heartbeat may extend only the lease expiry while the worker stays live.
        normalized_before = dict(before_row)
        normalized_after = dict(after_row)
        normalized_before.pop("lease_expires_at", None)
        normalized_after.pop("lease_expires_at", None)
        unchanged = (
            normalized_before == normalized_after
            and before.get("progress") == after.get("progress")
            and before.get("events") == after.get("events")
            and before.get("outbox") == after.get("outbox")
            and _r4_run_selection(selection_before["body"])
            == _r4_run_selection(selection_after["body"])
        )
        return {
            "kind": kind,
            "url": url,
            "request_url": str(response.request.url),
            "request_body": body,
            "request_wire_utf8": response.request.content.decode("utf-8"),
            "status_code": response.status_code,
            "response_body": response_body,
            "response_text": response_text,
            "request_start_ns": start_ns,
            "request_end_ns": end_ns,
            "before_snapshot": before,
            "before_snapshot_sha256": _r4_snapshot_hash(before),
            "after_snapshot": after,
            "after_snapshot_sha256": _r4_snapshot_hash(after),
            "zero_protected_effects": unchanged,
            "event_count_delta": len(after["events"]) - len(before["events"]),
            "outbox_count_delta": len(after["outbox"]) - len(before["outbox"]),
            "selection_before": _r4_run_selection(selection_before["body"]),
            "selection_after": _r4_run_selection(selection_after["body"]),
            "selection_before_http": selection_before,
            "selection_after_http": selection_after,
            "selection_unchanged": (
                _r4_run_selection(selection_before["body"])
                == _r4_run_selection(selection_after["body"])
            ),
        }

    def _capture_completed_method_failure() -> None:
        """Retain the real bounded shared failure, if the handle has completed."""
        if method_handle is None or not method_handle.done():
            return
        try:
            completion = method_handle.result(timeout=0)
            observation["executor"]["shared_execution_handle"]["completion_status"] = (
                completion.status
            )
            actual_value = completion.value
            if completion.status == "completed" and actual_value is not None:
                candidate = getattr(actual_value, "candidate_outcome", None)
                observation["result"]["shared_execution_outcome"] = {
                    "type": type(actual_value).__module__ + "." + type(actual_value).__qualname__,
                    "job_id": getattr(actual_value, "job_id", None),
                    "run_id": getattr(actual_value, "run_id", None),
                    "attempt": getattr(actual_value, "attempt", None),
                    "candidate_status": getattr(candidate, "status", None),
                }
            failure = completion.failure
            if failure is not None:
                observation["result"]["shared_execution_failure"] = {
                    "exception_type": failure.exception_type,
                    "message_excerpt": failure.message_excerpt,
                    "code": failure.code,
                    "retryable": failure.retryable,
                }
        except Exception as exc:
            observation["errors"].append(
                {
                    "stage": "completed_handle_readback",
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
            )

    def _skip_with_partial(stage: str, reason: str) -> None:
        """Persist actual early timing/state as INCONCLUSIVE before pytest skips."""
        observation["case"]["stage"] = stage
        observation["case"]["verdict"]["bounded_native_in_flight"] = "INCONCLUSIVE"
        observation["case"]["verdict"]["native_activity"] = "INCONCLUSIVE"
        # The peer is no longer needed once the premise is lost. Free capacity
        # before diagnostic GET/cleanup, without changing the real fit.
        _release_peer()
        if observer is not None:
            while True:
                try:
                    native_events.append(observer.events.get_nowait())
                except Exception:
                    break
        outer_return = next(
            (
                event
                for event in native_events
                if event.get("kind") == "fit_return" and event.get("fit_layer") == "forest_dr"
            ),
            None,
        )
        observation["result"]["fit_natural_return_ns"] = (
            outer_return.get("monotonic_ns") if outer_return else None
        )
        observation["result"]["method_work_return_ns"] = (
            time.monotonic_ns() if method_handle is not None and method_handle.done() else None
        )
        observation["executor"]["shared_execution_handle"]["done_at_post_end"] = (
            method_handle.done() if method_handle is not None else None
        )
        observation["executor"]["shared_execution_handle"]["completion_status"] = (
            "completed_before_cancel"
            if method_handle is not None and method_handle.done()
            else "UNRUN"
        )
        _capture_completed_method_failure()
        observation["result"]["handler_errors"] = list(worker_errors)
        selected_job = reader.get_job(job_id) if reader is not None and job_id else None
        if selected_job is not None:
            snapshot = _r4_snapshot(reader, job_id)
            observation["final"].update(
                {
                    "fresh_sqlite_readback_monotonic_ns": time.monotonic_ns(),
                    "database_path": str(Path(reader._sqlite_path).resolve()),
                    "snapshot": snapshot,
                    "snapshot_sha256": _r4_snapshot_hash(snapshot),
                    "selection_status": (
                        "selected"
                        if selected_job.method_execution_selection
                        else "withheld_or_absent"
                    ),
                    "selection_attempt": (
                        selected_job.attempt if selected_job.method_execution_selection else None
                    ),
                }
            )
            observation["result"]["selection_status"] = observation["final"]["selection_status"]
        if client is not None and run_id:
            run_response, _, _ = _selection_get(client, headers)
            observation["result"]["fresh_get_status"] = run_response["status_code"]
            observation["result"]["fresh_get_selection"] = _r4_run_selection(run_response["body"])
            observation["cancel"]["fresh_run_get"] = {
                **run_response,
                "monotonic_ns": time.monotonic_ns(),
            }
        pytest.skip(reason)

    class _R4ObservedSemanticError(AssertionError):
        """Keep a completed observed semantic failure distinct from harness errors."""

    try:
        if evidence_root is None:
            raise RuntimeError("POLISYOS_C96_EVIDENCE_DIR_not_set")
        expected_head = os.environ.get("POLISYOS_C96_EXPECTED_HEAD", "")
        expected_tree = os.environ.get("POLISYOS_C96_EXPECTED_TREE", "")
        if not expected_head or not expected_tree:
            raise RuntimeError("expected_source_head_or_tree_not_bound")
        for env_name in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        ):
            if os.environ.get(env_name) != "1":
                raise RuntimeError(f"{env_name}_must_equal_1")

        from polisyos.common import async_tools
        from polisyos.runtime.http import deployment_security
        from polisyos.runtime.http.cancellation_admission import (
            is_current_cancellation_authority,
        )
        from polisyos.runtime.http.services.control_plane_store import (
            ControlJobLeaseLostError,
            ControlPlaneStore,
        )
        from polisyos.runtime.http.services.control_worker import ControlWorker
        from polisyos.runtime.quality.substrate_registry import (
            CatalogServingSourceSelection,
        )
        from tests._helpers.r4_native_fit_observer import (
            FitObserver,
            callable_record,
            mach_thread_basic_info_sample,
            source_file_record,
        )
        from tests._helpers.runtime_http import (
            build_runtime_api_env,
            close_runtime_api_env,
            deployment_security_config_mapping,
        )
        from tests.unit.runtime.http import test_runtime_api_authz as authz
        from tests.unit.runtime.quality.test_catalog_source_identity import (
            _selected_fixture,
        )

        revision = "r4-native-fit-cancel-capacity2-r2"
        profile = async_tools.SharedExecutorProfile(capacity=2, queue_capacity=2, revision=revision)
        async_tools.configure_shared_executor_profile(profile)
        executor = async_tools.get_shared_executor()
        observation["executor"]["profile"]["revision"] = revision
        observation["executor"]["object_type"] = (
            type(executor).__module__ + "." + type(executor).__qualname__
        )
        observation["executor"]["object_id"] = id(executor)
        code_root, owner_root, selected_source = _selected_fixture(native_dir / "catalog")
        catalog_selection = CatalogServingSourceSelection(
            snapshot_root=selected_source.snapshot_root,
            source_owner_root=owner_root,
            database_relative_path=selected_source.database_path.relative_to(
                selected_source.snapshot_root
            ),
            catalog_run_profile="prod_full",
        )
        env = build_runtime_api_env(
            native_dir / "runtime-env",
            include_test_client=False,
            app_kwargs={
                "repo_root": code_root,
                "catalog_source_selection": catalog_selection,
                "process_worker_capacity": 2,
                "process_worker_profile_revision": revision,
            },
            raise_server_exceptions=False,
        )
        original_app_factory = authz.create_runtime_api_app

        def app_factory(**kwargs: Any) -> Any:
            kwargs.setdefault("repo_root", code_root)
            kwargs.setdefault("catalog_source_selection", catalog_selection)
            kwargs["process_worker_capacity"] = 2
            kwargs["process_worker_profile_revision"] = revision
            return original_app_factory(**kwargs)

        monkeypatch.setattr(authz, "create_runtime_api_app", app_factory)
        client, cell, provider = authz._build_secure_client(
            env,
            opa_client=authz._AllowOPA(),
            claims_by_token={},
            raise_server_exceptions=False,
            repo_root=code_root,
            catalog_source_selection=catalog_selection,
        )
        env["client"] = client
        bearer = authz._fixture_bearer("r4-native-authorized")
        denied_bearer = authz._fixture_bearer("r4-native-denied")
        tenant = str(env["tenant_a"])
        cell_id = cell.cell_id
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.core.contracts.runtime import ObservationalRunIntent
        from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
        from polisyos.core.security.tenant_context import tenant_scope

        for token in (bearer, denied_bearer):
            provider.put_claim(
                token,
                UserIdentityClaims(
                    sub="r4-native-fixture",
                    tenant_id=tenant,
                    cell_id=cell_id,
                    roles=frozenset({PolicyOSRole.ADMIN}),
                    mfa_verified=True,
                    iss="https://idp.example",
                    aud="polisyos-runtime",
                    exp=9_999_999_999,
                    iat=1,
                    jti="r4-native-" + token[-12:],
                ),
            )
        headers = {"Authorization": f"Bearer {bearer}", "X-Tenant-ID": tenant}
        denied_headers = {
            "Authorization": f"Bearer {denied_bearer}",
            "X-Tenant-ID": tenant,
        }
        config = deployment_security_config_mapping(native_dir)
        registry_path = native_dir / "cells.json"
        registry_path.write_text(
            json.dumps(
                {
                    "cells": [cell.model_dump(mode="json")],
                    "tenants": [
                        {
                            "tenant_id": item,
                            "name": "R4 synthetic tenant",
                            "tier": cell.tier.value,
                            "region": cell.region,
                            "cell_id": cell_id,
                        }
                        for item in (tenant, str(env["tenant_b"]))
                    ],
                }
            ),
            encoding="utf-8",
        )
        config["cell_registry_path"] = str(registry_path)

        def build_grants(permissions: list[str]) -> Any:
            selected = dict(config)
            selected["service_principals"] = [dict(item) for item in config["service_principals"]]
            selected["service_principals"][0].update(
                tenant_id=tenant, cell_id=cell_id, permissions=permissions
            )
            return deployment_security.build_deployment_security(
                deployment_security.DeploymentSecurityConfig.from_mapping(selected)
            ).principal_grants

        allowed_grants = build_grants(["runs.launch", "runs.view", "jobs.cancel"])
        denied_grants = build_grants(["runs.launch", "runs.view"])
        client.app.state.runtime_deployment_principal_grants = allowed_grants
        client.app.state.control_job_cancellation_rollout_enabled = True
        authz._install_authorization_audit_capture(client)
        with _draining_client(client):
            client_lifespan_entered = True
            service = client.app.state._control_service
            actual_catalog_source = service._catalog_serving_source
            if (
                actual_catalog_source.database_path != selected_source.database_path
                or actual_catalog_source.snapshot_root != selected_source.snapshot_root
            ):
                raise RuntimeError("actual_served_catalog_source_differs_from_selected_fixture")
            observation["catalog"] = {
                "selected_database_path": str(selected_source.database_path),
                "served_database_path": str(actual_catalog_source.database_path),
                "selected_snapshot_root": str(selected_source.snapshot_root),
                "served_snapshot_root": str(actual_catalog_source.snapshot_root),
                "source_owner_root": str(owner_root),
                "selected_and_served_paths_match": True,
                "authority": "fixture_synthetic_candidate",
            }
            if service._worker is not None:
                service._worker.stop()
            raw_store = getattr(service._control_store, "_target", service._control_store)
            db_path = Path(raw_store._sqlite_path).resolve()
            reader = ControlPlaneStore(backend="sqlite", sqlite_path=db_path)
            observation["sqlite"].update(
                {
                    "database_path": str(db_path),
                    "path_is_under_case_sandbox": db_path.is_relative_to(evidence_root),
                }
            )
            if not db_path.is_relative_to(evidence_root):
                raise RuntimeError("control_database_escaped_case_sandbox")

            from polisyos.core.artifacts.store import FileSystemCAS

            cas = FileSystemCAS(env["cas_root"])
            owner_scope = (tenant, cell_id)
            source_ref = _put_runtime_observational_source(
                service,
                owner_scope=owner_scope,
                n_obs=2000,
            )
            source_payload = _runtime_hte_source_payload(n_obs=2000)
            artifact_hex = source_ref.artifact_id.hex
            payload_path = (
                Path(env["cas_root"])
                / "artifacts"
                / "sha256"
                / artifact_hex[:2]
                / artifact_hex[2:4]
                / f"{artifact_hex}.blob"
            ).resolve()
            profile_hash = source_ref.manifest_profile_sha256
            if not profile_hash:
                raise RuntimeError("source_manifest_profile_missing")
            manifest_path = Path(
                cas._manifest_path_for_ref(source_ref.artifact_id, profile_hash)
            ).resolve()
            payload_bytes = payload_path.read_bytes()
            manifest_bytes = manifest_path.read_bytes()
            persisted_envelope = json.loads(payload_bytes)
            persisted_payload = persisted_envelope["contract_payload"]
            sample_ids = persisted_payload["sample_ids"]
            observation["input"].update(
                {
                    "source_ref": source_ref.model_dump(mode="json"),
                    "cas_root": str(Path(env["cas_root"]).resolve()),
                    "payload_path": str(payload_path),
                    "payload_file_bytes": len(payload_bytes),
                    "payload_file_sha256": hashlib.sha256(payload_bytes).hexdigest(),
                    "manifest_path": str(manifest_path),
                    "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                    "manifest_profile_sha256": profile_hash,
                    "rows": len(sample_ids),
                    "sample_ids_unique": len(set(sample_ids)) == len(sample_ids),
                    "observed_source_payload_sha256": hashlib.sha256(
                        json.dumps(source_payload, sort_keys=True, separators=(",", ":")).encode()
                    ).hexdigest(),
                }
            )
            if len(sample_ids) != 2000 or len(set(sample_ids)) != 2000:
                raise RuntimeError("served_input_payload_row_or_sample_id_binding_mismatch")

            method_params = {
                "n_estimators": 128,
                "cv_folds": 2,
                "subforest_size": 4,
                "random_state": 73,
                "n_jobs": 1,
            }
            request_body = {
                "observational_input": {
                    "protocol": "method_input_envelope_v1",
                    "source_ref": source_ref.model_dump(mode="json"),
                    "method": {
                        "fqn": "causal.hte.forest_dr@1.1.0",
                        "params": method_params,
                    },
                }
            }

            # Import the real implementation only inside the eventual runtime node.
            try:
                import econml
                from econml.dr import ForestDRLearner
                from econml.grf._base_grftree import GRFTree
            except (ImportError, OSError) as exc:
                observation["case"]["stage"] = "backend_import_unavailable"
                observation["case"]["verdict"]["backend_load"] = "UNAVAILABLE"
                observation["errors"].append(
                    {
                        "stage": "backend_import",
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
                pytest.skip(f"EconML runtime import unavailable: {type(exc).__name__}: {exc}")
            observation["case"]["verdict"]["backend_load"] = "PASS"
            econml_version = importlib.metadata.version("econml")
            forest_dr_fit = ForestDRLearner.fit
            grftree_fit = GRFTree.fit
            observer = FitObserver(is_shared_worker=executor.is_current_worker)
            observation["native"].update(
                {
                    "econml_version": econml_version,
                    "econml_module_origin": str(Path(econml.__file__).resolve()),
                    "econml_module_sha256": source_file_record(econml.__file__)["sha256"],
                    "forest_dr_defining_class": (
                        ForestDRLearner.__module__ + "." + ForestDRLearner.__qualname__
                    ),
                    "forest_dr_public_import_alias": "econml.dr.ForestDRLearner",
                    "forest_dr_module_origin": str(
                        Path(sys.modules[ForestDRLearner.__module__].__file__).resolve()
                    ),
                    "forest_dr_module_sha256": source_file_record(
                        sys.modules[ForestDRLearner.__module__].__file__
                    )["sha256"],
                    "forest_dr_fit_original": callable_record(forest_dr_fit),
                    "grftree_class": GRFTree.__module__ + "." + GRFTree.__qualname__,
                    "grftree_module_origin": str(
                        Path(sys.modules[GRFTree.__module__].__file__).resolve()
                    ),
                    "grftree_module_sha256": source_file_record(
                        sys.modules[GRFTree.__module__].__file__
                    )["sha256"],
                    "fit_original": callable_record(grftree_fit),
                }
            )
            monkeypatch.setattr(ForestDRLearner, "fit", observer.wrap_forest_dr_fit(forest_dr_fit))
            monkeypatch.setattr(GRFTree, "fit", observer.wrap_grftree_fit(grftree_fit))
            # Submit the normal public job request; no direct estimator or backend call.
            launch_start_ns = time.monotonic_ns()
            launch_response = _post_runtime_api_as_fixture_owner(
                env, "/api/v1/control/runs", json=request_body, headers=headers
            )
            launch_end_ns = time.monotonic_ns()
            launch_body, launch_text = _r4_response_body(launch_response)
            observation["method"]["launch"] = {
                "url": "/api/v1/control/runs",
                "request_url": str(launch_response.request.url),
                "request_body": request_body,
                "request_wire_utf8": launch_response.request.content.decode("utf-8"),
                "start_ns": launch_start_ns,
                "end_ns": launch_end_ns,
                "status_code": launch_response.status_code,
                "response_body": launch_body,
                "response_text": launch_text,
            }
            if launch_response.status_code != 200 or launch_body.get("status") != "accepted":
                observation["case"]["stage"] = "public_admission_refused"
                observation["case"]["verdict"]["method_execution"] = "INCONCLUSIVE"
                pytest.skip("served observational admission did not accept the proposed profile")
            job_id = str(launch_body["job_id"])
            run_id = str(launch_body["run_id"])
            intent_ref = ArtifactRef.model_validate(launch_body["observational_run_intent_ref"])
            intent_hex = intent_ref.artifact_id.hex
            intent_blob_path = (
                Path(env["cas_root"])
                / "artifacts"
                / "sha256"
                / intent_hex[:2]
                / intent_hex[2:4]
                / f"{intent_hex}.blob"
            ).resolve()
            intent_manifest_path = Path(
                cas._manifest_path_for_ref(
                    intent_ref.artifact_id, intent_ref.manifest_profile_sha256
                )
            ).resolve()
            intent_bytes = intent_blob_path.read_bytes()
            intent_manifest_bytes = intent_manifest_path.read_bytes()
            with tenant_scope(None, tenant_id=tenant, cell_id=cell_id):
                intent = ObservationalRunIntent.model_validate(
                    service._read_bounded_intent_artifact(intent_ref)
                )
            observation["method"]["observational_run_intent_artifact"] = {
                "ref": intent_ref.model_dump(mode="json"),
                "blob_path": str(intent_blob_path),
                "blob_bytes": len(intent_bytes),
                "blob_sha256": hashlib.sha256(intent_bytes).hexdigest(),
                "manifest_path": str(intent_manifest_path),
                "manifest_bytes": len(intent_manifest_bytes),
                "manifest_sha256": hashlib.sha256(intent_manifest_bytes).hexdigest(),
                "manifest_profile_sha256": intent_ref.manifest_profile_sha256,
                "payload_sha256": hashlib.sha256(
                    json.dumps(
                        intent.artifact_payload(), sort_keys=True, separators=(",", ":")
                    ).encode()
                ).hexdigest(),
            }
            observation["method"]["intent_cas"] = {
                "ref": intent_ref.model_dump(mode="json"),
                "cas_root": str(Path(env["cas_root"]).resolve()),
                "payload_path": str(intent_blob_path),
                "payload_file_bytes": len(intent_bytes),
                "payload_file_sha256": hashlib.sha256(intent_bytes).hexdigest(),
                "manifest_path": str(intent_manifest_path),
                "manifest_file_bytes": len(intent_manifest_bytes),
                "manifest_sha256": hashlib.sha256(intent_manifest_bytes).hexdigest(),
                "manifest_profile_sha256": intent_ref.manifest_profile_sha256,
                "payload_sha256": hashlib.sha256(
                    json.dumps(
                        intent.artifact_payload(), sort_keys=True, separators=(",", ":")
                    ).encode()
                ).hexdigest(),
            }
            job = reader.get_job(job_id)
            if job is None or job.state != "pending":
                raise RuntimeError("freshly_admitted_job_not_pending")
            observation["method"].update(
                {
                    "job_id": job_id,
                    "run_id": run_id,
                    "effective_fqn": intent.method_fqn,
                    "effective_params": dict(intent.resolved_params),
                    "resource_policy_ref": intent.resource_policy_ref.model_dump(mode="json"),
                    "resource_policy_digest": intent.resource_policy_digest,
                    "admission_binding_status": "recomputed_from_admitted_intent",
                }
            )

            backend = service._method_backend
            original_submit = backend.submit_method_execution_work
            handle_box: dict[str, Any] = {}

            def capture_submit(work: Any) -> Any:
                nonlocal method_handle
                descriptor = {
                    "job_id": work.job_id,
                    "run_id": work.run_id,
                    "attempt": work.attempt,
                    "requested_source_ref": work.requested_source_ref.model_dump(mode="json"),
                    "observational_run_intent_ref": work.observational_run_intent_ref.model_dump(
                        mode="json"
                    ),
                }
                returned_handle = original_submit(work)
                method_handle = returned_handle
                handle_box["handle"] = returned_handle
                observation["method"]["work_descriptor"] = descriptor
                observation["method"]["dispatch_binding_status"] = "captured_actual_submit_work"
                observation["executor"]["submit_owner"] = callable_record(original_submit)
                observation["executor"]["shared_execution_handle"].update(
                    {
                        "captured": True,
                        "type": type(returned_handle).__module__
                        + "."
                        + type(returned_handle).__qualname__,
                        "future_id": id(getattr(returned_handle, "_future", returned_handle)),
                    }
                )
                return returned_handle

            monkeypatch.setattr(backend, "submit_method_execution_work", capture_submit)
            original_renew = raw_store.renew_job_lease

            def record_renew(**kwargs: Any) -> bool:
                result = original_renew(**kwargs)
                renewed_ns = time.monotonic_ns()
                current = reader.get_job(job_id)
                with renewals_lock:
                    observation["lease"]["renewals"].append(
                        {
                            "monotonic_ns": renewed_ns,
                            "readback_monotonic_ns": time.monotonic_ns(),
                            "expected_attempt": kwargs.get("expected_attempt"),
                            "result": result,
                            "fresh_owner": current.lease_owner if current else None,
                            "fresh_attempt": current.attempt if current else None,
                            "fresh_lease_expires_at": (
                                current.lease_expires_at.isoformat()
                                if current and current.lease_expires_at
                                else None
                            ),
                        }
                    )
                return result

            monkeypatch.setattr(raw_store, "renew_job_lease", record_renew)
            original_cancel = raw_store.cancel_job

            def observe_cancel(**kwargs: Any) -> Any:
                proof = kwargs.get("authorization_proof")
                verification = getattr(proof, "verification", None)
                bound = getattr(proof, "bound_resource", None)
                selectors = (
                    dict(getattr(bound, "canonical_selectors", {})) if bound is not None else {}
                )
                raw_cell_selector = selectors.get("cell_id")
                try:
                    actual_cell_id = (
                        json.loads(raw_cell_selector)
                        if isinstance(raw_cell_selector, str)
                        else None
                    )
                except ValueError:
                    actual_cell_id = None
                entry = {
                    "monotonic_ns": time.monotonic_ns(),
                    "current_authority": is_current_cancellation_authority(proof),
                    "operation_id": kwargs.get("operation_id"),
                    "expected_attempt": kwargs.get("expected_attempt"),
                    "expected_lease_owner": kwargs.get("expected_lease_owner"),
                    "authorized_actor": getattr(verification, "subject", None),
                    "tenant_id": getattr(verification, "tenant_id", None),
                    "bound_job_id_selector": selectors.get("job_id"),
                    "bound_cell_id_selector": raw_cell_selector,
                    "cell_id": actual_cell_id,
                    "body_sha256": getattr(bound, "body_sha256", None),
                    "body_called": True,
                    "body_called_at_ns": time.monotonic_ns(),
                }
                control_calls.append(entry)
                return original_cancel(**kwargs)

            monkeypatch.setattr(raw_store, "cancel_job", observe_cancel)
            worker = ControlWorker(
                store=service._control_store,
                handler=service._process_control_job,
                worker_id=worker_id,
                lease_seconds=2,
            )
            worker._heartbeat_interval_s = 0.05
            dispatch_done = threading.Event()

            def dispatch() -> None:
                try:
                    worker.dispatch_once()
                except BaseException as exc:
                    worker_errors.append(
                        {
                            "type": type(exc).__name__,
                            "message": str(exc),
                            "monotonic_ns": time.monotonic_ns(),
                        }
                    )
                finally:
                    dispatch_done.set()

            dispatch_thread = threading.Thread(
                target=dispatch, name="r4-native-control-dispatch", daemon=True
            )
            dispatch_thread.start()
            running_deadline = time.monotonic() + 30.0
            running = None
            while time.monotonic() < running_deadline:
                running = reader.get_job(job_id)
                if running is not None and running.state == "running":
                    break
                if dispatch_done.is_set() and method_handle is None:
                    observation["result"]["handler_errors"] = list(worker_errors)
                    observation["result"]["handler_disposition"] = (
                        "dispatch_returned_without_handle"
                    )
                    _skip_with_partial(
                        "dispatch_finished_without_method",
                        "dispatch ended before an observed live lease or method handle",
                    )
                dispatch_done.wait(0.002)
            if running is None or running.state != "running" or not running.lease_owner:
                observation["case"]["stage"] = "worker_lease_not_observed"
                pytest.skip("the real ControlWorker did not establish a fresh lease in bound")
            attempt = running.attempt
            lease_owner = str(running.lease_owner)
            observation["method"].update(
                {
                    "attempt": attempt,
                    "lease_owner": lease_owner,
                    "lease_expires_at": running.lease_expires_at.isoformat()
                    if running.lease_expires_at
                    else None,
                }
            )
            observation["lease"]["initial_readback"] = {
                "state": running.state,
                "attempt": attempt,
                "lease_owner": lease_owner,
                "lease_expires_at": running.lease_expires_at.isoformat()
                if running.lease_expires_at
                else None,
            }

            # Wait only in the test thread. The actual fit wrapper never blocks.
            _next_native_event(600.0)
            observer_worker = observer.worker
            if not isinstance(observer_worker, dict):
                raise RuntimeError("shared_worker_identity_not_observed")
            if not observer_worker.get("is_current_shared_executor_worker"):
                raise RuntimeError("GRFTree.fit_did_not_run_on_shared_executor_worker")

            # This distinct nonnumeric peer occupies the second physical slot
            # only after the real selected native fit has entered. It never
            # stands in for fit progress and is released after the POST.
            def nonnumeric_peer() -> None:
                observation["executor"]["nonnumeric_peer"].update(
                    {
                        "pid": os.getpid(),
                        "thread_id": threading.get_ident(),
                        "native_thread_id": threading.get_native_id(),
                        "enter_ns": time.monotonic_ns(),
                        "is_current_shared_executor_worker": async_tools.is_current_shared_executor_worker(),
                    }
                )
                peer_started.set()
                released = peer_release.wait(timeout=600.0)
                observation["executor"]["nonnumeric_peer"].update(
                    {
                        "exit_ns": time.monotonic_ns(),
                        "release_observed": released,
                    }
                )

            peer_future = executor.submit(nonnumeric_peer)
            if not peer_started.wait(timeout=30.0):
                _skip_with_partial(
                    "peer_not_observed", "nonnumeric second worker did not start in bound"
                )
            if method_handle is not None and method_handle.done():
                _skip_with_partial(
                    "fit_finished_before_negatives", "real method finished before pool saturation"
                )

            # Queue both owner-configured FIFO slots behind the actual fit and peer.
            def queued_follower(follower_id: int) -> None:
                queued_body_returns.append(
                    {
                        "follower_id": follower_id,
                        "monotonic_ns": time.monotonic_ns(),
                        "pid": os.getpid(),
                        "thread_id": threading.get_ident(),
                    }
                )

            queue_future = executor.submit(queued_follower, 1)
            queue_future2 = executor.submit(queued_follower, 2)
            queue_pending = all(
                not future.done() and not future.running()
                for future in (queue_future, queue_future2)
            )
            full_observed_ns = time.monotonic_ns()
            observation["executor"]["queue"].update(
                {
                    "follower_future_type": type(queue_future).__module__
                    + "."
                    + type(queue_future).__qualname__,
                    "follower_future_id": id(queue_future),
                    "second_follower_future_id": id(queue_future2),
                    "pending_when_fit_active": queue_pending,
                    "full_observed_ns": full_observed_ns,
                }
            )
            try:
                executor.submit(lambda: None)
            except async_tools.SharedExecutorBackpressureError as exc:
                observation["executor"]["queue"].update(
                    {
                        "overflow_error_code": exc.code,
                        "overflow_capacity": exc.capacity,
                        "overflow_queue_capacity": exc.queue_capacity,
                        "overflow_queue_depth": exc.queue_depth,
                        "full_observed_ns": time.monotonic_ns(),
                    }
                )
            else:
                observation["executor"]["queue"]["overflow_error_code"] = "not_raised"
            observation["executor"]["queue"]["submit_owner"] = callable_record(executor.submit)
            with executor._admission_lock:
                observation["executor"]["queue"].update(
                    {
                        "physical_workers": executor._physical_workers,
                        "queued_jobs": executor._queued_jobs,
                        "outstanding_jobs": executor._outstanding_jobs,
                    }
                )
            if (
                not queue_pending
                or observation["executor"]["queue"]["overflow_error_code"]
                != "shared_executor_queue_full"
            ):
                _skip_with_partial(
                    "saturation_premise_missing",
                    "real shared queue was not observed full while the fit was running",
                )

            # Wait in the test thread for natural progress and two real lease
            # renewals after the queue becomes full. Never pause a fit callback.
            full_at = observation["executor"]["queue"]["full_observed_ns"]
            progress_deadline = test_started_monotonic + 600.0
            while True:
                with renewals_lock:
                    eligible_renewals = [
                        row
                        for row in observation["lease"]["renewals"]
                        if row["monotonic_ns"] > full_at
                        and row["result"] is True
                        and row["expected_attempt"] == attempt
                        and row["fresh_attempt"] == attempt
                        and row["fresh_owner"] == lease_owner
                    ]
                completed_trees = [
                    event
                    for event in native_events
                    if event.get("fit_layer") == "grf_tree"
                    and event.get("kind") == "fit_return"
                    and event.get("success") is True
                ]
                if len(eligible_renewals) >= 2 and completed_trees:
                    break
                if (method_handle is not None and method_handle.done()) or any(
                    event.get("fit_layer") == "forest_dr" and event.get("kind") == "fit_return"
                    for event in native_events
                ):
                    _skip_with_partial(
                        "fit_finished_before_negatives",
                        "real method completed before the saturated progress premise",
                    )
                if time.monotonic() >= progress_deadline:
                    _skip_with_partial(
                        "live_renewal_premise_missing",
                        "two renewed leases and real tree progress were not observed in the bounded test interval",
                    )
                try:
                    event = observer.events.get(timeout=0.02)
                    native_events.append(event)
                except __import__("queue").Empty:
                    pass

            # Preserve the exact still-running scope before both HTTP negatives.
            running = reader.get_job(job_id)
            if running is None or running.state != "running" or running.attempt != attempt:
                _skip_with_partial(
                    "fit_finished_before_negatives",
                    "fit/lease no longer running before the live negative controls",
                )
            stale_body = {
                "expected_lease_owner": lease_owner,
                "expected_attempt": max(0, attempt - 1),
                "operation_id": "r4-native-stale-attempt",
            }
            stale_negative = _capture_negative(
                kind="stale_attempt",
                selected_client=client,
                headers=headers,
                body=stale_body,
            )
            observation["negatives"].append(stale_negative)
            after_stale_negative = reader.get_job(job_id)
            if (
                after_stale_negative is None
                or after_stale_negative.state != "running"
                or after_stale_negative.attempt != attempt
                or after_stale_negative.lease_owner != lease_owner
            ):
                _skip_with_partial(
                    "fit_finished_during_negative_controls",
                    "fit/lease changed during the stale-attempt control; INCONCLUSIVE",
                )
            denied_body = {
                "expected_lease_owner": lease_owner,
                "expected_attempt": attempt,
                "operation_id": "r4-native-denied-permission",
            }
            client.app.state.runtime_deployment_principal_grants = denied_grants
            denied_negative = _capture_negative(
                kind="denied_permission",
                selected_client=client,
                headers=denied_headers,
                body=denied_body,
            )
            observation["negatives"].append(denied_negative)
            client.app.state.runtime_deployment_principal_grants = allowed_grants
            after_negatives = reader.get_job(job_id)
            observation["negatives_running_scope"] = {
                "state": after_negatives.state if after_negatives else None,
                "attempt": after_negatives.attempt if after_negatives else None,
                "lease_owner": after_negatives.lease_owner if after_negatives else None,
            }

            # A naturally finished model is a bounded INCONCLUSIVE candidate. Do not
            # cancel a terminal job or reinterpret this timing as a product defect.
            while True:
                try:
                    native_events.append(observer.events.get_nowait())
                except Exception:
                    break
            early_fit_return = next(
                (
                    event
                    for event in native_events
                    if event.get("kind") == "fit_return" and event.get("fit_layer") == "forest_dr"
                ),
                None,
            )
            after_negatives = reader.get_job(job_id)
            if (
                early_fit_return is not None
                or (method_handle is not None and method_handle.done())
                or after_negatives is None
                or after_negatives.state != "running"
                or after_negatives.attempt != attempt
                or after_negatives.lease_owner != lease_owner
            ):
                observation["case"]["stage"] = "fit_finished_before_cancel"
                observation["case"]["verdict"]["bounded_native_in_flight"] = "INCONCLUSIVE"
                observation["case"]["verdict"]["native_activity"] = "INCONCLUSIVE"
                observation["result"]["fit_natural_return_ns"] = (
                    early_fit_return.get("monotonic_ns") if early_fit_return else None
                )
                observation["result"]["method_work_return_ns"] = (
                    time.monotonic_ns()
                    if method_handle is not None and method_handle.done()
                    else None
                )
                observation["executor"]["shared_execution_handle"]["done_at_post_end"] = (
                    method_handle.done() if method_handle is not None else None
                )
                observation["executor"]["shared_execution_handle"]["completion_status"] = (
                    "completed_before_cancel"
                    if method_handle is not None and method_handle.done()
                    else "UNRUN"
                )
                _release_peer()
                _capture_completed_method_failure()
                partial = _r4_snapshot(reader, job_id)
                observation["final"].update(
                    {
                        "fresh_sqlite_readback_monotonic_ns": time.monotonic_ns(),
                        "database_path": str(db_path),
                        "snapshot": partial,
                        "snapshot_sha256": _r4_snapshot_hash(partial),
                        "selection_status": (
                            "withheld_or_absent"
                            if not after_negatives or not after_negatives.method_execution_selection
                            else "selected"
                        ),
                        "selection_attempt": (
                            after_negatives.attempt
                            if after_negatives and after_negatives.method_execution_selection
                            else None
                        ),
                    }
                )
                observation["result"]["selection_status"] = observation["final"]["selection_status"]
                run_body, _, _ = _selection_get(client, headers)
                observation["result"]["fresh_get_status"] = run_body["status_code"]
                observation["result"]["fresh_get_selection"] = _r4_run_selection(run_body["body"])
                pytest.skip(
                    "natural fit completion or lost live lease before cancellation; INCONCLUSIVE"
                )

            # Query the actual same worker port around the unmodified public POST.
            port = observer_worker.get("mach_thread_port")
            observation["executor"]["occupied_worker"].update(
                {
                    "pid": observer_worker.get("pid"),
                    "thread_id": observer_worker.get("thread_id"),
                    "native_thread_id": observer_worker.get("native_thread_id"),
                    "thread_name": observer_worker.get("thread_name"),
                    "is_current_shared_executor_worker": observer_worker.get(
                        "is_current_shared_executor_worker"
                    ),
                    "mach_thread_port": port,
                }
            )
            if type(port) is int and port > 0:
                sample_before = mach_thread_basic_info_sample(port)
            else:
                sample_before = {
                    "error": observer_worker.get("mach_port_error") or "port_unavailable"
                }
            cancel_url = f"/api/v1/control/jobs/{job_id}/cancel"
            cancel_body = {
                "expected_lease_owner": lease_owner,
                "expected_attempt": attempt,
                "operation_id": "r4-native-authorized-cancel",
            }
            post_start_ns = time.monotonic_ns()
            cancel_response = client.post(cancel_url, json=cancel_body, headers=headers)
            post_end_ns = time.monotonic_ns()
            future_done_at_response = method_handle.done() if method_handle is not None else None
            if type(port) is int and port > 0:
                sample_after = mach_thread_basic_info_sample(port)
            else:
                sample_after = {
                    "error": observer_worker.get("mach_port_error") or "port_unavailable"
                }
            # The POST has returned; release the explicitly held peer so the
            # real method's later guarded CAS work is not artificially starved.
            _release_peer()
            cancel_body_wire, cancel_text = _r4_response_body(cancel_response)
            same_identity = all(
                observer_worker.get(field) is not None
                for field in (
                    "pid",
                    "thread_id",
                    "native_thread_id",
                    "mach_thread_port",
                )
            )
            cpu_before = _r4_mach_nested_sample(sample_before)
            cpu_after = _r4_mach_nested_sample(sample_after)
            before_cpu = cpu_before.get("thread_cpu_microseconds")
            after_cpu = cpu_after.get("thread_cpu_microseconds")
            cpu_delta = (
                after_cpu - before_cpu
                if type(before_cpu) is int and type(after_cpu) is int
                else None
            )
            bracket_error = sample_before.get("error") or sample_after.get("error")
            bracket_available = (
                same_identity
                and cpu_before.get("return_code") == 0
                and cpu_after.get("return_code") == 0
                and cpu_delta is not None
            )
            observation["cancel"].update(
                {
                    "authorized": True,
                    "post_start_ns": post_start_ns,
                    "post_end_ns": post_end_ns,
                    "status_code": cancel_response.status_code,
                    "url": cancel_url,
                    "request_url": str(cancel_response.request.url),
                    "request_body": cancel_body,
                    "body": cancel_body_wire,
                    "request_wire_utf8": cancel_response.request.content.decode("utf-8"),
                    "response_body": cancel_body_wire,
                    "response_text": cancel_text,
                    "worker_cpu_bracket": {
                        "method": "mach_THREAD_BASIC_INFO",
                        "available": bracket_available,
                        "pid": observer_worker.get("pid"),
                        "thread_id": observer_worker.get("thread_id"),
                        "native_thread_id": observer_worker.get("native_thread_id"),
                        "mach_thread_port": port,
                        "flavor": 3,
                        "count": 10,
                        "struct_size_bytes": 40,
                        "resolution_microseconds": 1,
                        "before": cpu_before,
                        "after": cpu_after,
                        "thread_cpu_delta_microseconds": cpu_delta,
                        "error": bracket_error,
                    },
                    "future_unfinished_at_response": (
                        not future_done_at_response if future_done_at_response is not None else None
                    ),
                    "database_path": str(db_path),
                }
            )
            observation["executor"]["shared_execution_handle"]["done_at_post_end"] = (
                future_done_at_response
            )
            if control_calls:
                positive_calls = [
                    item
                    for item in control_calls
                    if item.get("operation_id") == cancel_body["operation_id"]
                ]
                if positive_calls:
                    initial_call = positive_calls[0]
                    observation["cancel"]["actual_store_cancel_entry_ns"] = initial_call[
                        "monotonic_ns"
                    ]
                    observation["cancel"]["current_authority_at_entry"] = initial_call[
                        "current_authority"
                    ]
                    observation["cancel"]["actual_store_cancel_body_called_at_ns"] = initial_call[
                        "body_called_at_ns"
                    ]
                    observation["cancel"]["authority"] = {
                        "authorized_actor": initial_call["authorized_actor"],
                        "tenant_id": initial_call["tenant_id"],
                        "bound_job_id_selector": initial_call["bound_job_id_selector"],
                        "bound_cell_id_selector": initial_call["bound_cell_id_selector"],
                        "body_sha256": initial_call["body_sha256"],
                        "operation_id": initial_call["operation_id"],
                        "expected_lease_owner": initial_call["expected_lease_owner"],
                        "expected_attempt": initial_call["expected_attempt"],
                    }
                    observation["cancel"]["authorized_actor"] = initial_call["authorized_actor"]
                    observation["cancel"]["tenant_id"] = initial_call["tenant_id"]
                    observation["cancel"]["cell_id"] = initial_call["cell_id"]

            fresh_cancel_snapshot = _r4_snapshot(reader, job_id)
            observed_after_cancel = reader.get_job(job_id)
            fresh_cancel_readback_ns = time.monotonic_ns()
            fresh_job = None
            fresh_verification_error = None
            if observed_after_cancel is None:
                _skip_with_partial(
                    "fit_finished_during_cancel",
                    "fresh job disappeared; current attempt is not established",
                )
            if observed_after_cancel.state == "cancelled":
                try:
                    fresh_job = reader.get_cancelled_job_verified_record(job_id)
                except ControlJobLeaseLostError as exc:
                    # Preserve the owner's actual rejection with raw rows. A
                    # different unexpected exception remains an instrument error.
                    fresh_verification_error = {"type": type(exc).__name__, "message": str(exc)}
                fresh_cancel_readback_ns = time.monotonic_ns()
            elif (
                observed_after_cancel.state != "running"
                or observed_after_cancel.attempt != attempt
                or observed_after_cancel.lease_owner != lease_owner
            ):
                _skip_with_partial(
                    "fit_finished_during_cancel",
                    "the original live attempt is no longer established after cancellation",
                )
            # A still-running same attempt is retained as an actual candidate red.
            # Do not retry or run stale-owner mutations against a live owner.
            observation["cancel"]["fresh_sqlite_readback"] = {
                "monotonic_ns": fresh_cancel_readback_ns,
                "snapshot": fresh_cancel_snapshot,
                "snapshot_sha256": _r4_snapshot_hash(fresh_cancel_snapshot),
                "subsequent_job_read": {
                    "job_id": observed_after_cancel.job_id,
                    "run_id": observed_after_cancel.run_id,
                    "state": observed_after_cancel.state,
                    "attempt": observed_after_cancel.attempt,
                    "lease_owner": observed_after_cancel.lease_owner,
                },
                "verified_cancelled_record": fresh_job is not None
                and fresh_job.state == "cancelled",
                "verification_error": fresh_verification_error,
            }
            fresh_job_url = f"/api/v1/control/jobs/{job_id}"
            fresh_get_response = client.get(fresh_job_url, headers=headers)
            fresh_get_body, fresh_get_text = _r4_response_body(fresh_get_response)
            observation["cancel"]["fresh_http_get"] = {
                "method": "GET",
                "url": fresh_job_url,
                "monotonic_ns": time.monotonic_ns(),
                "status_code": fresh_get_response.status_code,
                "body": fresh_get_body,
                "request_url": str(fresh_get_response.request.url),
                "response_text": fresh_get_text,
            }
            run_get, _, _ = _selection_get(client, headers)
            run_get["monotonic_ns"] = time.monotonic_ns()
            observation["cancel"]["fresh_run_get"] = run_get
            observation["cancel"]["selection_snapshot"] = _r4_run_selection(run_get["body"])

            if fresh_job is not None:
                retry_start_ns = time.monotonic_ns()
                retry_response = client.post(cancel_url, json=cancel_body, headers=headers)
                retry_body, retry_text = _r4_response_body(retry_response)
                observation["cancel"]["retry"] = {
                    "method": "POST",
                    "url": cancel_url,
                    "monotonic_ns": retry_start_ns,
                    "status_code": retry_response.status_code,
                    "request_body": cancel_body,
                    "request_wire_utf8": retry_response.request.content.decode("utf-8"),
                    "request_url": str(retry_response.request.url),
                    "body": retry_body,
                    "response_text": retry_text,
                }

            # Supplementary old-owner guarded writes run only after durable fencing.
            def stale_operation(name: str, operation: Any) -> None:
                record = {
                    "called": True,
                    "refused": False,
                    "exception_type": None,
                    "exception_message": None,
                    "body_entered": False,
                    "returned_normally": None,
                }
                try:
                    operation(record)
                    record["returned_normally"] = True
                except Exception as exc:
                    record["returned_normally"] = False
                    record["exception_type"] = type(exc).__name__
                    record["exception_message"] = str(exc)
                    record["refused"] = isinstance(exc, ControlJobLeaseLostError)
                observation["final"]["stale_write_results"][name] = record
                observation["final"]["stale_write_refused"][name] = record["refused"]

            def progress_write(record: dict[str, Any]) -> None:
                record["body_entered"] = None
                service._control_store.update_progress_state(
                    job_id=job_id,
                    state="running",
                    progress={"r4_stale_probe": True},
                    expected_lease_owner=lease_owner,
                    expected_attempt=attempt,
                )

            def manifest_write(record: dict[str, Any]) -> None:
                with service._control_store.job_execution_fence(
                    job_id=job_id,
                    worker_id=worker_id,
                    attempt=attempt,
                ):
                    record["body_entered"] = True
                    service._control_store.update_manifest_ref(
                        job_id=job_id,
                        capability_manifest_ref=str(fresh_job.capability_manifest_ref),
                    )

            def terminal_write(record: dict[str, Any]) -> None:
                record["body_entered"] = None
                service._control_store.complete_job(
                    job_id=job_id,
                    run_id=run_id,
                    expected_lease_owner=lease_owner,
                    expected_attempt=attempt,
                )

            if fresh_job is not None:
                stale_operation("progress", progress_write)
                stale_operation("manifest", manifest_write)
                stale_operation("terminal", terminal_write)

            # Wait outside the native fit callback for the actual outer model return.
            wait_deadline = time.monotonic() + 600.0
            while time.monotonic() < wait_deadline and fit_return_event is None:
                try:
                    event = observer.events.get(
                        timeout=min(0.5, max(0.001, wait_deadline - time.monotonic()))
                    )
                except Exception:
                    if (
                        dispatch_done.is_set()
                        and method_handle is not None
                        and method_handle.done()
                    ):
                        break
                    continue
                native_events.append(event)
                if event.get("fit_layer") == "forest_dr" and event.get("kind") == "fit_return":
                    fit_return_event = event
            if fit_return_event is not None:
                observation["result"]["fit_natural_return_ns"] = fit_return_event.get(
                    "monotonic_ns"
                )
            if fit_return_event is not None and method_handle is not None:
                completion_deadline = test_started_monotonic + 600.0
                while not method_handle.done() and time.monotonic() < completion_deadline:
                    time.sleep(0.02)
                while (
                    any(
                        future is not None and not future.done()
                        for future in (queue_future, queue_future2)
                    )
                    and time.monotonic() < completion_deadline
                ):
                    time.sleep(0.02)
            observation["result"]["method_work_return_ns"] = (
                time.monotonic_ns() if method_handle is not None and method_handle.done() else None
            )
            if method_handle is not None and method_handle.done():
                try:
                    completion = method_handle.result(timeout=0)
                    observation["executor"]["shared_execution_handle"]["completion_status"] = (
                        completion.status
                    )
                    _capture_completed_method_failure()
                    if completion.status == "completed":
                        from polisyos.scientist.compute.runner import (
                            MethodExecutionRefOutcome,
                        )

                        actual = completion.value
                        if type(actual) is MethodExecutionRefOutcome:
                            candidate = actual.candidate_outcome
                            observation["result"]["candidate_outcome"] = (
                                candidate.model_dump(mode="json") if candidate is not None else None
                            )
                            observation["result"]["method_result_ref"] = (
                                actual.method_result_ref.model_dump(mode="json")
                            )
                            observation["result"]["method_evidence_ref"] = (
                                actual.method_evidence_ref.model_dump(mode="json")
                            )
                            observation["result"]["selection_attempt"] = actual.attempt
                            observation["executor"]["shared_execution_handle"]["typed_outcome"] = {
                                "type": type(actual).__module__ + "." + type(actual).__qualname__,
                                "job_id": actual.job_id,
                                "run_id": actual.run_id,
                                "attempt": actual.attempt,
                                "requested_source_ref": actual.requested_source_ref.model_dump(
                                    mode="json"
                                ),
                                "observational_run_intent_ref": actual.observational_run_intent_ref.model_dump(
                                    mode="json"
                                ),
                                "candidate_outcome": observation["result"]["candidate_outcome"],
                                "method_result_ref": observation["result"]["method_result_ref"],
                                "method_evidence_ref": observation["result"]["method_evidence_ref"],
                            }
                            with tenant_scope(None, tenant_id=tenant, cell_id=cell_id):
                                result_bytes = cas.get_bytes(actual.method_result_ref.artifact_id)
                                evidence_bytes = cas.get_bytes(
                                    actual.method_evidence_ref.artifact_id
                                )
                            observation["result"]["cas_readback_status"] = "bytes_reloaded"
                            observation["result"]["cas_readback_sha256"] = {
                                "method_result": hashlib.sha256(result_bytes).hexdigest(),
                                "method_evidence": hashlib.sha256(evidence_bytes).hexdigest(),
                            }
                            observation["result"]["semantic_estimate_valid"] = bool(
                                candidate is not None
                                and candidate.status == "success"
                                and candidate.sample_size == 2000
                                and candidate.point_estimate is not None
                                and candidate.confidence_interval is not None
                                and all(
                                    map(
                                        __import__("math").isfinite,
                                        (
                                            candidate.point_estimate,
                                            *candidate.confidence_interval,
                                        ),
                                    )
                                )
                            )
                        else:
                            observation["executor"]["shared_execution_handle"]["typed_outcome"] = {
                                "type": type(actual).__module__ + "." + type(actual).__qualname__
                            }
                except Exception as exc:
                    # Numerical/result CAS readback is optional for the cancellation
                    # property. Preserve its failure without fabricating a result;
                    # an actual handle read failure is separately captured by the drain.
                    observation["result"]["cas_readback_status"] = "UNAVAILABLE"
                    observation["result"]["optional_outcome_readback_error"] = {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }
            elif method_handle is not None:
                observation["executor"]["shared_execution_handle"]["completion_status"] = (
                    "still_running_at_bound"
                )
            if dispatch_thread is not None:
                while (
                    dispatch_thread.is_alive() and time.monotonic() < test_started_monotonic + 600.0
                ):
                    dispatch_thread.join(timeout=0.2)
            observation["result"]["handler_errors"] = worker_errors
            observation["result"]["handler_disposition"] = (
                "dispatch_returned" if dispatch_done.is_set() else "handler_not_returned_at_bound"
            )

            final_readback_ns = time.monotonic_ns()
            final_snapshot = _r4_snapshot(reader, job_id)
            final_job = reader.get_job(job_id)
            final_run_get, _, _ = _selection_get(client, headers)
            final_selection = _r4_run_selection(final_run_get["body"])
            events = final_snapshot["events"]
            outbox = final_snapshot["outbox"]
            observation["final"].update(
                {
                    "fresh_sqlite_readback_monotonic_ns": final_readback_ns,
                    "database_path": str(db_path),
                    "snapshot": final_snapshot,
                    "snapshot_sha256": _r4_snapshot_hash(final_snapshot),
                    "cancel_event_count": sum(
                        row.get("event_type") == "job_cancelled" for row in events
                    ),
                    "cancel_outbox_count": sum(
                        row.get("topic") == "control.job.cancelled" for row in outbox
                    ),
                    "completed_or_failed_terminal_count": sum(
                        row.get("event_type") in {"job_completed", "job_failed"} for row in events
                    ),
                    "selection_status": (
                        final_selection.get("status")
                        if isinstance(final_selection, dict)
                        else "withheld_or_absent"
                    ),
                    "selection_attempt": final_job.attempt
                    if final_job and final_job.method_execution_selection
                    else None,
                    "queued_body_entered_after_fit_return": bool(
                        fit_return_event is not None
                        and queued_body_returns
                        and queued_body_returns[0]["monotonic_ns"]
                        > fit_return_event.get("monotonic_ns", 0)
                    ),
                    "queued_body_entered_after_peer_release": bool(
                        len(queued_body_returns) == 2
                        and observation["executor"]["nonnumeric_peer"]["release_ns"] is not None
                        and all(
                            row["monotonic_ns"]
                            > observation["executor"]["nonnumeric_peer"]["release_ns"]
                            for row in queued_body_returns
                        )
                    ),
                }
            )
            if fit_return_event is not None and queued_body_returns:
                observation["executor"]["queue"]["body_entered_before_fit_return"] = (
                    queued_body_returns[0]["monotonic_ns"]
                    <= fit_return_event.get("monotonic_ns", 0)
                )
            observation["executor"]["queue"]["follower_events"] = list(queued_body_returns)
            observation["result"]["selection_status"] = observation["final"]["selection_status"]
            observation["result"]["fresh_get_status"] = final_run_get["status_code"]
            observation["result"]["fresh_get_selection"] = final_selection
            observation["case"]["verdict"]["durable_cancel"] = (
                "PASS"
                if final_job is not None
                and final_job.state == "cancelled"
                and observation["final"]["cancel_event_count"] == 1
                and observation["final"]["cancel_outbox_count"] == 1
                and observation["final"]["completed_or_failed_terminal_count"] == 0
                and not final_job.method_execution_selection
                else "FAIL"
            )
            observation["case"]["verdict"]["method_execution"] = (
                "OBSERVED" if fit_return_event is not None else "INCONCLUSIVE"
            )
            observation["case"]["stage"] = "complete"

            # Recompute from actual origins/events first, then falsify the decisive
            # native evidence while retaining every superficial HTTP/queue marker.
            observation["native"]["forest_dr_fit_events"] = [
                event for event in native_events if event.get("fit_layer") == "forest_dr"
            ]
            observation["native"]["grf_tree_fit_events"] = [
                event for event in native_events if event.get("fit_layer") == "grf_tree"
            ]
            module_readset_cache = _r4_module_readset()
            observation["native"]["loaded_native_modules"] = module_readset_cache[1]
            native_classification = _r4_native_inflight_classification(observation)
            stripped = json.loads(json.dumps(observation))
            stripped["native"]["loaded_native_modules"] = []
            stripped["native"]["fit_original"] = {}
            stripped["native"]["forest_dr_fit_original"] = {}
            stripped["native"]["grf_tree_fit_events"] = []
            stripped["cancel"]["worker_cpu_bracket"]["available"] = False
            stripped["cancel"]["worker_cpu_bracket"]["thread_cpu_delta_microseconds"] = None
            stripped["cancel"]["worker_cpu_bracket"]["before"] = {}
            stripped["cancel"]["worker_cpu_bracket"]["after"] = {}
            removed_classification = _r4_native_inflight_classification(stripped)
            fake = json.loads(json.dumps(stripped))
            fake["native"]["grf_tree_fit_events"] = [
                {
                    "kind": "fit_return",
                    "success": True,
                    "sequence": 1,
                    "fit_call_id": 1,
                    "tree_identity": 1,
                    "pid": observer_worker.get("pid"),
                    "thread_id": observer_worker.get("thread_id"),
                    "native_thread_id": observer_worker.get("native_thread_id"),
                    "monotonic_ns": observation["cancel"]["post_end_ns"] + 1,
                }
            ]
            fake_classification = _r4_native_inflight_classification(fake)
            durable_signature_before = _r4_durable_cancel_signature(observation)
            durable_signature_after = _r4_durable_cancel_signature(stripped)
            observation["native_removal_falsifier"] = {
                "retained_http_status": observation["cancel"]["status_code"],
                "retained_queue_error": observation["executor"]["queue"]["overflow_error_code"],
                "native_evidence_removed": True,
                "native_classification_before": native_classification,
                "native_classification_after_removal": removed_classification,
                "present_but_fake_classification": fake_classification,
                "durable_signature_unchanged": durable_signature_before == durable_signature_after,
                "classifier_implementation": "_r4_native_inflight_classification_from_raw_events",
            }
            observation["case"]["verdict"]["bounded_native_in_flight"] = (
                "PASS"
                if native_classification in {"PASS", "BOUNDED_NATIVE_IN_FLIGHT"}
                else "INCONCLUSIVE"
            )
            observation["case"]["verdict"]["native_activity"] = (
                "PASS" if native_classification == "PASS" else "INCONCLUSIVE"
            )

            # Collect all completed evidence before reporting an observed red.
            # The controller separately qualifies authority, in-flight timing,
            # race boundaries and stored carriers before attributing a failure.
            if not (
                observation["cancel"]["future_unfinished_at_response"] is True
                and fit_return_event is not None
                and fit_return_event.get("monotonic_ns", 0) > post_end_ns
            ):
                observation["case"]["stage"] = "insufficient_live_overlap"
                observation["case"]["verdict"]["bounded_native_in_flight"] = "INCONCLUSIVE"
                pytest.skip("real native fit did not span cancellation and natural return")
            semantic_failures = []
            if fresh_job is None:
                semantic_failures.append(
                    "first_cancel_left_same_attempt_running"
                    if observed_after_cancel.state == "running"
                    else "cancelled_record_failed_owner_verification"
                )
            elif observation["case"]["verdict"]["durable_cancel"] != "PASS":
                semantic_failures.append("final_cancellation_or_publication_fence_missing")
            if observation["negatives"][0]["status_code"] < 400:
                semantic_failures.append("stale_attempt_request_accepted")
            if observation["negatives"][1]["status_code"] != 403:
                semantic_failures.append("denied_permission_request_not_forbidden")
            for name, detail in observation["final"]["stale_write_results"].items():
                if detail.get("called") and detail.get("returned_normally") is True:
                    semantic_failures.append("stale_" + name + "_returned_normally")
            if observation["cancel"]["status_code"] != 200:
                semantic_failures.append("authorized_cancel_response_not_200")
            observation["case"]["semantic_failures"] = semantic_failures
            if semantic_failures:
                raise _R4ObservedSemanticError(", ".join(semantic_failures))

    except pytest.skip.Exception:
        observation["case"]["stage"] = observation["case"].get("stage") or "skipped"
        raise
    except _R4ObservedSemanticError:
        # Keep stage=complete and the actual JUnit failure for independent classification.
        raise
    except BaseException as exc:
        interrupted_stage = observation["case"].get("stage")
        observation["case"]["stage"] = "error"
        observation["errors"].append(
            {
                "stage": interrupted_stage,
                "type": type(exc).__name__,
                "message": str(exc),
            }
        )
        raise
    finally:
        if worker is not None:
            try:
                worker.stop()
            except Exception as exc:
                observation["errors"].append(
                    {
                        "stage": "worker_stop",
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
        if dispatch_thread is not None and dispatch_thread.is_alive():
            dispatch_thread.join(timeout=1.0)
        if reader is not None:
            try:
                reader.close()
            except Exception as exc:
                observation["errors"].append(
                    {
                        "stage": "reader_close",
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
        if env is not None:
            try:
                if client_lifespan_entered:
                    # `with client` already exited the secure app lifespan.
                    env["client"] = None
                close_runtime_api_env(env)
            except Exception as exc:
                observation["errors"].append(
                    {
                        "stage": "runtime_env_close",
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
        observation["native"]["forest_dr_fit_events"] = [
            event
            for event in native_events
            if event.get("kind") in {"fit_enter", "fit_return"}
            and event.get("fit_layer") == "forest_dr"
        ]
        observation["native"]["grf_tree_fit_events"] = [
            event
            for event in native_events
            if event.get("kind") in {"fit_enter", "fit_return"}
            and event.get("fit_layer") == "grf_tree"
        ]
        _save()
