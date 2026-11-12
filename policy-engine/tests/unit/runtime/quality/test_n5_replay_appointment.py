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
    producer: owner.N5OriginalProducerSeal
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
    issuer = next(row for row in demo.state.config.trusted_keys if "appointment_issuer" in row.roles)
    keys = tuple(
        row.model_copy(update={"identity": issuer.identity})
        if "result_user" in row.roles
        else row
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
