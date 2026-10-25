from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import cast

import pytest

from polisyos.core import components as core_components
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.pdc import ArtifactRef as EvalSafetyArtifactRef
from polisyos.pdc import EvaluationInputProvenance
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import RuntimeContainerOverrides
from polisyos.runtime.http.services.control.evaluation_safety import (
    EvaluationSafetyAttemptAuthorities,
    EvaluationSafetyAuthoritiesSourceRefusalError,
)
from polisyos.runtime.quality.evaluation_modes import resolve_evaluation_mode
from polisyos.runtime.quality.evaluation_safety import (
    EVALUATION_SAFETY_ARTIFACT_IDENTITIES,
    EvalSafetyAppointmentResolution,
    EvalSafetyAuthorityResolution,
    EvalSafetyAuthorityResolver,
    EvalSafetyVerifierAppointmentResolver,
    EvalSafetyVerifierRegistry,
    EvaluationAttemptIntake,
    EvaluationAttemptRequest,
)
from tests._helpers.runtime_http import (
    _build_control_service,
    build_runtime_api_env,
    close_runtime_api_env,
)


class _NeverAuthorityResolver:
    def resolve(self, artifact_ref: EvalSafetyArtifactRef) -> EvalSafetyAuthorityResolution:
        raise AssertionError("source refusal must precede authority resolution")


class _NeverAppointmentResolver:
    def resolve(self, appointment_ref: EvalSafetyArtifactRef) -> EvalSafetyAppointmentResolution:
        raise AssertionError("source refusal must precede appointment resolution")


class _NeverVerifierRegistry:
    def resolve(self, evidence_contract_id: str) -> None:
        raise AssertionError("source refusal must precede verifier lookup")


class _RefusingAuthoritiesSource:
    """Test-only source that refuses present selection; it makes no authority claim."""

    def __init__(self) -> None:
        self.authority_resolver: EvalSafetyAuthorityResolver = _NeverAuthorityResolver()
        self.appointment_resolver: EvalSafetyVerifierAppointmentResolver = (
            _NeverAppointmentResolver()
        )
        self.verifier_registry: EvalSafetyVerifierRegistry = _NeverVerifierRegistry()
        self.selected_pack_refs: list[EvalSafetyArtifactRef] = []
        self.called = Event()

    def resolve_for_attempt(
        self,
        *,
        artifact_store: ArtifactStore,
        intake: EvaluationAttemptIntake,
    ) -> EvaluationSafetyAttemptAuthorities:
        del artifact_store
        assert intake.domain_pack_ref is not None
        self.selected_pack_refs.append(intake.domain_pack_ref)
        self.called.set()
        raise EvaluationSafetyAuthoritiesSourceRefusalError(
            "evaluation_safety_test_owner_profile_not_admitted",
            "The test source deliberately refuses an unsupported selected profile.",
        )

    def resolve_for_replay(
        self,
        *,
        artifact_store: ArtifactStore,
        intake_ref: EvalSafetyArtifactRef,
        intake: EvaluationAttemptIntake,
        request_ref: EvalSafetyArtifactRef,
        request: EvaluationAttemptRequest,
    ) -> EvaluationSafetyAttemptAuthorities:
        del artifact_store, intake_ref, intake, request_ref, request
        raise AssertionError("a refused attempt must not reach source replay")


def _ref(value: str, kind: str) -> EvalSafetyArtifactRef:
    return EvalSafetyArtifactRef(
        artifact_id=value,
        artifact_type=kind,
        content_hash=value,
        schema_ref=f"{kind}.v1",
        uri=f"cas://sha256/{value.removeprefix('sha256:')}",
        version="1.0",
    )


def _unestablished_intake(data_ref: str) -> EvaluationAttemptIntake:
    input_ref = _ref(data_ref, "test.input")
    now = datetime.now(UTC)
    return EvaluationAttemptIntake(
        attempt_id="attempt-source-refusal",
        evaluator_owner_id=core_components.ComponentId(
            "polisyos.runtime.quality.foundry_value_port@1.0.0"
        ),
        design_problem_ref="sha256:" + "0" * 64,
        candidate_ref=_ref("sha256:" + "1" * 64, "test.candidate"),
        world_model_record_ref=_ref("sha256:" + "2" * 64, "test.world-model"),
        requested_mode_token="field_pilot",  # noqa: S106
        mode_resolution=resolve_evaluation_mode("field_pilot"),
        domain_hint="controlled-source-refusal",
        domain_pack_ref=_ref("sha256:" + "9" * 64, "test.eval-safety-pack"),
        target_population_scope_ref=_ref("sha256:" + "3" * 64, "test.population"),
        evaluation_input_refs=(input_ref,),
        evaluation_input_provenance=(
            EvaluationInputProvenance(
                input_ref=input_ref,
                input_class="not_established",
                predicate_provenance="not_established",
            ),
        ),
        evidence_refs=(),
        requested_at=now,
        intended_start_at=now,
        requested_rule_version="policyos.runtime.eval-safety.v1",
        external_executor_identity_ref=None,
    )


@pytest.mark.integration
def test_present_unadmitted_source_refuses_through_http_worker_and_fresh_get(
    tmp_path: Path,
    pytestconfig: pytest.Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A present source refusal stays distinct from absent C01 authority material."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv(
        "POLISYOS_CONTROL_SQLITE_PATH",
        (tmp_path / "control.sqlite3").as_posix(),
    )
    source = _RefusingAuthoritiesSource()
    env = build_runtime_api_env(
        tmp_path,
        app_kwargs={
            "repo_root": Path(pytestconfig.rootpath).resolve(strict=True),
            "container_overrides": RuntimeContainerOverrides(
                evaluation_safety_authorities_source=source
            ),
        },
    )
    client = cast("TestClient", env["client"])
    app = env["app"]
    try:
        with client:
            launch = client.post(
                "/api/v1/control/runs",
                json={
                    "data_source": {
                        "data_snapshot_ref": env["data_snapshot_artifact_id"],
                    },
                    "params": {
                        "evaluation_safety_attempt": _unestablished_intake(
                            str(env["data_snapshot_artifact_id"])
                        ).model_dump(mode="json"),
                    },
                },
            )
            assert launch.status_code == 200, launch.text
            job_id = launch.json()["job_id"]
            assert source.called.wait(10.0), "embedded worker did not resolve the selected source"
            deadline = time.monotonic() + 10.0
            fresh = client.get(f"/api/v1/control/jobs/{job_id}")
            while fresh.status_code == 200 and fresh.json()["state"] in {"pending", "running"}:
                if time.monotonic() >= deadline:
                    raise TimeoutError("typed source refusal did not reach terminal job state")
                time.sleep(0.05)
                fresh = client.get(f"/api/v1/control/jobs/{job_id}")
            assert fresh.status_code == 200, fresh.text
            body = fresh.json()
            assert body["state"] == "failed"
            assert "evaluation_safety_test_owner_profile_not_admitted" in body["error_message"]
            assert len(source.selected_pack_refs) == 1
            assert source.selected_pack_refs[0].content_hash == "sha256:" + "9" * 64
            service = app.state._control_service
            decision_kind = EVALUATION_SAFETY_ARTIFACT_IDENTITIES["decision"].kind
            decision_ids = tuple(
                artifact_id
                for artifact_id in service._artifact_store.iter_artifact_ids()
                if service._artifact_store.get_manifest(artifact_id).kind == decision_kind
            )
            assert decision_ids == ()
    finally:
        close_runtime_api_env(env)


@pytest.mark.integration
@pytest.mark.parametrize("prebuilt_has_same_source", [False, True])
def test_container_rejects_source_override_with_prebuilt_control_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prebuilt_has_same_source: bool,
) -> None:
    """Reject dropped source config through the supported app/container composition."""
    pytest.importorskip("fastapi")
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    source = _RefusingAuthoritiesSource()
    service = _build_control_service(
        tmp_path,
        evaluation_safety_authorities_source=source if prebuilt_has_same_source else None,
    )
    try:
        with pytest.raises(
            ValueError,
            match="evaluation_safety_authorities_source_conflicts_with_prebuilt_control_service",
        ):
            create_runtime_api_app(
                cas_root=tmp_path / "container-cas",
                core_runs_root=tmp_path / "container-runs",
                allow_fixture_identity=True,
                container_overrides=RuntimeContainerOverrides(
                    control_service=service,
                    evaluation_safety_authorities_source=source,
                ),
            )
        assert not source.called.is_set()
    finally:
        service.close()
