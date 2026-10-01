from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from polisyos.core import artifacts, canon
from polisyos.runtime.quality import generation_cycle as n6
from polisyos.runtime.quality.design_axes import value_choice_provenance as s8
from polisyos.runtime.quality.open_world_risk import PromotionRuntime
from tests.unit.runtime.quality.test_design_axes_value_choice_provenance import (
    NOW,
    RULE_VERSION_REF,
    _authority_boundary,
    _authorized_schedule_payload,
    _guarded_signature_verifier,
    _pareto_archive_payload,
)
from tests.unit.runtime.quality.test_generation_cycle import (
    REPO_ROOT,
    _AlwaysLowGrounding,
    _budget,
    _CounterexampleAwareGenerator,
    _CurrentValidGrounding,
    _problem,
)


class _N6DispositionController(n6.GenerationCycleController):
    def __init__(self, *, disposition: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._disposition = disposition

    def decide_next_action(self, **kwargs: Any) -> Any:
        decision = super().decide_next_action(**kwargs)
        return decision.model_copy(
            update={
                "next_action": self._disposition,
                "reason": f"r11_direct_n6_{self._disposition}",
            }
        )


async def _source_root(tmp_path: Path) -> Path:
    """Create an isolated output root with the current product source read-only by convention."""
    root = tmp_path / "n6-source-root"
    source_dir = root / "src"
    source_dir.mkdir(parents=True)
    source_link = source_dir / "polisyos"
    os.symlink(REPO_ROOT / "src" / "polisyos", source_link, target_is_directory=True)
    return root


def _put_signed(
    store: artifacts.FileSystemCAS,
    payload: object,
    *,
    kind: str,
    schema: str,
    key: artifacts.KeyPair,
    identity: str,
) -> str:
    ref = store.put_json(
        payload,
        artifacts.PutOptions(
            kind=kind,
            media_type="application/json",
            schema=artifacts.SchemaInfo(name=kind, version=schema),
        ),
    )
    store.sign_artifact(
        ref.artifact_id,
        artifacts.Ed25519Signer(key.private_key),
        signer_identity=identity,
    )
    return str(ref.artifact_id)


def _identity_current_test_run(
    run: n6.GenerationCycleRun,
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> n6.GenerationCycleRun:
    """Inject a typed currentness observation to isolate consumer behavior."""

    source_root = tmp_path / "passing-source-census"
    source = source_root / "src/polisyos/minimal.py"
    source.parent.mkdir(parents=True)
    source.write_text("def candidate_source():\n    return None\n", encoding="utf-8")
    receipt = n6.StrangleReceipt.recompute(source_root)
    assert receipt.status == "strangled"
    identity = "policy-engine-deployment:sha256:" + "a" * 64
    currentness = n6.N6DeploymentCurrentnessObservation(
        status="current",
        census_verdict="PASS",
        recorded_identity_status="established",
        recorded_deployment_identity=identity,
        loaded_identity_status="established",
        loaded_deployment_identity=identity,
        reason_code="n6_currentness_established",
        unresolved_by_construction=(),
    )
    monkeypatch.setattr(
        n6, "observe_n6_deployment_currentness", lambda **_kwargs: currentness
    )
    return run.model_copy(
        update={
            "strangle_receipt": receipt,
            "deployment_identity_status": "established",
            "deployment_identity": identity,
            "deployment_identity_reason": None,
        }
    )


def _track_currentness_observations(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, object]]:
    """Record the ledger observations made by each consumer's strict validator."""

    original = n6.observe_n6_deployment_currentness
    observed: list[dict[str, object]] = []

    def record(**kwargs: Any) -> n6.N6DeploymentCurrentnessObservation:
        observed.append(dict(kwargs))
        return original(**kwargs)

    monkeypatch.setattr(n6, "observe_n6_deployment_currentness", record)
    return observed


async def _owner_source_harness(
    tmp_path: Path,
    *,
    disposition: str,
    runtime_source_store: bool = False,
    identity_current: bool = False,
    historical_v1_source: bool = False,
    historical_v1_terminal_blocked: bool = False,
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> dict[str, Any]:
    """Persist an N6 source and bind real signed S8 evidence to its exact ref."""
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    source_root: Path | None
    source_payload: dict[str, Any]
    problem = None
    if historical_v1_source:
        if runtime_source_store or identity_current:
            raise AssertionError("historical-v1-source-conflicts-with-current-source-options")
        if historical_v1_terminal_blocked:
            from tests.unit.runtime.quality.historical_artifacts import (
                historical_generation_cycle_v1,
            )

            source_payload = historical_generation_cycle_v1()["generation_cycle_run"]
            blocked_reason = "explicit_voi_block"
            source_payload["terminal_status"] = "blocked"
            source_payload["blocked_reason"] = blocked_reason
            final_cycle = source_payload["cycles"][-1]
            final_cycle["voi_decision"].update({"next_action": "blocked", "reason": blocked_reason})
            final_cycle["refinement_decision"].update(
                {"decision": "block_candidate", "reason": blocked_reason}
            )
            final_cycle["search_iteration"]["status"] = "blocked_no_retry"
            source_payload["promotion_port"].update(
                {
                    "status": "not_promoted",
                    "reason": f"generation_cycle_blocked_before_n9:{blocked_reason}",
                    "certified_candidate_ids": [],
                    "receipts": [],
                    "strangle_receipt": None,
                    "pre_n9_open_world_gates": [],
                }
            )
            run = n6.GenerationCycleRun.model_validate(source_payload)
            source_payload = run.model_dump(mode="json")
            run = n6.GenerationCycleRun.model_validate(source_payload)
            assert n6.validate_generation_cycle_run_history(source_payload) == ()
            assert run.terminal_status == "blocked"
            source_root = None
        else:
            from tests.unit.runtime.quality.historical_artifacts import (
                historical_generation_cycle_v1,
            )

            source_payload = historical_generation_cycle_v1()["generation_cycle_run"]
            run = n6.GenerationCycleRun.model_validate(source_payload)
            assert run.terminal_status == "completed"
            source_root = None
        source_root = None
    else:
        source_root = await _source_root(tmp_path)
        grounding = _AlwaysLowGrounding() if disposition == "blocked" else _CurrentValidGrounding()
        promotion_runtime = PromotionRuntime(store=store) if runtime_source_store else None
        controller = _N6DispositionController(
            disposition=disposition,
            generation_port=_CounterexampleAwareGenerator(),
            grounding_port=grounding,
            value_port=n6.PendingN8ValuePort(),
            repo_root=source_root,
            promotion_runtime=promotion_runtime,
        )
        problem = _problem(f"r11_direct_s8_{disposition}")
        run = await controller.run(
            problem,
            budget_state=_budget(),
            min_cycles=2,
            max_cycles=3,
        )
        assert run.terminal_status == ("blocked" if disposition == "blocked" else "completed")
        if identity_current:
            if monkeypatch is None:
                raise AssertionError("identity-current fixture requires the currentness test seam")
            run = _identity_current_test_run(run, tmp_path=tmp_path, monkeypatch=monkeypatch)
        if runtime_source_store:
            assert n6.validate_generation_cycle_run(run, repo_root=source_root) == ()
        else:
            assert run.source_custody_limitation is not None
            assert run.source_custody_limitation.reason_code == "source_store_unavailable"
        source_payload = run.model_dump(mode="json")

    source_ref = str(
        store.put_json(
            source_payload,
            artifacts.PutOptions(
                kind=s8.NORMATIVE_GENERATION_SOURCE_KIND,
                media_type="application/json",
                schema=artifacts.SchemaInfo(
                    name=s8.NORMATIVE_GENERATION_SOURCE_KIND,
                    version=run.schema_version,
                ),
            ),
            canon_spec=canon.CanonSpec(forbid_floats=False),
        ).artifact_id
    )
    case_id = run.cycles[0].revision_request.revised_problem.design_problem_id
    candidate_ids = tuple(
        candidate_id
        for ids in run.fronts.candidate_ids_by_front().values()
        for candidate_id in ids
    )
    assert candidate_ids
    selected = candidate_ids[0]
    binding = s8.NormativeGenerationBinding(
        compiled_run_ref="sha256:" + "a" * 64,
        source_run_ref=source_ref,
        node_ref=f"r11-direct-n6:{disposition}",
    )

    claimant_key, authorizer_key = artifacts.KeyPair.generate(), artifacts.KeyPair.generate()
    claimant = "claimant://r11-direct-n6"
    authorizer = "principal://ua/ministry-of-economy"
    scope = "value-scope://r11-direct-n6"
    mandate = "pdc://layer2/s6/ua-msme/mandate-legitimacy"
    schedule = s8.build_authorized_value_schedule(
        **_authorized_schedule_payload(
            case_id=case_id,
            principal_refs=[authorizer],
            schedule_ref=f"pdc://value-schedule/{uuid4().hex}",
        )
    )
    schedule_ref = _put_signed(
        store,
        schedule.model_dump(mode="json"),
        kind=s8.NORMATIVE_SCHEDULE_KIND,
        schema=s8.LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION,
        key=claimant_key,
        identity=claimant,
    )
    frontier = s8.build_pareto_archive(
        **_pareto_archive_payload(
            case_id=case_id,
            frontier_refs=[source_ref],
            nondominated_alternative_ids=[selected],
            rejected_nondominated_alternative_ids=[],
            value_schedule_ref=None,
            ranking_mode="unranked_frontier_only",
            archive_status="frontier_available",
            authority_boundary=_authority_boundary(
                authoritative_for=["candidate_value_disclosure"]
            ),
        )
    )
    frontier_ref = _put_signed(
        store,
        frontier.model_dump(mode="json"),
        kind=s8.NORMATIVE_FRONTIER_KIND,
        schema=s8.LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION,
        key=claimant_key,
        identity=claimant,
    )
    authorization = s8.NormativeAuthorizationRecordV2(
        authorizer_identity=authorizer,
        authority_purpose="value_schedule_for_ranking",
        case_id=case_id,
        scope_ref=scope,
        mandate_ref=mandate,
        decision_class_id="value_authorization",
        decision_role="principal",
        source_schedule_ref=schedule_ref,
        frontier_ref=frontier_ref,
        selected_alternative_id=selected,
        effective_at=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=1),
        rule_version_ref=RULE_VERSION_REF,
        generation_binding=binding,
    )
    authorization_ref = _put_signed(
        store,
        authorization.model_dump(mode="json"),
        kind=s8.NORMATIVE_AUTHORIZATION_KIND,
        schema=s8.NORMATIVE_GENERATION_AUTHORIZATION_SCHEMA_VERSION,
        key=authorizer_key,
        identity=authorizer,
    )
    trust = s8.NormativeAuthorityTrust(
        epoch="r11-direct-n6-test-epoch",
        principals=(
            s8.NormativeAuthorityPrincipal(
                identity=authorizer,
                public_key_pem=authorizer_key.public_pem().decode(),
                decision_roles=("principal",),
                authority_purposes=("value_schedule_for_ranking",),
                case_ids=(case_id,),
                scope_refs=(scope,),
                mandate_refs=(mandate,),
            ),
            s8.NormativeAuthorityPrincipal(
                identity=claimant,
                public_key_pem=claimant_key.public_pem().decode(),
            ),
        ),
    )
    owner = s8.NormativeValueScheduleOwner(
        store=store,
        trust=trust,
        signature_verifier=_guarded_signature_verifier(store),
        repo_root=source_root,
    )
    evidence = s8.NormativeGenerationEvidenceRefs(
        frontier_ref=frontier_ref,
        authorization_ref=authorization_ref,
        scope_ref=scope,
    )
    return {
        "binding": binding,
        "candidate_fronts": run.fronts.candidate_ids_by_front(),
        "evidence": evidence,
        "owner": owner,
        "problem": problem,
        "run": run,
        "source_root": source_root,
        "source_ref": source_ref,
        "source_payload": source_payload,
        "store": store,
    }


@pytest.mark.asyncio
async def test_actual_blocked_n6_source_is_persisted_as_blocked_s8_disposition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = await _owner_source_harness(
        tmp_path,
        disposition="blocked",
        runtime_source_store=True,
        identity_current=True,
        monkeypatch=monkeypatch,
    )
    run = harness["run"]
    assert run.synthetic is None  # R1 provenance remains unestablished in this fixture.
    disposition_ref = harness["owner"].produce_generation_disposition(
        binding=harness["binding"],
        evidence=harness["evidence"],
        evaluated_at=NOW,
    )
    disposition = harness["owner"].project_generation_disposition(
        disposition_ref,
        evaluated_at=NOW,
    )

    assert disposition.authorization_status == "blocked"
    assert disposition.ranked_recommendations == ()
    assert disposition.decision_request.reason_codes == (
        "p20_normative_generation_source_blocked",
    )
    assert disposition.candidate_fronts == harness["candidate_fronts"]
    assert disposition.compiled_membership_status == "not_established"
    assert disposition.evidence == harness["evidence"]
    persisted = canon.from_canonical_bytes(
        harness["store"].get_bytes(artifacts.ArtifactID.model_validate(disposition_ref))
    )
    assert persisted["authorization_status"] == "blocked"
    assert persisted["ranked_recommendations"] == []


@pytest.mark.asyncio
async def test_actual_nonblocked_n6_stop_preserves_signed_s8_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = await _owner_source_harness(
        tmp_path,
        disposition="stop",
        runtime_source_store=True,
        identity_current=True,
        monkeypatch=monkeypatch,
    )
    run = harness["run"]
    assert run.terminal_status == "completed"
    assert run.source_custody_limitation is None
    assert run.synthetic is None  # R1 provenance remains unestablished in this fixture.
    disposition_ref = harness["owner"].produce_generation_disposition(
        binding=harness["binding"],
        evidence=harness["evidence"],
        evaluated_at=NOW,
    )
    disposition = harness["owner"].project_generation_disposition(
        disposition_ref,
        evaluated_at=NOW,
    )

    assert disposition.authorization_status == "authorized"
    assert disposition.ranked_recommendations
    assert disposition.compiled_membership_status == "not_established"
    assert disposition.generation_binding.source_run_ref == harness["source_ref"]


@pytest.mark.asyncio
async def test_n6_currentness_admission_is_frozen_and_candidate_work_remains_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy v1 history cannot gain authority from a later Confidence Ledger read."""
    harness = await _owner_source_harness(
        tmp_path,
        disposition="historical-v1",
        historical_v1_source=True,
    )
    run = harness["run"]
    unavailable = n6.N6DeploymentCurrentnessObservation(
        status="not_established",
        census_verdict="UNRUN",
        recorded_identity_status=run.deployment_identity_status,
        recorded_deployment_identity=run.deployment_identity,
        loaded_identity_status="not_established",
        loaded_deployment_identity=None,
        loaded_identity_reason_code="packaged_deployment_identity_issuer_unavailable",
        reason_code="historical_deployment_identity_not_recorded",
        unresolved_by_construction=("historical_deployment_identity_not_recorded",),
    )
    live = {"observation": unavailable}
    calls: list[dict[str, object]] = []

    def observe(**kwargs: object) -> n6.N6DeploymentCurrentnessObservation:
        calls.append(dict(kwargs))
        return live["observation"]

    monkeypatch.setattr(n6, "observe_n6_deployment_currentness", observe)
    owner = harness["owner"]
    # Candidate computation remains available for the pinned historical input.
    assert n6.validate_generation_cycle_candidate_run(run) == ()
    calls.clear()
    source_id = artifacts.ArtifactID.model_validate(harness["source_ref"])
    source_bytes = harness["store"].get_bytes(source_id)
    disposition_ref = owner.produce_generation_disposition(
        binding=harness["binding"],
        evidence=harness["evidence"],
        evaluated_at=NOW,
    )
    disposition_id = artifacts.ArtifactID.model_validate(disposition_ref)
    disposition_bytes = harness["store"].get_bytes(disposition_id)
    envelope = canon.from_canonical_bytes(disposition_bytes)
    assert envelope["schema_version"] == s8.NORMATIVE_GENERATION_DISPOSITION_V2_SCHEMA_VERSION
    assert envelope["n6_currentness_at_admission"] == unavailable.model_dump(mode="json")
    assert envelope["disposition_v1"]["authorization_status"] == "blocked"
    assert envelope["disposition_v1"]["ranked_recommendations"] == []
    assert len(calls) == 1

    expected_history = canon.to_canonical_bytes(
        envelope["disposition_v1"], canon.CanonSpec(forbid_floats=False)
    )
    live["observation"] = n6.N6DeploymentCurrentnessObservation(
        status="current",
        census_verdict="PASS",
        recorded_identity_status="established",
        recorded_deployment_identity="policy-engine-deployment:sha256:" + "a" * 64,
        loaded_identity_status="established",
        loaded_deployment_identity="policy-engine-deployment:sha256:" + "a" * 64,
        reason_code="n6_currentness_established",
        unresolved_by_construction=(),
    )
    historical = owner.replay_generation_disposition(disposition_ref)
    assert canon.to_canonical_bytes(
        historical.model_dump(mode="json"), canon.CanonSpec(forbid_floats=False)
    ) == expected_history
    projection = owner.project_generation_disposition(disposition_ref, evaluated_at=NOW)
    assert projection.authorization_status == "blocked"
    assert projection.ranked_recommendations == ()
    assert projection.decision_request is not None
    assert "p20_normative_generation_currentness_reissue_required" in (
        projection.decision_request.reason_codes
    )
    assert len(calls) == 1
    assert harness["store"].get_bytes(source_id) == source_bytes
    assert harness["store"].get_bytes(disposition_id) == disposition_bytes

    # Removal probe: bypass only the persisted currentness admission gate.
    # The historical v1 input is not a served or production S8 authority witness.
    with monkeypatch.context() as removed_gate:
        removed_gate.setattr(
            owner,
            "_blocked_generation_disposition_projection",
            lambda recorded, *, reason_code: owner._generation_disposition(
                binding=recorded.generation_binding,
                evidence=recorded.evidence,
                evaluated_at=NOW,
                input_limitation=recorded.input_limitation,
            ),
        )
        removed_gate.setattr(
            n6,
            "inspect_generation_cycle_run",
            lambda *_args, **_kwargs: n6.GenerationCycleRunInspection(
                issues=(), currentness=live["observation"]
            ),
        )
        bypassed = owner.project_generation_disposition(disposition_ref, evaluated_at=NOW)
        assert bypassed.authorization_status == "authorized"
        assert bypassed.ranked_recommendations


@pytest.mark.asyncio
async def test_v2_reader_rejects_current_observation_with_unresolved_census(
    tmp_path: Path,
) -> None:
    """A forged current marker cannot override a remaining N6 census limitation."""
    harness = await _owner_source_harness(
        tmp_path,
        disposition="historical-v1",
        historical_v1_source=True,
    )
    owner = harness["owner"]
    store = harness["store"]
    disposition_ref = owner.produce_generation_disposition(
        binding=harness["binding"],
        evidence=harness["evidence"],
        evaluated_at=NOW,
    )
    disposition_id = artifacts.ArtifactID.model_validate(disposition_ref)
    envelope = s8._NormativeGenerationDispositionV2.model_validate(
        canon.from_canonical_bytes(store.get_bytes(disposition_id))
    )
    identity = "policy-engine-deployment:sha256:" + "c" * 64
    forged_currentness = n6.N6DeploymentCurrentnessObservation.model_validate(
        {
            **n6.N6DeploymentCurrentnessObservation(
                status="current",
                census_verdict="PASS",
                recorded_identity_status="established",
                recorded_deployment_identity=identity,
                loaded_identity_status="established",
                loaded_deployment_identity=identity,
                reason_code="n6_currentness_established",
                unresolved_by_construction=(),
            ).model_dump(mode="json"),
            "unresolved_by_construction": ("n6_strangle_census_not_established",),
        }
    )
    forged = s8._NormativeGenerationDispositionV2(
        disposition_v1=envelope.disposition_v1,
        n6_currentness_at_admission=forged_currentness,
    )
    forged_ref = store.put_json(
        forged.model_dump(mode="json"),
        artifacts.PutOptions(
            kind=s8.NORMATIVE_GENERATION_DISPOSITION_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=s8.NORMATIVE_GENERATION_DISPOSITION_KIND,
                version=s8.NORMATIVE_GENERATION_DISPOSITION_V2_SCHEMA_VERSION,
            ),
        ),
    )

    with pytest.raises(
        s8.P20NormativeChoiceError,
        match="p20_normative_generation_disposition_history_invalid",
    ) as error:
        owner.replay_generation_disposition(str(forged_ref.artifact_id))

    assert isinstance(error.value.__cause__, ValueError)
    assert str(error.value.__cause__) == "n6 currentness observation is not fully established"


@pytest.mark.asyncio
async def test_identity_current_v4_source_limited_run_is_refused_by_direct_s8_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = await _owner_source_harness(
        tmp_path,
        disposition="stop",
        runtime_source_store=False,
        identity_current=True,
        monkeypatch=monkeypatch,
    )
    run = harness["run"]
    assert run.schema_version == "policyos.runtime.generation_cycle_controller.v4"
    assert run.source_custody_limitation is not None
    assert run.source_custody_limitation.reason_code == "source_store_unavailable"
    observations = _track_currentness_observations(monkeypatch)
    assert n6.currentness_for_generation_cycle_run(run).status == "current"
    observations.clear()

    # Removal probe: deleting the strict custody issue while retaining the v4
    # limitation marker would let this otherwise admissible signed S8 bundle
    # through.  The consumer must therefore reject on the source-custody issue.
    with pytest.raises(
        s8.P20NormativeChoiceError, match="p20_normative_generation_source_invalid"
    ):
        harness["owner"].produce_generation_disposition(
            binding=harness["binding"],
            evidence=harness["evidence"],
            evaluated_at=NOW,
        )
    assert observations
    assert all(
        item
        == {
            "recorded_identity_status": "established",
            "recorded_deployment_identity": run.deployment_identity,
        }
        for item in observations
    )


@pytest.mark.asyncio
async def test_historical_v1_identity_and_custody_limits_block_s8_with_exact_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Persist the pinned v1 source as blocked and prove its N6 gate is decisive."""
    harness = await _owner_source_harness(
        tmp_path,
        disposition="historical-v1",
        historical_v1_source=True,
    )
    run = harness["run"]
    payload = harness["source_payload"]
    owner = harness["owner"]
    store = harness["store"]
    source_ref = harness["source_ref"]
    source_id = artifacts.ArtifactID.model_validate(source_ref)

    assert run.schema_version == "policyos.runtime.generation_cycle_controller.v1"
    assert run.terminal_status == "completed"
    assert run.deployment_identity_status == "not_established"
    assert run.deployment_identity is None
    assert run.source_preservation_receipt is None
    assert run.source_custody_limitation is None
    assert "source_preservation_receipt" not in payload
    assert "source_custody_limitation" not in payload
    source_bytes = store.get_bytes(source_id)
    assert source_bytes == canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False))
    assert (
        owner._read(
            source_ref,
            kind=s8.NORMATIVE_GENERATION_SOURCE_KIND,
            schema=n6.GENERATION_CYCLE_SCHEMA_VERSION,
        )
        == payload
    )
    assert n6.validate_generation_cycle_run_history(payload) == ()
    # Candidate-band computation remains available for this exact historical input.
    assert n6.validate_generation_cycle_candidate_run(run) == ()
    strict_issues = n6.validate_generation_cycle_run(run)
    assert len(strict_issues) == 1
    assert strict_issues[0]["code"] == "strangle_receipt_currentness_not_established"
    assert strict_issues[0]["reason"] == "historical_deployment_identity_not_recorded"
    assert strict_issues[0]["census_verdict"] == "UNRUN"

    recommend_calls = 0
    original_recommend = owner.recommend

    def track_recommend(*args: Any, **kwargs: Any) -> Any:
        nonlocal recommend_calls
        recommend_calls += 1
        return original_recommend(*args, **kwargs)

    monkeypatch.setattr(owner, "recommend", track_recommend)
    disposition_ref = owner.produce_generation_disposition(
        binding=harness["binding"],
        evidence=harness["evidence"],
        evaluated_at=NOW,
    )
    disposition = owner.project_generation_disposition(
        disposition_ref,
        evaluated_at=NOW,
    )

    expected_reasons = (
        "strangle_receipt_currentness_not_established",
        "historical_deployment_identity_not_recorded",
        "generation_cycle_source_preservation_not_established",
        "historical_v1_source_custody_not_represented",
        "p20_normative_generation_currentness_reissue_required",
    )
    assert disposition.authorization_status == "blocked"
    assert disposition.ranked_recommendations == ()
    assert disposition.decision_request is not None
    assert disposition.decision_request.reason_codes == expected_reasons
    assert disposition.candidate_fronts == run.fronts.candidate_ids_by_front()
    assert disposition.compiled_membership_status == "not_established"
    assert disposition.evidence == harness["evidence"]
    assert recommend_calls == 0  # S8 signatures and evidence were not evaluated.
    persisted = canon.from_canonical_bytes(
        store.get_bytes(artifacts.ArtifactID.model_validate(disposition_ref))
    )
    assert persisted["schema_version"] == s8.NORMATIVE_GENERATION_DISPOSITION_V2_SCHEMA_VERSION
    assert persisted["disposition_v1"]["authorization_status"] == "blocked"
    assert persisted["disposition_v1"]["ranked_recommendations"] == []
    assert persisted["disposition_v1"]["decision_request"]["reason_codes"] == list(
        expected_reasons[:-1]
    )

    # Marker-retaining removal probe: preserve exact v1 bytes and every other N6
    # issue, but remove only the typed currentness refusal. The same signed S8
    # evidence is then sufficient to rank, so the blocked assertion above turns red.
    original_inspector = n6.inspect_generation_cycle_run
    with monkeypatch.context() as removed_gate:

        def inspection_without_currentness(
            checked_run: object, **kwargs: object
        ) -> n6.GenerationCycleRunInspection:
            inspected = original_inspector(checked_run, **kwargs)
            return n6.GenerationCycleRunInspection(
                issues=tuple(
                    issue
                    for issue in inspected.issues
                    if issue.get("code")
                    != "strangle_receipt_currentness_not_established"
                ),
                currentness=inspected.currentness,
            )

        removed_gate.setattr(n6, "inspect_generation_cycle_run", inspection_without_currentness)
        assert (
            owner._read(
                source_ref,
                kind=s8.NORMATIVE_GENERATION_SOURCE_KIND,
                schema=n6.GENERATION_CYCLE_SCHEMA_VERSION,
            )
            == payload
        )
        admitted = owner._generation_disposition(
            binding=harness["binding"],
            evidence=harness["evidence"],
            evaluated_at=NOW,
        )
        assert admitted.authorization_status == "authorized"
        assert admitted.ranked_recommendations
    assert recommend_calls == 1

    with monkeypatch.context() as marker_only_census:

        def census_pass_with_missing_identity(
            checked_run: object, **kwargs: object
        ) -> n6.GenerationCycleRunInspection:
            inspected = original_inspector(checked_run, **kwargs)
            return n6.GenerationCycleRunInspection(
                issues=tuple(
                    {**issue, "census_verdict": "PASS"}
                    for issue in inspected.issues
                ),
                currentness=inspected.currentness,
            )

        marker_only_census.setattr(
            n6, "inspect_generation_cycle_run", census_pass_with_missing_identity
        )
        still_limited = owner._generation_disposition(
            binding=harness["binding"],
            evidence=harness["evidence"],
            evaluated_at=NOW,
        )
        assert still_limited.authorization_status == "blocked"
        assert still_limited.decision_request is not None
        assert "historical_deployment_identity_not_recorded" in (
            still_limited.decision_request.reason_codes
        )


@pytest.mark.asyncio
async def test_historical_v1_terminal_block_remains_primary_s8_reason(
    tmp_path: Path,
) -> None:
    """Preserve the N6 terminal block while disclosing v1 identity/custody limits."""
    harness = await _owner_source_harness(
        tmp_path,
        disposition="blocked",
        historical_v1_source=True,
        historical_v1_terminal_blocked=True,
    )
    run = harness["run"]
    payload = harness["source_payload"]
    owner = harness["owner"]

    assert run.schema_version == "policyos.runtime.generation_cycle_controller.v1"
    assert run.terminal_status == "blocked"
    assert n6.validate_generation_cycle_run_history(payload) == ()
    issues = n6.validate_generation_cycle_run(run)
    assert len(issues) == 1
    assert issues[0]["code"] == "strangle_receipt_currentness_not_established"
    assert issues[0]["reason"] == "historical_deployment_identity_not_recorded"
    assert issues[0]["census_verdict"] == "UNRUN"

    disposition_ref = owner.produce_generation_disposition(
        binding=harness["binding"],
        evidence=harness["evidence"],
        evaluated_at=NOW,
    )
    disposition = owner.project_generation_disposition(
        disposition_ref,
        evaluated_at=NOW,
    )

    assert disposition.authorization_status == "blocked"
    assert disposition.ranked_recommendations == ()
    assert disposition.decision_request is not None
    assert disposition.decision_request.reason_codes == (
        "p20_normative_generation_source_blocked",
        "strangle_receipt_currentness_not_established",
        "historical_deployment_identity_not_recorded",
        "generation_cycle_source_preservation_not_established",
        "historical_v1_source_custody_not_represented",
        "p20_normative_generation_currentness_reissue_required",
    )
