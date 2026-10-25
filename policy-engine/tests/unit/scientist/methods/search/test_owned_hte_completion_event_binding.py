from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.contracts.owned_attempt_anchor import SelectedArtifactRef
from polisyos.scientist.methods.search.uncertainty import (
    SearchUncertaintyAdmissionError,
    SearchUncertaintyTicketState,
    _canonical_owned_lifecycle_event_digest_hex,
    _ref_key,
    _require_optional_artifact_ref_match,
)


def _event(
    *,
    event_id: int = 1,
    job_id: str = "job-search-owner",
    event_type: str = "job_completed",
    payload_sha256: str = "sha256:" + "a" * 64,
) -> SimpleNamespace:
    return SimpleNamespace(
        event_id=event_id,
        job_id=job_id,
        event_type=event_type,
        payload_sha256=payload_sha256,
        created_at=datetime(2026, 10, 24, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("wire_digest", "expected_hex"),
    [
        ("sha256:" + "a" * 64, "a" * 64),
        ("a" * 64, None),
        ("sha512:" + "a" * 64, None),
        ("sha256:" + "a" * 63, None),
        ("sha256:" + "A" * 64, None),
    ],
)
def test_search_receiver_digest_uses_typed_runtime_event_abi(
    wire_digest: str,
    expected_hex: str | None,
) -> None:
    """Only the canonical typed Runtime digest converts to Search's bare-hex field."""
    assert (
        _canonical_owned_lifecycle_event_digest_hex(_event(payload_sha256=wire_digest))
        == expected_hex
    )


def _owner_association_pair(
    *,
    event_id: int = 1,
    event_job_id: str = "job-search-owner",
    event_type: str = "job_completed",
    event_digest: str = "sha256:" + "a" * 64,
    successor_digest: str = "a" * 64,
) -> tuple[SimpleNamespace, SimpleNamespace]:
    refs = tuple(
        ArtifactRef(
            artifact_id=f"sha256:{index:064x}",
            kind=f"scientist.search.fixture_{index}",
            media_type="application/json",
            manifest_profile_sha256=f"sha256:{index + 100:064x}",
        )
        for index in range(1, 9)
    )
    completed_at = datetime(2026, 10, 24, tzinfo=UTC)
    event = _event(
        event_id=event_id,
        job_id=event_job_id,
        event_type=event_type,
        payload_sha256=event_digest,
    )
    event.created_at = completed_at
    association = SimpleNamespace(
        schema_version="1.0",
        status="owner_selection_reconciled",
        anchor_ref=refs[0],
        outcome_ref=refs[1],
        outcome_kind="point_estimate",
        invocation_basis_ref=None,
        refusal_diagnostic_ref=None,
        source_data_ref=refs[2],
        materialization_binding_ref=refs[3],
        search_uncertainty_task_binding_ref=refs[4],
        method_result_ref=refs[5],
        method_evidence_ref=refs[6],
        inference_basis_ref=None,
        point_result_ref=refs[7],
        hte_result_ref=None,
        job_id="job-search-owner",
        run_id="run-search-owner",
        attempt=1,
        job_completed_event=event,
    )
    successor = SimpleNamespace(
        owned_attempt_anchor_ref=refs[0],
        hte_outcome_ref=refs[1],
        invocation_basis_ref=None,
        source_data_ref=refs[2],
        materialization_binding_ref=refs[3],
        method_result_ref=refs[5],
        method_evidence_ref=refs[6],
        inference_basis_ref=None,
        point_result_ref=refs[7],
        hte_result_ref=None,
        search_uncertainty_task_binding_ref=refs[4],
        job_id="job-search-owner",
        run_id="run-search-owner",
        attempt=1,
        completed_event_id=1,
        completed_event_payload_sha256=successor_digest,
        completed_at=completed_at,
    )
    return association, successor


def test_search_owner_association_joins_canonical_digest_to_assessment_hex() -> None:
    association, successor = _owner_association_pair()
    resolved = SearchUncertaintyTicketState._verify_owned_attempt_association(
        object(),
        successor,
        owner_association=association,
    )
    assert resolved is association


@pytest.mark.parametrize(
    ("event_id", "event_job_id", "event_type", "event_digest", "successor_digest"),
    [
        (1, "job-search-owner", "job_completed", "a" * 64, "a" * 64),
        (1, "job-search-owner", "job_completed", "sha512:" + "a" * 64, "a" * 64),
        (1, "job-search-owner", "job_completed", "sha256:" + "b" * 64, "a" * 64),
        (2, "job-search-owner", "job_completed", "sha256:" + "a" * 64, "a" * 64),
        (1, "job-other", "job_completed", "sha256:" + "a" * 64, "a" * 64),
        (1, "job-search-owner", "job_failed", "sha256:" + "a" * 64, "a" * 64),
    ],
)
def test_search_owner_association_refuses_digest_or_event_identity_drift(
    event_id: int,
    event_job_id: str,
    event_type: str,
    event_digest: str,
    successor_digest: str,
) -> None:
    association, successor = _owner_association_pair(
        event_id=event_id,
        event_job_id=event_job_id,
        event_type=event_type,
        event_digest=event_digest,
        successor_digest=successor_digest,
    )
    with pytest.raises(SearchUncertaintyAdmissionError) as refused:
        SearchUncertaintyTicketState._verify_owned_attempt_association(
            object(),
            successor,
            owner_association=association,
        )
    assert refused.value.reason_code == "runtime_attempt_association_mismatch"


def test_search_optional_invocation_ref_join_allows_only_typed_optional_absence() -> None:
    """Optional absence joins only as both absent; selected ref identity stays exact."""
    _require_optional_artifact_ref_match(None, None, "invocation basis")
    ref = ArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="runtime.invocation_basis",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "2" * 64,
    )
    _require_optional_artifact_ref_match(ref, ref.model_copy(), "invocation basis")
    for left, right in (
        (ref, None),
        (None, ref),
        (
            ref,
            ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "3" * 64}),
        ),
    ):
        with pytest.raises(SearchUncertaintyAdmissionError) as refused:
            _require_optional_artifact_ref_match(left, right, "invocation basis")
        assert refused.value.reason_code == "hte_content_mismatch"


def test_search_selected_ref_identity_crosses_dto_subclasses_and_keeps_profile() -> None:
    """Core and owner-selected refs join by all four selected identity fields."""
    selected = SelectedArtifactRef(
        artifact_id="sha256:" + "4" * 64,
        kind="ir.observation_method_input",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "5" * 64,
    )
    core = ArtifactRef.model_validate(selected.model_dump(mode="python"), strict=True)
    changed_profile = core.model_copy(update={"manifest_profile_sha256": "sha256:" + "6" * 64})
    assert type(selected) is not type(core)
    assert _ref_key(selected) == _ref_key(core)
    assert _ref_key(selected) != _ref_key(changed_profile)


def test_search_bounded_json_owner_models_use_core_wire_validation(tmp_path) -> None:
    """Bounded Search reads preserve strict DTO rules while adapting Core JSON wire values."""
    import hashlib
    import json
    from copy import deepcopy
    from dataclasses import replace
    from datetime import timedelta

    from pydantic import ValidationError

    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.core.artifacts import (
        CanonInfo,
        CoreJsonReadBoundsRefusalError,
        CoreJsonReadLimits,
        FileSystemCAS,
        PutOptions,
        SchemaInfo,
        read_core_json_artifact_bounded,
        validate_core_model_bounded_read,
    )
    from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
    from polisyos.core.canon import CanonSpec, to_canonical_bytes
    from polisyos.core.contracts.bounded_liveness import BoundedLivenessConfig
    from polisyos.core.contracts.owned_attempt_anchor import (
        OWNED_ATTEMPT_ANCHOR_KIND,
        OWNED_ATTEMPT_ANCHOR_SCHEMA_NAME,
        OWNED_ATTEMPT_ANCHOR_SCHEMA_VERSION,
        OwnedAttemptAnchor,
        OwnedAttemptHTEInputAdmitted,
        OwnedAttemptHTEInputCapture,
        OwnedAttemptLifecycleEvent,
        OwnedAttemptPhysicalSourceBindingRef,
        OwnedAttemptPredicateOrigins,
        OwnedHTERequestContextV1,
        SelectedArtifactRef,
    )
    from polisyos.core.contracts.runtime import ObservationalInputResourcePolicy

    store = FileSystemCAS(tmp_path / "search-owner-json-cas")
    spec = CanonSpec(forbid_floats=False, exclude_none=False, max_depth=64)
    limits = CoreJsonReadLimits(
        max_bytes=1_048_576,
        max_depth=64,
        max_elements=100_000,
        max_manifest_bytes=65_536,
    )

    def put_json(
        payload: object,
        *,
        kind: str,
        schema: SchemaInfo | None = None,
        inputs: tuple[object, ...] = (),
        canon_spec: CanonSpec = spec,
    ) -> tuple[ArtifactRef, bytes]:
        raw = to_canonical_bytes(payload, canon_spec)
        ref = store.put_bytes(
            raw,
            PutOptions(
                kind=kind,
                media_type="application/json",
                schema=schema,
                canon=CanonInfo.from_spec(canon_spec),
                inputs=list(inputs),
            ),
            return_selected_profile=True,
        )
        assert ref.manifest_profile_sha256 is not None
        return ref, raw

    def put_selected_ref(kind: str, label: str) -> SelectedArtifactRef:
        ref, _ = put_json({"fixture": label}, kind=kind)
        return SelectedArtifactRef.model_validate(ref.model_dump(mode="python"), strict=True)

    source_ref = put_selected_ref("ir.observation_method_input", "source")
    intent_ref = put_selected_ref("runtime.observational_run_intent", "intent")
    content_intent_ref = put_selected_ref(
        "runtime.content_admitted_observational_run_intent", "content-intent"
    )
    binding_ref = put_selected_ref("scientist.search.uncertainty_task_binding", "search-binding")
    physical_core_ref, _ = put_json(
        {"fixture": "physical-binding"},
        kind="foundry.hte.physical_source_materialization_binding",
    )
    physical_ref = OwnedAttemptPhysicalSourceBindingRef.model_validate(
        physical_core_ref.model_dump(mode="python"),
        strict=True,
    )

    method_fqn = "causal.hte.causal_forest@2.0.0"
    method_profile = "econml.causal_forest_dml.native_mean@2.0"
    wait_policy = BoundedLivenessConfig().resolve(
        "runtime.observational_method_execution",
        requested_retries=0,
    )
    policy = ObservationalInputResourcePolicy(
        schema_version="polisyos.runtime.observational_input_resource_policy.v5",
        revision="r5",
        method_contract_target=(
            "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
        ),
        required_estimator_n_jobs=1,
        method_execution_wait_policy=wait_policy,
        method_fqn=method_fqn,
        method_profile_id=method_profile,
        execution_scope="producer_scoped_joblib_parallelism_one",
        max_jobs=1,
    )
    policy_ref_core, policy_raw = put_json(
        policy.model_dump(mode="json"),
        kind="runtime.observational_input_resource_policy",
        schema=SchemaInfo(
            name="polisyos.runtime.ObservationalInputResourcePolicy",
            version="1.0",
        ),
    )
    policy_ref = SelectedArtifactRef.model_validate(
        policy_ref_core.model_dump(mode="python"),
        strict=True,
    )

    request_context = OwnedHTERequestContextV1(
        request_estimand_status="declared",
        request_estimand="mean_effect_over_selected_x",
        request_target_scope_status="declared",
        request_target_scope="selected_evaluation_rows",
        outcome_variable_status="declared",
        outcome_variable_id="outcome.effect",
        treatment_variable_status="declared",
        treatment_variable_id="treatment.policy",
        contrast_status="declared",
        control_value=0.0,
        treated_value=1.0,
        request_alpha_status="declared",
        requested_alpha=0.05,
        requested_guarantee_status="declared",
        requested_guarantee="backend_conditional_interval",
        search_uncertainty_task_binding_ref=binding_ref,
        materialization_binding_ref=physical_ref,
    )
    resolved_params = {"alpha": 0.05}
    resolved_params_sha256 = hashlib.sha256(
        json.dumps(
            {"params": resolved_params, "seed": 0},
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    capture = OwnedAttemptHTEInputCapture(
        source_data_ref=source_ref,
        source_data_sha256=source_ref.artifact_id.hex,
        input_profile_id="all_source_rows_in_input_order@1.0",
        selected_input_sha256=source_ref.artifact_id.hex,
        selected_rows_sha256="a" * 64,
        selected_x_sha256="b" * 64,
        selected_row_order_sha256="c" * 64,
        fit_rows_sha256="d" * 64,
        eval_rows_sha256="d" * 64,
        fit_eval_relation="same_selected_rows",
        n_selected_rows=2,
        n_treated=1,
        n_control=1,
        n_features=2,
        source_feature_names=("age", "baseline"),
        n_confounders=0,
        sample_ids_status="not_established",
        method_fqn=method_fqn,
        method_abi="2.0.0",
        method_abi_digest="e" * 64,
        method_profile_id=method_profile,
        resolved_params_sha256=resolved_params_sha256,
        resolved_params=resolved_params,
        seed=0,
        materialization_binding_ref=physical_ref,
        request_context=request_context,
    )
    captured_at = datetime(2026, 10, 24, tzinfo=UTC)
    anchor = OwnedAttemptAnchor(
        captured_at=captured_at,
        job_id="job-search-owner-json",
        run_id="run-search-owner-json",
        tenant_id="tenant-search-owner-json",
        cell_id="cell-search-owner-json",
        attempt=1,
        worker_id="worker-search-owner-json",
        lease_expires_at=captured_at + timedelta(minutes=1),
        job_created_event=OwnedAttemptLifecycleEvent(
            event_id=1,
            job_id="job-search-owner-json",
            event_type="job_created",
            payload_sha256="sha256:" + "1" * 64,
            created_at=captured_at - timedelta(seconds=2),
        ),
        job_running_event=OwnedAttemptLifecycleEvent(
            event_id=2,
            job_id="job-search-owner-json",
            event_type="job_running",
            payload_sha256="sha256:" + "2" * 64,
            created_at=captured_at - timedelta(seconds=1),
        ),
        requested_source_ref=source_ref,
        observational_run_intent_ref=intent_ref,
        resource_policy_ref=policy_ref,
        selection_digest="3" * 64,
        source_manifest_sha256="4" * 64,
        method_fqn=method_fqn,
        method_version="2.0.0",
        method_abi_digest="e" * 64,
        method_build_digest="5" * 64,
        resource_policy_digest=policy.digest(),
        resource_policy_schema_version=policy.schema_version,
        resource_policy_revision=policy.revision,
        resource_policy_method_contract_target=policy.method_contract_target,
        resource_policy_required_estimator_n_jobs=policy.required_estimator_n_jobs,
        resource_policy_method_fqn=policy.method_fqn,
        resource_policy_method_profile_id=policy.method_profile_id,
        resource_policy_execution_scope=policy.execution_scope,
        resource_policy_max_jobs=policy.max_jobs,
        source_protocol="method_input_envelope_v1",
        resolved_params_sha256=resolved_params_sha256,
        request_context=request_context,
        input_admission=OwnedAttemptHTEInputAdmitted(
            content_admitted_intent_ref=content_intent_ref,
            submitted_input_ref=source_ref,
            effective_input_ref=source_ref,
            normalization="canonical_passthrough",
            input_capture=capture,
        ),
        predicate_origins=OwnedAttemptPredicateOrigins(
            owner_attempt_fence="recomputed",
            lifecycle_event_chain="recomputed",
            requested_source_identity="independently_reconciled",
            selected_method_abi="independently_reconciled",
            selected_resource_policy="independently_reconciled",
            resolved_params_and_seed="independently_reconciled",
            selected_input_content="recomputed",
            request_estimand="independently_reconciled",
            request_target_scope="independently_reconciled",
            outcome_variable="independently_reconciled",
            treatment_variable="independently_reconciled",
            treatment_contrast="independently_reconciled",
            requested_alpha="independently_reconciled",
            requested_guarantee="independently_reconciled",
            estimator_job_cap="independently_reconciled",
            selected_producer_job_cap="independently_reconciled",
            actual_execution_resource_context="not_established",
            search_dependency_inventory="not_established",
            completed_output_owner_association="not_established",
        ),
    )
    anchor_inputs = tuple(
        input_ref_from_artifact_ref(ref, role=role)
        for ref, role in (
            (source_ref, "requested_source"),
            (intent_ref, "observational_run_intent"),
            (content_intent_ref, "content_admitted_intent"),
            (policy_ref, "resource_policy"),
            (binding_ref, "search_uncertainty_task_binding"),
            (source_ref, "submitted_input"),
            (source_ref, "effective_input"),
            (physical_ref, "physical_source_materialization_binding"),
        )
    )
    anchor_schema = SchemaInfo(
        name=OWNED_ATTEMPT_ANCHOR_SCHEMA_NAME,
        version=OWNED_ATTEMPT_ANCHOR_SCHEMA_VERSION,
    )
    anchor_ref, anchor_raw = put_json(
        anchor.model_dump(mode="json"),
        kind=OWNED_ATTEMPT_ANCHOR_KIND,
        schema=anchor_schema,
        inputs=anchor_inputs,
    )

    anchor_read = read_core_json_artifact_bounded(store, anchor_ref, limits=limits)
    policy_read = read_core_json_artifact_bounded(store, policy_ref_core, limits=limits)
    assert isinstance(anchor_read.value["captured_at"], str)
    assert isinstance(policy_read.value["method_execution_wait_policy"]["deadline_s"], float)
    assert isinstance(
        next(
            value
            for value in (
                anchor_read.value.get("input_admission", {}).get("input_capture"),
                anchor_read.value.get("input_admission", {})
                .get("input_admitted", {})
                .get("input_capture"),
            )
            if isinstance(value, dict)
        )["source_feature_names"],
        list,
    )

    parsed_anchor = validate_core_model_bounded_read(OwnedAttemptAnchor, anchor_read)
    parsed_policy = validate_core_model_bounded_read(
        ObservationalInputResourcePolicy,
        policy_read,
    )
    assert parsed_anchor.captured_at == captured_at
    assert type(parsed_anchor.input_capture.source_feature_names) is tuple
    assert parsed_anchor.input_capture.source_feature_names == ("age", "baseline")
    assert parsed_policy == policy
    assert type(parsed_policy.method_execution_wait_policy.notes) is list

    policy_schema = SchemaInfo(
        name="polisyos.runtime.ObservationalInputResourcePolicy",
        version="1.0",
    )
    invalid_policy_payloads = []
    wrong_scalar_type = deepcopy(policy.model_dump(mode="json"))
    wrong_scalar_type["max_bytes"] = str(policy.max_bytes)
    invalid_policy_payloads.append(wrong_scalar_type)
    policy_extra_field = deepcopy(policy.model_dump(mode="json"))
    policy_extra_field["unrecognized_owner_claim"] = "must-not-be-ignored"
    invalid_policy_payloads.append(policy_extra_field)
    for invalid_policy_payload in invalid_policy_payloads:
        invalid_policy_ref, _ = put_json(
            invalid_policy_payload,
            kind="runtime.observational_input_resource_policy",
            schema=policy_schema,
        )
        invalid_policy_read = read_core_json_artifact_bounded(
            store,
            invalid_policy_ref,
            limits=limits,
        )
        with pytest.raises(ValidationError):
            validate_core_model_bounded_read(
                ObservationalInputResourcePolicy,
                invalid_policy_read,
            )

    def nested_replace(value: object, key: str, replacement: object) -> bool:
        if isinstance(value, dict):
            if key in value:
                value[key] = replacement
                return True
            return any(nested_replace(child, key, replacement) for child in value.values())
        if isinstance(value, list):
            return any(nested_replace(child, key, replacement) for child in value)
        return False

    def read_anchor_payload(payload: dict[str, object]):
        ref, raw = put_json(
            payload,
            kind=OWNED_ATTEMPT_ANCHOR_KIND,
            schema=anchor_schema,
            inputs=anchor_inputs,
        )
        return read_core_json_artifact_bounded(store, ref, limits=limits)

    malformed_names = deepcopy(anchor.model_dump(mode="json"))
    assert nested_replace(
        malformed_names,
        "source_feature_names",
        ["age", 7],
    )
    with pytest.raises(ValidationError):
        validate_core_model_bounded_read(
            OwnedAttemptAnchor,
            read_anchor_payload(malformed_names),
        )

    extra_field = deepcopy(anchor.model_dump(mode="json"))
    extra_field["unrecognized_owner_claim"] = "must-not-be-ignored"
    with pytest.raises(ValidationError):
        validate_core_model_bounded_read(
            OwnedAttemptAnchor,
            read_anchor_payload(extra_field),
        )

    alternate_profile_spec = CanonSpec(
        forbid_floats=False,
        exclude_none=False,
        max_depth=63,
    )
    alternate_ref, _ = put_json(
        anchor.model_dump(mode="json"),
        kind=OWNED_ATTEMPT_ANCHOR_KIND,
        schema=anchor_schema,
        inputs=anchor_inputs,
        canon_spec=alternate_profile_spec,
    )
    alternate_read = read_core_json_artifact_bounded(
        store,
        alternate_ref,
        limits=limits,
    )
    with pytest.raises(CanonicalProfileRefusalError) as wrong_profile:
        validate_core_model_bounded_read(
            OwnedAttemptAnchor,
            replace(anchor_read, effective_ref=alternate_read.effective_ref),
        )
    assert wrong_profile.value.code == "canon_profile_bounded_read_carrier_mismatch"

    with pytest.raises(CanonicalProfileRefusalError) as changed_bytes:
        validate_core_model_bounded_read(
            OwnedAttemptAnchor,
            replace(anchor_read, raw_payload_bytes=b"{}"),
        )
    assert changed_bytes.value.code == "canon_profile_bounded_read_carrier_mismatch"

    corrupt_store = FileSystemCAS(tmp_path / "corrupt-search-owner-json-cas")
    corrupt_ref = corrupt_store.put_bytes(
        anchor_raw,
        PutOptions(
            kind=OWNED_ATTEMPT_ANCHOR_KIND,
            media_type="application/json",
            schema=anchor_schema,
            canon=CanonInfo.from_spec(spec),
            inputs=list(anchor_inputs),
        ),
        return_selected_profile=True,
    )
    corrupt_blob, _ = corrupt_store._paths(corrupt_ref.artifact_id)
    corrupt_blob.write_bytes(b"{}")
    with pytest.raises(CoreJsonReadBoundsRefusalError) as content_refusal:
        read_core_json_artifact_bounded(
            corrupt_store,
            corrupt_ref,
            limits=limits,
        )
    assert not content_refusal.value.payload_integrity_verified
