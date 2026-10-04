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
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> dict[str, Any]:
    """Produce one current N6 run and bind real signed S8 evidence to its persisted ref."""
    source_root = await _source_root(tmp_path)
    store = artifacts.FileSystemCAS(tmp_path / "cas")
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
            raise AssertionError(
                "identity-current fixture requires the currentness test seam"
            )
        run = _identity_current_test_run(
            run, tmp_path=tmp_path, monkeypatch=monkeypatch
        )
    if runtime_source_store:
        assert n6.validate_generation_cycle_run(run, repo_root=source_root) == ()
    else:
        assert run.source_custody_limitation is not None
        assert run.source_custody_limitation.reason_code == "source_store_unavailable"

    source_ref = str(
        store.put_json(
            run.model_dump(mode="json"),
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
