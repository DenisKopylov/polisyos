from __future__ import annotations

from datetime import UTC, datetime
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
    hits = fresh_registry.query_with_transfer(
        LessonQuery(
            domain=expected_context.domain,
            task_family=expected_context.task_family,
            source_run_id=expected_context.run_id,
            tenant_hash=expected_context.tenant_hash,
            limit=5,
        ),
        target_context=expected_context,
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
