from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.lex import ComplianceIssue
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.observation.contracts import ObservationFamily
from polisyos.ir.observation.governance import (
    GovernancePassMappingRegistry,
    ObservationFamilyPolicyRegistry,
)
from polisyos.scientist.governance.calibration import (
    CalibrationAdversarialSuiteRegistry,
    CalibrationGovernanceInput,
    CalibrationGovernanceRunner,
)
from polisyos.scientist.methods.search import transfer_context as transfer_context_module
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonQuery,
    LessonRegistry,
    load_lesson_card,
)
from polisyos.scientist.methods.search.transfer_context import (
    TransferContext,
    TransferTenantScopeStatus,
)


class _RecordingPass(ValidatorPass):
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    @property
    def pass_id(self) -> str:
        return "calibration_registry_probe"

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        del ctx
        self.calls.append(self.pass_id)
        return []


class _MissingLessonRegistry:
    pass


class _NonCallableLessonRegistry:
    record_local = 11


class _WrongResultLessonRegistry:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls = 0

    def record_local(self, card: object, *, context: TransferContext) -> object:
        del card, context
        self.calls += 1
        return self.result


class _ContextAwareLessonRegistry:
    def __init__(self, registry: LessonRegistry) -> None:
        self.registry = registry
        self.resolutions = 0
        self.calls = 0
        self.contexts: list[TransferContext] = []

    @property
    def record_local(self) -> object:
        self.resolutions += 1
        if self.resolutions > 1:
            raise AssertionError("selected lesson writer was resolved more than once")

        def record(card: LessonCard, *, context: TransferContext) -> ArtifactRef:
            self.calls += 1
            self.contexts.append(context)
            return self.registry.record_local(card, context=context)

        return record


def _candidate_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="scientist.test",
        media_type="application/json",
    )


def _runner(calls: list[str]) -> CalibrationGovernanceRunner:
    mapping = GovernancePassMappingRegistry(
        global_mandatory_passes=["calibration_registry_probe"],
        family_passes={family.value: [] for family in ObservationFamily},
    )
    return CalibrationGovernanceRunner(
        passes=[_RecordingPass(calls)],
        policy_registry=ObservationFamilyPolicyRegistry.default(),
        mapping_registry=mapping,
        adversarial_suite_registry=CalibrationAdversarialSuiteRegistry(suite_aliases={}),
    )


def _input(registry: object | None) -> CalibrationGovernanceInput:
    return CalibrationGovernanceInput(
        run_id="R_c5a_lesson_registry",
        observation_families=[ObservationFamily.MACRO_STATE],
        profile=ValidationProfile.fast(),
        candidate_ref=_candidate_ref(),
        lesson_registry=registry,
    )


@pytest.mark.parametrize(
    "registry",
    [_MissingLessonRegistry(), _NonCallableLessonRegistry()],
    ids=["missing-record-local", "noncallable-record-local"],
)
def test_calibration_governance_rejects_malformed_registry_before_pass_work(
    registry: object,
) -> None:
    calls: list[str] = []

    with pytest.raises(TypeError, match="lesson registry must provide a callable record_local"):
        _runner(calls).run(_input(registry))

    assert calls == []


def test_calibration_governance_none_registry_is_an_explicit_opt_out() -> None:
    calls: list[str] = []
    report = _runner(calls).run(_input(None))

    assert report.lesson_card_ref is None
    assert calls == ["calibration_registry_probe"]


def test_calibration_lesson_supersedes_only_on_new_selected_observations(
    tmp_path: Path,
) -> None:
    from polisyos.calibration.forecast_bridge import (
        persist_empirical_calibration_evidence,
        produce_empirical_calibration_evidence,
    )
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.security import (
        AccessScope,
        reset_current_access_scope,
        set_current_access_scope,
    )
    from polisyos.ir.analytics.backtest import load_backtest_report, persist_backtest_report
    from polisyos.ir.artifacts import InputRef
    from polisyos.runtime.http.services.predictive_calibration import (
        _build_empirical_context,
        _persist_evidence_role_refs,
    )
    from polisyos.scientist.methods.backtesting.forecast_owner import ForecastOwner
    from tests.unit.remediation.test_frc_02_owner import _request, _rule, _source, _spec

    store = FileSystemCAS(tmp_path / "cas")
    root = tmp_path / "lessons"
    registry = LessonRegistry(root=root, store=store)
    candidate = _spec(store, kind="ir.candidate_scenario_source", spec_id="subject")
    model = _spec(store, kind="ir.model_spec", spec_id="model")
    policy = _spec(store, kind="ir.policy_spec", spec_id="policy")
    rule = _rule(store)
    owner = ForecastOwner(store)
    ir_store = ensure_ir_artifact_store(store)
    now = datetime.now(UTC)
    original_obs = now - timedelta(days=100)
    recent_obs = now - timedelta(days=1)

    def produce(report_id: str, observed_at: datetime, held_out: list[float]) -> ArtifactRef:
        request = _request(
            _source(store, training=[float(index) for index in range(10, 20)], holdout=held_out),
            rule,
            report_id=report_id,
            model_spec_ref=str(model.artifact_id),
            policy_spec_ref=str(policy.artifact_id),
            train_end=10,
            horizon=3,
        )
        original_times = request.temporal_roles.model_dump(mode="python")
        shift = observed_at - request.temporal_roles.observation_time
        request = request.model_copy(
            update={
                "temporal_roles": type(request.temporal_roles).model_validate(
                    {name: value + shift for name, value in original_times.items()}
                )
            }
        )
        produced = owner.run(request)
        backtest = load_backtest_report(ir_store, produced.backtest_report_ref)
        refs = _persist_evidence_role_refs(
            store=store,
            report_id=report_id,
            threshold=0.5,
            model_spec_ref=model,
            policy_spec_ref=policy,
            candidate_source_ref=candidate,
            observed_source_ref=produced.observed_source_ref,
            training_slice_ref=produced.training_slice_ref,
            uncertainty_bundle_ref=produced.uncertainty_bundle_ref,
            method_artifact_ref=produced.method_artifact_ref,
            calibration_rule_ref=produced.calibration_rule_ref,
        )
        selected_report = persist_backtest_report(
            ir_store,
            backtest,
            inputs=[
                *ir_store.get_manifest(produced.backtest_report_ref).inputs,
                InputRef(
                    artifact_id=candidate.artifact_id,
                    role="candidate_source",
                    manifest_profile_sha256=candidate.manifest_profile_sha256,
                ),
                *[
                    InputRef(
                        artifact_id=ref.artifact_id,
                        role=role,
                        manifest_profile_sha256=ref.manifest_profile_sha256,
                    )
                    for role, ref in refs.items()
                ],
            ],
        )
        evidence = produce_empirical_calibration_evidence(
            store,
            selected_report,
            context=_build_empirical_context(
                refs,
                model_spec_ref=produced.model_spec_ref,
                policy_spec_ref=produced.policy_spec_ref,
                threshold=0.5,
                temporal_roles=request.temporal_roles,
            ),
        )
        assert evidence.context_bound and evidence.recomputed_denominator == 3
        assert evidence.failure_codes == ("backtest_source_not_established",)
        assert not evidence.usable_for_calibration
        return ArtifactRef.model_validate(
            persist_empirical_calibration_evidence(store, evidence).model_dump(mode="python")
        )

    prior = produce("prior-observed", original_obs, [20.0, 21.0, 22.0])
    relabeled = produce("restamped-old", recent_obs, [20.0, 21.0, 22.0])
    new = produce("new-observed", recent_obs, [20.0, 23.0, 28.0])
    token = set_current_access_scope(
        AccessScope.for_service(
            tenant_id="assessment", cell_id=None, spiffe_id="spiffe://test/search"
        )
    )
    try:
        source = TransferContext(task_family="policy", domain="fiscal", run_id="assessment")
        target = TransferContext(task_family="policy", domain="labor", run_id="look-ahead")
        runner = _runner([])

        def publish(evidence_ref: ArtifactRef, prior_lesson: ArtifactRef | None) -> ArtifactRef:
            bundle = CalibrationGovernanceInput.model_validate(
                {
                    "run_id": source.run_id,
                    "observation_families": [ObservationFamily.MACRO_STATE],
                    "candidate_ref": candidate,
                    "profile": ValidationProfile.fast(),
                    "lesson_registry": registry,
                    "predictive_lesson": {
                        "evidence_ref": evidence_ref,
                        "prior_lesson_ref": prior_lesson,
                        "context": source,
                    },
                }
            )
            outcome = runner.run(bundle)
            assert outcome.lesson_card_ref is not None
            return outcome.lesson_card_ref

        first_ref = publish(prior, None)
        old_body = store.get_bytes(first_ref)
        first = load_lesson_card(store, first_ref)
        assert first.created_at == original_obs and first.confidence == 0.5
        assert first.trust_level.value == "low_confidence"
        assert first.metadata["empirical_source_status"] == "not_established"
        selector = LessonQuery(domain="fiscal", failure_type=first.failure_type, limit=1)
        [old_hint] = registry.query_with_transfer(selector, target_context=target)
        assert old_hint.created_at == original_obs and old_hint.provenance_weight == 0.325

        before = registry.index_snapshot(context=source).model_dump(mode="json")
        with pytest.raises(ValueError, match="new observations"):
            publish(relabeled, first_ref)
        with pytest.raises(ValueError, match="selected evidence"):
            publish(new.model_copy(update={"manifest_profile_sha256": None}), first_ref)
        assert registry.index_snapshot(context=source).model_dump(mode="json") == before

        updated_ref = publish(new, first_ref)
        assert updated_ref != first_ref and store.get_bytes(first_ref) == old_body
        manifest = store.get_manifest(updated_ref)
        assert {
            item.role: (item.artifact_id, item.manifest_profile_sha256) for item in manifest.inputs
        } == {
            "selected_lesson_assessment": (new.artifact_id, new.manifest_profile_sha256),
            "prior_lesson_assessment": (first_ref.artifact_id, first_ref.manifest_profile_sha256),
        }
        fresh = LessonRegistry(root=root, store=FileSystemCAS(store.root))
        rows = fresh.index_snapshot(context=source).entries
        assert {(str(row.artifact_ref.artifact_id), row.invalidated) for row in rows} == {
            (str(first_ref.artifact_id), True),
            (str(updated_ref.artifact_id), False),
        }
        [reopened] = fresh.query_with_transfer(selector, target_context=target)
        assert reopened.created_at == recent_obs and reopened.provenance_weight == 0.65
        assert reopened.confidence == 0.5 and reopened.trust_level.value == "low_confidence"
        assert reopened.metadata["empirical_source_status"] == "not_established"
        assert reopened.source_run_id == "new-observed"
        assert fresh.invalidate(load_lesson_card(store, updated_ref).lesson_id, "source-removed")
        assert fresh.query_with_transfer(selector, target_context=target) == []
        assert store.get_bytes(first_ref) == old_body
    finally:
        reset_current_access_scope(token)


def test_calibration_governance_forwards_resolved_context_to_selected_writer_and_fresh_cas_read(
    tmp_path: Path,
    cas_store: FileSystemCAS,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_context = TransferContext(
        task_family="policy_calibration_context_witness",
        domain="calibration_context_witness_domain",
        run_id="R_c5a_lesson_registry",
        tenant_hash=None,
        tenant_scope_status=TransferTenantScopeStatus.DECLARED_UNSCOPED,
        cross_tenant_opt_in=False,
        timestamp=datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC),
    )
    monkeypatch.setattr(
        transfer_context_module,
        "resolve_transfer_context",
        lambda **kwargs: expected_context,
    )
    registry = LessonRegistry(root=tmp_path / "lessons", store=cas_store)
    selected_registry = _ContextAwareLessonRegistry(registry)
    calls: list[str] = []
    report = _runner(calls).run(_input(selected_registry))

    assert report.lesson_card_ref is not None
    assert selected_registry.resolutions == 1
    assert selected_registry.calls == 1
    assert selected_registry.contexts == [expected_context]
    assert selected_registry.contexts[0].timestamp == datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert calls == ["calibration_registry_probe"]

    card = load_lesson_card(cas_store, report.lesson_card_ref)
    assert card.stage_name == "calibration_governance"
    assert card.source_run_id == expected_context.run_id
    assert card.task_family == expected_context.task_family
    assert card.domain == expected_context.domain
    assert card.origin_tenant_hash is None
    assert card.origin_tenant_scope_status is TransferTenantScopeStatus.DECLARED_UNSCOPED

    fresh_registry = LessonRegistry(root=tmp_path / "lessons", store=cas_store)
    snapshot = fresh_registry.index_snapshot(context=expected_context)
    assert snapshot.source_scope is not None
    assert snapshot.source_scope.task_family == expected_context.task_family
    assert snapshot.source_scope.domain == expected_context.domain
    assert snapshot.source_scope.tenant_hash == expected_context.tenant_hash
    assert snapshot.source_scope.tenant_scope_status is expected_context.tenant_scope_status
    entry = next(item for item in snapshot.entries if item.lesson_id == card.lesson_id)
    assert entry.origin_run_id == expected_context.run_id
    assert entry.task_family == expected_context.task_family
    assert entry.domain == expected_context.domain
    assert entry.origin_tenant_hash == expected_context.tenant_hash
    assert entry.origin_tenant_scope_status is expected_context.tenant_scope_status
    query = LessonQuery(
        domain=expected_context.domain,
        task_family=expected_context.task_family,
        source_run_id=expected_context.run_id,
        tenant_hash=expected_context.tenant_hash,
        limit=5,
    )
    assert fresh_registry.query_with_transfer(query, target_context=expected_context) == []
    hits = fresh_registry.query_with_transfer(
        query, target_context=expected_context.model_copy(update={"timestamp": card.created_at})
    )
    assert any(hit.lesson_id == card.lesson_id for hit in hits)


@pytest.mark.parametrize("result_value", [None, "not-an-artifact-ref"], ids=["none", "string"])
def test_calibration_governance_rejects_malformed_lesson_publication_result(
    result_value: object,
) -> None:
    calls: list[str] = []
    registry = _WrongResultLessonRegistry(result_value)

    with pytest.raises(TypeError, match="lesson registry record_local must return an ArtifactRef"):
        _runner(calls).run(_input(registry))

    assert calls == ["calibration_registry_probe"]
    assert registry.calls == 1
