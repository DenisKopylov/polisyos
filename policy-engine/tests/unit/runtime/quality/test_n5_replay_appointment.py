"""Real signature intake on a demonstration trust root; no replay or N5."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pydantic import BaseModel, ValidationError

from polisyos.core import artifacts, security
from polisyos.core.artifacts.signed_evidence import FileSystemSignedArtifactEvidenceRepository
from polisyos.runtime.quality import n5_replay_appointment as owner


def _digest(value: str) -> str:
    return security.raw_content_hash(value.encode())


@dataclass
class _DemonstrationTestTrustRoot:
    """Test-owned institution roles, never production configuration/authority."""

    store: artifacts.FileSystemCAS
    signers: dict[str, artifacts.Ed25519Signer]
    state: owner.N5ReplayDeploymentState
    query: owner.N5ReplayUseQuery
    appointment: owner.N5ReplayAppointment
    producer: owner.N5OriginalProducerSeal | owner.N5OriginalProducerSealV2
    now: datetime

    def resolver(self) -> owner.N5ReplayAppointmentResolver:
        return owner.N5ReplayAppointmentResolver(
            store=self.store, current_deployment=lambda: self.state, clock=lambda: self.now
        )

    def signed(self, statement: BaseModel, role: str, kind: str) -> artifacts.ArtifactRef:
        provenance = _write(self.store, role.encode(), "test.n5_replay.signer_provenance")
        profile = _write(self.store, (role + "-profile").encode(), "test.n5_replay.signing_profile")
        evidence = FileSystemSignedArtifactEvidenceRepository(self.store).persist_signed(
            blob_bytes=security.canonical_statement_bytes(statement),
            write_options=artifacts.ArtifactWriteOptions(
                kind=kind, media_type="application/octet-stream"
            ),
            signer=self.signers[role],
            signing_profile_ref=profile,
            signer_provenance_ref=provenance,
        )
        return artifacts.profile_bound_ref(self.store, evidence.evidence_record_ref)

    def install_appointment(self, appointment: owner.N5ReplayAppointment) -> None:
        appointment_evidence = self.signed(
            appointment, "issuer", "runtime.quality.n5_replay_appointment"
        )
        evidence = FileSystemSignedArtifactEvidenceRepository(self.store).read_exact(
            evidence_record_ref=appointment_evidence
        )
        appointment_ref = artifacts.artifact_ref_for_manifest(
            artifacts.ArtifactManifest.model_validate_json(evidence.exact_manifest_bytes)
        )
        check = owner.N5ReplayAppointmentVerification(
            scope=appointment.scope,
            appointment_ref=appointment_ref,
            appointment_content_hash=str(appointment_ref.artifact_id),
            current_trust_snapshot_hash=owner.n5_replay_trust_snapshot_hash(self.state.config),
            deployed_component_provenance_ref=self.state.component.component_provenance_ref,
            launcher_profile_ref=self.state.component.launcher_profile_ref,
            valid_from=self.now - timedelta(minutes=1),
            valid_until=self.now + timedelta(hours=1),
        )
        check_evidence = self.signed(
            check, "admin", "runtime.quality.n5_replay_appointment_verification"
        )
        self.state = replace(
            self.state,
            config=self.state.config.model_copy(
                update={
                    "appointment_evidence_ref": appointment_evidence,
                    "verification_evidence_ref": check_evidence,
                }
            ),
        )
        self.appointment = appointment

    def record(
        self, admission: owner.N5ReplayAppointmentResolution, **changes
    ) -> owner.N5AppointedReplayRecord:
        spec = admission.launch_spec
        payload = {
            "scope": spec.scope,
            "appointment_ref": admission.appointment_ref,
            "launch_spec_hash": security.raw_content_hash(security.canonical_statement_bytes(spec)),
            "replay_run_id": spec.replay_run_id,
            "replay_job_id": spec.replay_job_id,
            "launcher_instance_id": "demo-replay-instance",
            "numerical_intent_hash": spec.numerical_intent_hash,
            "execution_profile_ref": spec.execution_profile_ref,
            "comparator_ref": spec.comparator_ref,
            "tier": spec.tier,
            "seed_schedule_hash": spec.seed_schedule_hash,
            "attempt_number": 1,
            "planned_physical_units": spec.planned_physical_units,
            "completed_physical_units": spec.planned_physical_units,
            "outcome": "completed",
            "replay_result_projection_ref": self.producer.numerical_result_projection_ref,
            "replay_result_projection_hash": self.producer.numerical_result_projection_hash,
            "started_at": self.now - timedelta(seconds=10),
            "finished_at": self.now,
        }
        return owner.N5AppointedReplayRecord.model_validate({**payload, **changes})


def _write(store, payload: bytes, kind: str) -> artifacts.ArtifactRef:
    ref = store.put_bytes(
        payload,
        artifacts.ArtifactWriteOptions(
            kind=kind,
            media_type="application/octet-stream",
        ),
    )
    return artifacts.profile_bound_ref(store, ref)


@pytest.fixture
def demonstration_test_trust_root(tmp_path: Path) -> _DemonstrationTestTrustRoot:
    store = artifacts.FileSystemCAS(tmp_path / "demo-evidence")
    signers, keys = {}, []
    role_names = {
        "issuer": "appointment_issuer",
        "admin": "deployment_administrator",
        "launcher": "appointed_launcher",
        "producer": "original_producer",
        "user": "result_user",
    }
    for label, role in role_names.items():
        private = Ed25519PrivateKey.generate()
        signers[label] = artifacts.Ed25519Signer(private)
        public_path = tmp_path / f"demo-{label}.pub"
        public_path.write_bytes(
            private.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        )
        keys.append(
            owner.N5ReplayPublicKey(
                identity=f"demo://{label}",
                organization="demo-accepting-organization",
                function=f"demo-function-{label}",
                public_key_path=public_path,
                roles=(role,),
            )
        )
    scope = owner.N5ReplayScope(
        tenant_id="demo-tenant",
        cell_id="demo-cell",
        accepting_organization="demo-accepting-organization",
        scope_id="demo-only",
    )
    execution_profile = _write(store, b"demo actual runtime profile", "test.n5.execution_profile")
    component = owner.N5ReplayDeployedComponent(
        launcher_profile_ref=_write(store, b"demo launcher profile", "test.n5.launcher_profile"),
        execution_profile_ref=execution_profile,
        component_provenance_ref=_write(
            store, b"demo own-component build provenance", "test.n5.build_provenance"
        ),
    )
    comparator = owner.N5ReplayComparatorProfile(
        numerical_projection_schema="test.n5.numeric_projection.v1",
        excluded_time_identity_paths=("recorded_at",),
    )
    comparator_ref = store.put_json(
        comparator.model_dump(mode="json"),
        artifacts.ArtifactWriteOptions(
            kind="runtime.quality.n5_replay_comparator_profile",
            media_type="application/json",
            canon=artifacts.CanonInfo(),
        ),
        return_selected_profile=True,
    )
    now = datetime(2026, 11, 11, 12, tzinfo=UTC)
    producer = owner.N5OriginalProducerSeal(
        scope=scope,
        original_job_id="original-job",
        original_run_id="original-run",
        producer_instance_id="original-instance",
        numerical_intent_ref=_write(store, b"demo intent", "test.n5.numerical_intent"),
        numerical_intent_hash=_digest("demo intent"),
        execution_profile_ref=execution_profile,
        numerical_projection_schema=comparator.numerical_projection_schema,
        numerical_result_projection_ref=_write(
            store, b"demo numerical result", "test.n5.numerical_projection"
        ),
        numerical_result_projection_hash=_digest("demo numerical result"),
        seed_schedule_hash=_digest("demo seeds"),
        produced_at=now - timedelta(minutes=10),
    )
    appointment = owner.N5ReplayAppointment(
        scope=scope,
        launcher_identity="demo://launcher",
        launcher_key_id=signers["launcher"].key_id,
        launcher_profile_ref=component.launcher_profile_ref,
        comparator_ref=comparator_ref,
        comparator_content_hash=str(comparator_ref.artifact_id),
        supported_tiers=("STRICT_CPU", "STATISTICAL", "BEST_EFFORT_GPU"),
        allocated_capacity_units=3,
        attempt_limit=2,
        valid_from=now - timedelta(hours=1),
        valid_until=now + timedelta(hours=1),
        configured_independence="same_organization_separate_function",
    )
    config = owner.N5ReplayDeploymentConfig(
        trusted_keys=tuple(keys),
        authorized_scopes=(scope,),
        trust_root_class="demonstration_test_root",
    )
    # Construct test context before its source seal is signed; no production signing API is exposed.
    context = _DemonstrationTestTrustRoot(
        store,
        signers,
        owner.N5ReplayDeploymentState(config, component),
        None,
        appointment,
        producer,
        now,
    )
    seal = context.signed(producer, "producer", "runtime.quality.n5_original_producer_seal")
    context.query = owner.N5ReplayUseQuery(
        scope=scope,
        original_producer_evidence_ref=seal,
        execution_profile_ref=execution_profile,
        comparator_ref=comparator_ref,
        tier="STRICT_CPU",
        replay_seed_schedule_hash=producer.seed_schedule_hash,
        planned_physical_units=3,
        replay_run_id="diagnostic-run",
        replay_job_id="diagnostic-job",
    )
    context.install_appointment(appointment)
    return context


def test_empty_production_remains_unappointed_and_candidate_work_survives(
    demonstration_test_trust_root,
) -> None:
    demo = demonstration_test_trust_root
    result = owner.N5ReplayAppointmentResolver(store=demo.store).resolve(demo.query)
    assert result.status == "verifier_unappointed"
    assert result.code == "verifier_unappointed"
    assert result.candidate_work_allowed and not result.protected_use_allowed


def test_real_signed_appointment_uses_distinct_roles_and_emits_blind_spec(
    demonstration_test_trust_root,
) -> None:
    demo = demonstration_test_trust_root
    result = demo.resolver().resolve(demo.query)
    assert result.status == "appointed", result.code
    assert result.trust_root_class == "demonstration_test_root"
    assert result.configured_independence == "same_organization_separate_function"
    assert result.scientific_independence == "not_established"
    assert result.protected_use_allowed is False
    assert demo.producer.numerical_intent_hash == security.raw_content_hash(
        demo.store.get_bytes(demo.producer.numerical_intent_ref)
    )
    assert demo.producer.numerical_result_projection_hash == security.raw_content_hash(
        demo.store.get_bytes(demo.producer.numerical_result_projection_ref)
    )
    blind = result.launch_spec.model_dump(mode="json")
    assert "numerical_result_projection_ref" not in blind
    assert "numerical_result_projection_hash" not in blind
    assert "original_producer_evidence_ref" not in blind
    assert blind["invocation_purpose"] == "diagnostic"
    with pytest.raises(ValidationError):
        owner.N5BlindReplayLaunchSpec.model_validate({**blind, "original_result": "forbidden"})


@pytest.mark.parametrize(
    ("field", "kind", "payload", "code"),
    [
        (
            "numerical_intent_ref",
            "test.n5.numerical_intent",
            b"alternate signed numerical intent",
            "n5_replay_numerical_intent_content_hash_mismatch",
        ),
        (
            "numerical_result_projection_ref",
            "test.n5.numerical_projection",
            b"alternate signed numerical result",
            "n5_replay_numerical_result_content_hash_mismatch",
        ),
    ],
)
def test_resigned_producer_cannot_rebind_selected_intent_or_result_under_old_hash(
    demonstration_test_trust_root, field: str, kind: str, payload: bytes, code: str
) -> None:
    demo = demonstration_test_trust_root
    alternate_ref = _write(demo.store, payload, kind)
    producer = demo.producer.model_copy(update={field: alternate_ref})
    evidence = demo.signed(producer, "producer", "runtime.quality.n5_original_producer_seal")
    result = demo.resolver().resolve(
        demo.query.model_copy(update={"original_producer_evidence_ref": evidence})
    )
    assert result.status == "refused"
    assert result.code == code
    assert result.cache_key is None


def test_launcher_signature_is_authenticated_but_not_a_numerical_or_accounting_pass(
    demonstration_test_trust_root,
) -> None:
    demo = demonstration_test_trust_root
    admission = demo.resolver().resolve(demo.query)
    record = demo.record(admission)
    evidence = demo.signed(record, "launcher", "runtime.quality.n5_appointed_replay_record")
    result = demo.resolver().verify_launcher_record(demo.query, evidence)
    assert result.status == "authenticated_record", result.code
    assert result.physical_work_reconciled is False
    assert result.comparison_status == "not_performed"
    assert result.protected_use_allowed is False


def test_producer_copy_cannot_self_appoint_or_sign_its_replay(
    demonstration_test_trust_root,
) -> None:
    demo = demonstration_test_trust_root
    admission = demo.resolver().resolve(demo.query)
    copied = demo.record(admission)
    evidence = demo.signed(copied, "producer", "runtime.quality.n5_appointed_replay_record")
    result = demo.resolver().verify_launcher_record(demo.query, evidence)
    assert result.status == "not_established"
    assert result.code == "n5_replay_signature_untrusted_or_revoked"
    demo.state = replace(
        demo.state, config=demo.state.config.model_copy(update={"appointment_evidence_ref": None})
    )
    assert (
        demo.resolver().verify_launcher_record(demo.query, evidence).appointment.status
        == "verifier_unappointed"
    )


@pytest.mark.parametrize("role", ["issuer", "admin", "launcher", "producer"])
def test_cache_identity_never_bypasses_current_revocation(
    demonstration_test_trust_root, role: str
) -> None:
    demo = demonstration_test_trust_root
    first = demo.resolver().resolve(demo.query)
    assert first.status == "appointed"
    key = first.cache_key.content_hash
    demo.state = replace(
        demo.state,
        config=demo.state.config.model_copy(
            update={"revoked_key_ids": (demo.signers[role].key_id,)}
        ),
    )
    # The old identity remains observable, but it is not current permission.
    assert first.cache_key.content_hash == key
    result = demo.resolver().resolve(demo.query)
    assert result.status == "refused"
    assert result.protected_use_allowed is False


def test_public_key_rotation_is_observed_without_rebuilding_resolver(
    demonstration_test_trust_root,
) -> None:
    demo = demonstration_test_trust_root
    resolver = demo.resolver()
    assert resolver.resolve(demo.query).status == "appointed"
    issuer = demo.state.config.trusted_keys[0]
    replacement = (
        Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    )
    issuer.public_key_path.write_bytes(replacement)
    assert resolver.resolve(demo.query).status == "refused"


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"planned_physical_units": 4}, "n5_replay_capacity_insufficient"),
        (
            {"replay_seed_schedule_hash": _digest("other seeds"), "tier": "STATISTICAL"},
            "n5_replay_different_seed_inference_profile_not_established",
        ),
        ({"tier": "BEST_EFFORT_GPU"}, "n5_replay_tier_unsupported"),
        ({"replay_run_id": "original-run"}, "n5_replay_requires_separate_diagnostic_job"),
    ],
)
def test_unsupported_or_unfunded_replay_preparation_refuses(
    demonstration_test_trust_root, change, code: str
) -> None:
    demo = demonstration_test_trust_root
    result = demo.resolver().resolve(demo.query.model_copy(update=change))
    assert result.status == "refused"
    assert result.code == code


def test_same_seed_statistical_is_only_sampling_implementation_replay(
    demonstration_test_trust_root,
) -> None:
    demo = demonstration_test_trust_root
    result = demo.resolver().resolve(demo.query.model_copy(update={"tier": "STATISTICAL"}))
    assert result.status == "appointed"
    assert result.scientific_independence == "not_established"
    assert not result.protected_use_allowed


def test_full_comparator_profile_and_current_component_are_load_bearing(
    demonstration_test_trust_root,
) -> None:
    demo = demonstration_test_trust_root
    wrong_ref = demo.query.comparator_ref.model_copy(
        update={"manifest_profile_sha256": _digest("foreign profile")}
    )
    result = demo.resolver().resolve(demo.query.model_copy(update={"comparator_ref": wrong_ref}))
    assert result.code == "n5_replay_comparator_not_frozen"
    changed = _write(demo.store, b"other actual component", "test.n5.build_provenance")
    demo.state = replace(
        demo.state, component=replace(demo.state.component, component_provenance_ref=changed)
    )
    assert (
        demo.resolver().resolve(demo.query).code
        == "n5_replay_appointment_deployment_binding_mismatch"
    )


def test_declared_external_label_does_not_upgrade_same_organization(
    demonstration_test_trust_root,
) -> None:
    demo = demonstration_test_trust_root
    demo.install_appointment(
        demo.appointment.model_copy(update={"configured_independence": "external_organization"})
    )
    assert (
        demo.resolver().resolve(demo.query).code == "n5_replay_configured_independence_insufficient"
    )


def test_result_user_cannot_reuse_control_actor_identity_with_another_key_and_function(
    demonstration_test_trust_root,
) -> None:
    demo = demonstration_test_trust_root
    issuer = next(
        row for row in demo.state.config.trusted_keys if "appointment_issuer" in row.roles
    )
    keys = tuple(
        row.model_copy(update={"identity": issuer.identity}) if "result_user" in row.roles else row
        for row in demo.state.config.trusted_keys
    )
    demo.state = replace(
        demo.state,
        config=demo.state.config.model_copy(update={"trusted_keys": keys}),
    )
    # Reissue the administrator's check against the changed current public-trust snapshot.
    demo.install_appointment(demo.appointment.model_copy(update={"attempt_limit": 1}))
    result = demo.resolver().resolve(demo.query)
    assert result.status == "refused"
    assert result.code == "n5_replay_control_result_user_principal_overlap"


def test_changed_appointment_keeps_cache_identity_but_rechecks_admission(
    demonstration_test_trust_root,
) -> None:
    demo = demonstration_test_trust_root
    first = demo.resolver().resolve(demo.query)
    demo.install_appointment(
        demo.appointment.model_copy(update={"valid_until": demo.now + timedelta(hours=2)})
    )
    second = demo.resolver().resolve(demo.query)
    assert first.appointment_ref != second.appointment_ref
    assert first.cache_key == second.cache_key
    assert second.status == "appointed"


def test_expiry_and_attempt_limit_remain_live(demonstration_test_trust_root) -> None:
    demo = demonstration_test_trust_root
    admission = demo.resolver().resolve(demo.query)
    over_limit = demo.signed(
        demo.record(admission, attempt_number=3),
        "launcher",
        "runtime.quality.n5_appointed_replay_record",
    )
    assert (
        demo.resolver().verify_launcher_record(demo.query, over_limit).status == "not_established"
    )
    demo.now += timedelta(hours=2)
    assert (
        demo.resolver().resolve(demo.query).code == "n5_replay_appointment_expired_or_not_yet_valid"
    )


def test_public_configuration_accepts_no_institution_private_key(
    demonstration_test_trust_root,
) -> None:
    demo = demonstration_test_trust_root
    with pytest.raises(ValidationError):
        owner.N5ReplayDeploymentConfig.model_validate(
            {**demo.state.config.model_dump(), "issuer_private_key": "forbidden"}
        )


def test_current_deployment_scope_cannot_be_supplied_by_the_request(
    demonstration_test_trust_root,
) -> None:
    demo = demonstration_test_trust_root
    foreign_scope = demo.query.scope.model_copy(update={"cell_id": "unappointed-cell"})
    result = demo.resolver().resolve(demo.query.model_copy(update={"scope": foreign_scope}))
    assert result.status == "refused"
    assert result.code == "n5_replay_current_deployment_scope_unappointed"
    assert result.candidate_work_allowed and not result.protected_use_allowed


def _install_v2_intent(
    demo,
    *,
    selected_input_ref=None,
    comparator_profile=None,
    source_run_id=None,
    source_job_id=None,
):
    from polisyos.core.canon import CanonSpec
    from polisyos.runtime.quality import n5_execution_basis
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )
    from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_hash
    from polisyos.runtime.quality.n5_execution_profile import (
        N5NativeExecutionProfile,
        observe_n5_native_execution_profile,
    )
    from polisyos.runtime.quality.n5_replay_numerical_projection import (
        N5_NUMERICAL_RESULT_PROJECTION_SCHEMA,
        N5_REPLAY_EXCLUDED_TIME_IDENTITY_PATHS,
    )

    def put_core(
        kind: str,
        version: str,
        payload: object,
        *,
        schema_name: str | None = None,
        inputs: tuple[artifacts.ArtifactRef, ...] = (),
    ):
        canon_spec = CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False)
        return demo.store.put_json(
            payload,
            artifacts.ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                inputs=[
                    artifacts.input_ref_from_artifact_ref(ref, role="selected_input")
                    for ref in inputs
                ],
                schema=artifacts.SchemaInfo(name=schema_name or kind, version=version),
                canon=artifacts.CanonInfo.from_spec(canon_spec),
            ),
            canon_spec=canon_spec,
            return_selected_profile=True,
        )

    fixture_generation = getattr(demo, "_v2_intent_generation", 0) + 1
    demo._v2_intent_generation = fixture_generation
    input_ref = selected_input_ref or put_core(
        "runtime.quality.candidate_simulation_n5_input",
        "5.0",
        {
            "fixture": "synthetic selected candidate simulation V5 input",
            "generation": fixture_generation,
        },
    )
    if demo.state.component.execution_profile_ref.kind != owner.N5_REPLAY_EXECUTION_PROFILE_KIND:
        native_profile = observe_n5_native_execution_profile(
            first_party_root=Path(__file__).resolve().parents[4] / "src" / "polisyos",
            declared_settings={"fixture": "demonstration"},
        )
        profile_ref = put_core(
            owner.N5_REPLAY_EXECUTION_PROFILE_KIND,
            owner.N5_REPLAY_V1_CORE_SCHEMA_VERSION,
            native_profile.model_dump(mode="json"),
            inputs=(input_ref,),
        )
        demo.state = replace(
            demo.state,
            component=replace(demo.state.component, execution_profile_ref=profile_ref),
        )
        demo.producer = demo.producer.model_copy(update={"execution_profile_ref": profile_ref})
        demo.query = demo.query.model_copy(update={"execution_profile_ref": profile_ref})
    else:
        native_profile = artifacts.validate_core_model_json_artifact(
            N5NativeExecutionProfile,
            demo.store,
            demo.state.component.execution_profile_ref,
        )

    source_run_id = source_run_id or demo.producer.original_run_id
    source_job_id = source_job_id or demo.producer.original_job_id
    producer_run_id = f"producer-run-{fixture_generation}"
    producer_job_id = f"producer-job-{fixture_generation}"
    prepared = prepare_joint_simulation_configuration()
    prepared_ref = put_core(
        owner.N5_REPLAY_PREPARED_CONFIGURATION_KIND,
        owner.N5_REPLAY_V1_CORE_SCHEMA_VERSION,
        prepared.model_dump(mode="json"),
        inputs=(input_ref,),
    )
    prepared_hash = exact_n5_content_hash(prepared)
    # A synthetic, explicitly demonstration-only source image keeps this unit
    # test bounded; production image capture remains native child work.
    image_payload = {
        "schema_version": "N5ProductionImage@2.0",
        "source_scope": "all_first_party_production_python",
        "python_sources": [
            {
                "relative_path": "tests/fixtures/synthetic_replay_callable.py",
                "content_hash": _digest("synthetic source bytes"),
            }
        ],
        "lock_content_hash": _digest("synthetic lock bytes"),
        "platform_content": '{"fixture":"demonstration"}',
        "selected_profile_content": '{"fixture":"demonstration"}',
        "provenance": "recomputed",
        "reason_codes": [],
    }
    image = n5_execution_basis.N5ProductionImage.model_validate(
        {
            **image_payload,
            "content_hash": n5_execution_basis._v2_hash(image_payload),
        }
    )
    image_ref = put_core(
        owner.N5_REPLAY_PRODUCTION_IMAGE_KIND,
        owner.N5_REPLAY_V1_CORE_SCHEMA_VERSION,
        image.model_dump(mode="json"),
        inputs=(input_ref,),
    )
    intent_fields = {
        "selected_candidate_simulation_n5_input_ref": input_ref,
        "source_run_id": source_run_id,
        "source_job_id": source_job_id,
        "original_run_id": producer_run_id,
        "original_job_id": producer_job_id,
        "tenant_id": demo.query.scope.tenant_id,
        "cell_id": demo.query.scope.cell_id,
        "declared_numerical_intent_content_hash": _digest("captured numerical graph"),
        "declared_callable_content_hash": _digest("synthetic callable content"),
        "production_image_ref": image_ref,
        "production_image_content_hash": security.raw_content_hash(demo.store.get_bytes(image_ref)),
        "prepared_configuration_ref": prepared_ref,
        "prepared_configuration_content_hash": security.raw_content_hash(
            demo.store.get_bytes(prepared_ref)
        ),
        "prepared_configuration_hash": prepared_hash,
    }
    intent = owner.N5ReplayNumericalIntentV2.model_validate(intent_fields)
    intent_ref = put_core(
        owner.N5_REPLAY_NUMERICAL_INTENT_KIND,
        owner.N5_REPLAY_INTENT_V2_CORE_SCHEMA_VERSION,
        intent.model_dump(mode="json"),
        inputs=(input_ref,),
    )
    demo._v2_intent_ref = intent_ref
    comparator = comparator_profile or owner.N5ReplayComparatorProfile(
        numerical_projection_schema=N5_NUMERICAL_RESULT_PROJECTION_SCHEMA,
        excluded_time_identity_paths=N5_REPLAY_EXCLUDED_TIME_IDENTITY_PATHS,
    )
    comparator_ref = put_core(
        "runtime.quality.n5_replay_comparator_profile",
        "1.0",
        comparator.model_dump(mode="json"),
    )
    from polisyos.runtime.quality.n5_replay_execution import (
        N5OriginalProducerAction,
        N5OriginalProducerExecution,
    )

    original_result_ref = put_core(
        "polisyos.runtime.joint_simulation_result",
        "1.0",
        {"fixture": "demonstration-only parent result"},
    )
    ledger_snapshot_ref = _write(
        demo.store,
        b"demonstration-only ledger snapshot",
        "runtime.quality.n5_diagnostic_ledger_snapshot",
    )
    assert input_ref.kind == "runtime.quality.candidate_simulation_n5_input"
    assert input_ref.manifest_profile_sha256 is not None
    assert producer_run_id != source_run_id and producer_job_id != source_job_id
    assert original_result_ref.kind == "polisyos.runtime.joint_simulation_result"
    assert original_result_ref.manifest_profile_sha256 is not None
    assert ledger_snapshot_ref.kind == "runtime.quality.n5_diagnostic_ledger_snapshot"
    assert ledger_snapshot_ref.media_type == "application/octet-stream"
    assert ledger_snapshot_ref.manifest_profile_sha256 is not None
    action = N5OriginalProducerAction(
        source_input_ref=input_ref,
        source_run_id=source_run_id,
        source_job_id=source_job_id,
        producer_run_id=producer_run_id,
        producer_job_id=producer_job_id,
        tenant_id=demo.query.scope.tenant_id,
        cell_id=demo.query.scope.cell_id,
        cas_root="/demonstration/cas",
        ledger_path=f"/demonstration/ledger-{fixture_generation}.json",
        quota_units=1,
    )
    demo._v2_action = action
    action_ref = put_core(
        owner.N5_REPLAY_ORIGINAL_ACTION_KIND,
        owner.N5_REPLAY_ORIGINAL_ACTION_SCHEMA_VERSION,
        action.model_dump(mode="json"),
        schema_name=owner.N5_REPLAY_ORIGINAL_ACTION_SCHEMA_NAME,
        inputs=(input_ref,),
    )
    action_hash = security.raw_content_hash(demo.store.get_bytes(action_ref))
    execution = N5OriginalProducerExecution(
        source_input_ref=input_ref,
        source_run_id=source_run_id,
        source_job_id=source_job_id,
        producer_run_id=producer_run_id,
        producer_job_id=producer_job_id,
        tenant_id=demo.query.scope.tenant_id,
        cell_id=demo.query.scope.cell_id,
        pid=1,
        action_hash=action_hash,
        action_ref=action_ref,
        result_ref=original_result_ref,
        numerical_intent_ref=intent_ref,
        execution_profile_ref=demo.state.component.execution_profile_ref,
        ledger_owner=("demonstration", "owner", "candidate"),
        ledger_revision=1,
        ledger_hash=security.raw_content_hash(demo.store.get_bytes(ledger_snapshot_ref)),
        ledger_snapshot_ref=ledger_snapshot_ref,
        operation_ids=(f"demo-operation-{fixture_generation}",),
    )
    demo._v2_execution = execution
    execution_ref = put_core(
        owner.N5_REPLAY_ORIGINAL_EXECUTION_KIND,
        owner.N5_REPLAY_ORIGINAL_EXECUTION_SCHEMA_VERSION,
        execution.model_dump(mode="json"),
    )
    seal_fields = demo.producer.model_dump(mode="python")
    seal_fields.update(
        {
            "schema_version": "policyos.n5_replay.producer_seal.v2",
            "original_run_id": producer_run_id,
            "original_job_id": producer_job_id,
            "original_execution_ref": execution_ref,
            "numerical_intent_ref": intent_ref,
            "numerical_intent_hash": security.raw_content_hash(demo.store.get_bytes(intent_ref)),
            "numerical_projection_schema": N5_NUMERICAL_RESULT_PROJECTION_SCHEMA,
        }
    )
    demo.producer = owner.N5OriginalProducerSealV2.model_validate(seal_fields)
    producer_ref = demo.signed(
        demo.producer, "producer", "runtime.quality.n5_original_producer_seal"
    )
    demo.query = demo.query.model_copy(
        update={"original_producer_evidence_ref": producer_ref, "comparator_ref": comparator_ref}
    )
    demo.install_appointment(
        demo.appointment.model_copy(
            update={
                "comparator_ref": comparator_ref,
                "comparator_content_hash": str(comparator_ref.artifact_id),
                "attempt_limit": demo.appointment.attempt_limit + 1,
            }
        )
    )
    return input_ref, intent, native_profile, image


def test_v2_executable_intake_resolves_selected_cas_and_emits_result_blind_spec(
    demonstration_test_trust_root,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality import n5_replay_execution
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationN5InputV5
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    demo = demonstration_test_trust_root
    input_ref, intent, _native_profile, _image = _install_v2_intent(
        demo, source_run_id="source-input-run", source_job_id="source-input-job"
    )
    record = CandidateSimulationN5InputV5.model_construct(
        authority_purpose="candidate_scenario_n5_only",
        run_id=intent.source_run_id,
        job_id=intent.source_job_id,
        tenant_id=intent.tenant_id,
        cell_id=intent.cell_id,
    )
    calls = []

    def resolve(repository, **kwargs):
        calls.append((repository.store, kwargs))
        return record

    monkeypatch.setattr(GenerationSourceRepository, "resolve_candidate_simulation_v5", resolve)
    original_reopens = []

    def reopen_original(**kwargs):
        original_reopens.append(kwargs)
        return demo._v2_execution, None, None

    monkeypatch.setattr(
        n5_replay_execution,
        "_reopen_verified_original",
        reopen_original,
    )
    result = demo.resolver().resolve_executable(demo.query)
    assert result.status == "appointed", result.code
    assert result.launch_spec is not None
    assert calls == [
        (
            demo.store,
            {
                "ref": input_ref,
                "expected_run_id": intent.source_run_id,
                "expected_job_id": intent.source_job_id,
                "expected_tenant_id": intent.tenant_id,
                "expected_cell_id": intent.cell_id,
            },
        )
    ]
    assert original_reopens == [
        {
            "store": demo.store,
            "original_execution_ref": demo.producer.original_execution_ref,
            "scope": demo.query.scope,
        }
    ]
    child = result.launch_spec.model_dump(mode="json")
    assert child["selected_candidate_simulation_n5_input_ref"] == input_ref.model_dump(mode="json")
    assert child["source_run_id"] == "source-input-run"
    assert child["source_job_id"] == "source-input-job"
    assert child["original_run_id"] != child["source_run_id"]
    assert child["original_job_id"] != child["source_job_id"]
    assert "original_producer_evidence_ref" not in child
    assert "original_execution_ref" not in child
    assert "action_ref" not in child
    assert "result_ref" not in child
    assert "numerical_result_projection_ref" not in child
    assert "numerical_result_projection_hash" not in child
    assert child["invocation_purpose"] == "diagnostic"
    for ref in (
        demo._v2_intent_ref,
        intent.production_image_ref,
        intent.prepared_configuration_ref,
        demo.state.component.execution_profile_ref,
    ):
        manifest, _ = artifacts.read_core_manifest_profile(demo.store, ref)
        assert [(item.artifact_id, item.role) for item in manifest.inputs] == [
            (input_ref.artifact_id, "selected_input")
        ]
    intent_payload = intent.model_dump(mode="json")
    assert (
        not {
            "original_execution_ref",
            "result_ref",
            "numerical_result_projection_ref",
            "producer_seal_ref",
        }
        & intent_payload.keys()
    )
    with pytest.raises(ValidationError):
        owner.N5BlindReplayLaunchSpecV2.model_validate(
            {
                **child,
                "numerical_result_projection_ref": demo.producer.numerical_result_projection_ref,
            }
        )
    with pytest.raises(ValidationError):
        owner.N5BlindReplayLaunchSpecV2.model_validate(
            {**child, "replay_run_id": child["source_run_id"]}
        )


def test_v1_or_corrupt_selected_input_never_reaches_executable_intake(
    demonstration_test_trust_root,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    demo = demonstration_test_trust_root
    # The preserved v1 opaque intent still supports read-only appointment intake.
    assert demo.resolver().resolve(demo.query).status == "appointed"
    result = demo.resolver().resolve_executable(demo.query)
    assert result.status == "refused"
    assert result.launch_spec is None

    input_ref, intent, _native_profile, _image = _install_v2_intent(demo)
    corrupted_ref = input_ref.model_copy(update={"artifact_id": _digest("foreign input")})
    _install_v2_intent(demo, selected_input_ref=corrupted_ref)
    called = False

    def forbidden_resolve(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("invalid selected CAS view reached source owner")

    monkeypatch.setattr(
        GenerationSourceRepository, "resolve_candidate_simulation_v5", forbidden_resolve
    )
    result = demo.resolver().resolve_executable(demo.query)
    assert result.status == "refused"
    assert result.code == "n5_replay_selected_candidate_input_unavailable"
    assert not called
    assert intent.selected_candidate_simulation_n5_input_ref == input_ref

    unknown_version = intent.model_copy(
        update={"schema_version": "policyos.n5_replay.numerical_intent.v3"}
    )
    from polisyos.core.canon import CanonSpec

    canon_spec = CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False)
    unknown_ref = demo.store.put_json(
        unknown_version.model_dump(mode="json"),
        artifacts.ArtifactWriteOptions(
            kind=owner.N5_REPLAY_NUMERICAL_INTENT_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=owner.N5_REPLAY_NUMERICAL_INTENT_KIND,
                version=owner.N5_REPLAY_INTENT_V2_CORE_SCHEMA_VERSION,
            ),
            canon=artifacts.CanonInfo.from_spec(canon_spec),
        ),
        canon_spec=canon_spec,
        return_selected_profile=True,
    )
    unknown_bytes = demo.store.get_bytes(unknown_ref)
    producer = demo.producer.model_copy(
        update={
            "numerical_intent_ref": unknown_ref,
            "numerical_intent_hash": security.raw_content_hash(unknown_bytes),
        }
    )
    producer_ref = demo.signed(producer, "producer", "runtime.quality.n5_original_producer_seal")
    demo.query = demo.query.model_copy(update={"original_producer_evidence_ref": producer_ref})
    malformed = demo.resolver().resolve_executable(demo.query)
    assert malformed.status == "refused"
    assert malformed.launch_spec is None
    assert not called


def test_v2_seal_rejects_mismatched_parent_execution_bindings(
    demonstration_test_trust_root,
) -> None:
    from polisyos.core.canon import CanonSpec

    demo = demonstration_test_trust_root
    _input_ref, _intent, _native_profile, _image = _install_v2_intent(demo)
    execution = demo._v2_execution
    canon_spec = CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False)

    def persist_execution(execution_record):
        return demo.store.put_json(
            execution_record.model_dump(mode="json"),
            artifacts.ArtifactWriteOptions(
                kind=owner.N5_REPLAY_ORIGINAL_EXECUTION_KIND,
                media_type="application/json",
                schema=artifacts.SchemaInfo(
                    name=owner.N5_REPLAY_ORIGINAL_EXECUTION_KIND,
                    version=owner.N5_REPLAY_ORIGINAL_EXECUTION_SCHEMA_VERSION,
                ),
                canon=artifacts.CanonInfo.from_spec(canon_spec),
            ),
            canon_spec=canon_spec,
            return_selected_profile=True,
        )

    for execution_record, expected_code in (
        (
            execution.model_copy(
                update={
                    "producer_run_id": "different-producer-run",
                    "producer_job_id": "different-producer-job",
                }
            ),
            "n5_replay_original_execution_binding_mismatch",
        ),
        (
            execution.model_copy(
                update={
                    "numerical_intent_ref": demo.producer.numerical_intent_ref.model_copy(
                        update={"manifest_profile_sha256": _digest("wrong intent profile")}
                    )
                }
            ),
            "n5_replay_original_execution_binding_mismatch",
        ),
        (
            execution.model_copy(
                update={
                    "execution_profile_ref": demo.producer.execution_profile_ref.model_copy(
                        update={"manifest_profile_sha256": _digest("wrong runtime profile")}
                    )
                }
            ),
            "n5_replay_original_execution_binding_mismatch",
        ),
        (
            execution.model_copy(update={"action_hash": _digest("wrong action bytes")}),
            "n5_replay_original_action_binding_mismatch",
        ),
        (
            execution.model_copy(update={"ledger_hash": _digest("wrong ledger bytes")}),
            "n5_replay_original_ledger_snapshot_mismatch",
        ),
    ):
        execution_ref = persist_execution(execution_record)
        seal = demo.producer.model_copy(update={"original_execution_ref": execution_ref})
        evidence = demo.signed(seal, "producer", "runtime.quality.n5_original_producer_seal")
        demo.query = demo.query.model_copy(update={"original_producer_evidence_ref": evidence})

        result = demo.resolver().resolve_executable(demo.query)

        assert result.status == "refused"
        assert result.code == expected_code
        assert result.launch_spec is None


def test_v2_intent_wrong_scope_and_unsupported_comparator_fail_closed(
    demonstration_test_trust_root,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationN5InputV5
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.n5_replay_numerical_projection import (
        N5_NUMERICAL_RESULT_PROJECTION_SCHEMA,
    )

    demo = demonstration_test_trust_root
    _input_ref, intent, _native_profile, _image = _install_v2_intent(demo)
    mismatched_record = CandidateSimulationN5InputV5.model_construct(
        authority_purpose="candidate_scenario_n5_only",
        run_id=intent.source_run_id,
        job_id=intent.source_job_id,
        tenant_id=demo.query.scope.tenant_id,
        cell_id="foreign-cell",
    )
    monkeypatch.setattr(
        GenerationSourceRepository,
        "resolve_candidate_simulation_v5",
        lambda *_args, **_kwargs: mismatched_record,
    )
    wrong_scope = demo.resolver().resolve_executable(demo.query)
    assert wrong_scope.status == "refused"
    assert wrong_scope.code == "n5_replay_selected_candidate_input_not_established"

    unsupported = owner.N5ReplayComparatorProfile(
        numerical_projection_schema=N5_NUMERICAL_RESULT_PROJECTION_SCHEMA,
        excluded_time_identity_paths=("caller.selected.path",),
    )
    _input_ref, intent, _native_profile, _image = _install_v2_intent(
        demo, comparator_profile=unsupported
    )
    matching_record = CandidateSimulationN5InputV5.model_construct(
        authority_purpose="candidate_scenario_n5_only",
        run_id=intent.source_run_id,
        job_id=intent.source_job_id,
        tenant_id=demo.query.scope.tenant_id,
        cell_id=demo.query.scope.cell_id,
    )
    monkeypatch.setattr(
        GenerationSourceRepository,
        "resolve_candidate_simulation_v5",
        lambda *_args, **_kwargs: matching_record,
    )
    wrong_comparator = demo.resolver().resolve_executable(demo.query)
    assert wrong_comparator.status == "refused"
    assert wrong_comparator.code == "n5_replay_comparator_not_established"


def test_v2_cache_key_uses_recomputed_numerical_identity_axes_only(
    demonstration_test_trust_root,
) -> None:
    demo = demonstration_test_trust_root
    _input_ref, intent, native_profile, image = _install_v2_intent(demo)
    build_key = owner.build_n5_replay_verification_cache_key_v2
    fixed = {
        "declared_numerical_intent_content_hash": intent.declared_numerical_intent_content_hash,
        "declared_callable_content_hash": intent.declared_callable_content_hash,
        "native_profile": native_profile,
        "production_image": image,
        "comparator_ref": demo.query.comparator_ref,
        "tier": demo.query.tier,
        "seed_schedule_hash": _digest("ordered actual replay seeds"),
        "numerical_result_projection_hash": demo.producer.numerical_result_projection_hash,
    }
    baseline = build_key(**fixed)
    # Appointment, source ref, run/job labels, and allocation never enter the key.
    assert set(baseline.model_fields_set) == {
        "declared_numerical_intent_content_hash",
        "declared_callable_content_hash",
        "numerical_profile_content_hash",
        "production_image_content_hash",
        "comparator_ref",
        "comparator_content_hash",
        "tier",
        "seed_schedule_hash",
        "numerical_result_projection_hash",
    }
    assert build_key(**fixed) == baseline
    changed_intent = build_key(
        **{
            **fixed,
            "declared_numerical_intent_content_hash": _digest("different numerical graph"),
        }
    )
    changed_result = build_key(
        **{
            **fixed,
            "numerical_result_projection_hash": _digest("different original projection"),
        }
    )
    assert changed_intent != baseline
    assert changed_result != baseline
