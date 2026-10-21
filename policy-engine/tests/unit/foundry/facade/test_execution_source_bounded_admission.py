from __future__ import annotations

import importlib

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    InputRef,
    IntegrityInfo,
    SchemaInfo,
)
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    MetricsRef,
    SimulationResult,
    SimulationResultRef,
)

execute_facade = importlib.import_module("polisyos.foundry.execute")
from polisyos.foundry.execute import (
    BoundedExecutionSourceReader,
    ExecutionSourceBoundedReadRefusal,
    admit_execution_source_bounded,
)


class _NoFallbackStore:
    def get_manifest(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("bounded admission used the unbounded manifest API")

    def get_manifest_by_profile(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("bounded admission used the unbounded selected-profile API")

    def get_bytes(self, *_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("bounded admission used the unbounded payload API")

    def verify(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("bounded admission used the unbounded verification API")


class _LegacySelectedProfileReader:
    def __init__(self, manifest: ArtifactManifest, result: SimulationResult) -> None:
        self.manifest = manifest
        self.result = result
        self.calls: list[str] = []

    def read_selected_manifest(
        self,
        ref: ArtifactRef,
    ) -> tuple[ArtifactManifest, int]:
        self.calls.append("manifest")
        assert ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(self.manifest)
        return self.manifest, 11

    def read_edge_manifest(
        self,
        _edge: InputRef,
    ) -> tuple[ArtifactRef, ArtifactManifest, int]:
        raise AssertionError("legacy result without edges must not read an edge")

    def read_typed_model(
        self,
        model: type[SimulationResult],
        ref: ArtifactRef,
    ) -> tuple[ArtifactManifest, SimulationResult, int, int]:
        self.calls.append("typed_model")
        assert model is SimulationResult
        assert ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(self.manifest)
        return self.manifest, self.result, 13, 17


def _selected_legacy_fixture() -> tuple[SimulationResultRef, ArtifactManifest, SimulationResult]:
    manifest = ArtifactManifest(
        manifest_schema_version="v2",
        artifact_id="sha256:" + "a" * 64,
        kind=SimulationResult.ARTIFACT_KIND,
        media_type=SimulationResult.ARTIFACT_MEDIA_TYPE,
        byte_size=17,
        artifact_schema=SchemaInfo(
            name=SimulationResult.ARTIFACT_SCHEMA_NAME,
            version=SimulationResult.LEGACY_ARTIFACT_SCHEMA_VERSION,
        ),
        integrity=IntegrityInfo(sha256="sha256:" + "a" * 64),
    )
    profile = artifact_manifest_profile_sha256(manifest)
    ref = SimulationResultRef(
        artifact_id=manifest.artifact_id,
        manifest_profile_sha256=profile,
    )
    result = SimulationResult(
        schema_version=SimulationResult.LEGACY_ARTIFACT_SCHEMA_VERSION,
        exec_plan_ref=ExecPlanRef(
            artifact_id="sha256:" + "c" * 64,
            manifest_profile_sha256="sha256:" + "d" * 64,
        ),
        metrics_ref=MetricsRef(
            artifact_id="sha256:" + "e" * 64,
            manifest_profile_sha256="sha256:" + "f" * 64,
        ),
        execution_source_status="not_recorded",
    )
    return ref, manifest, result


def test_bounded_admission_api_is_exported_from_stable_execute_facade() -> None:
    expected = {
        "BoundedExecutionSourceReader",
        "ExecutionSourceBoundedReadRefusal",
        "admit_execution_source_bounded",
    }
    assert expected <= set(execute_facade.__all__)
    assert execute_facade.BoundedExecutionSourceReader is BoundedExecutionSourceReader
    assert execute_facade.ExecutionSourceBoundedReadRefusal is ExecutionSourceBoundedReadRefusal
    assert execute_facade.admit_execution_source_bounded is admit_execution_source_bounded


def test_bounded_admission_uses_required_reader_and_reports_all_observed_bytes() -> None:
    ref, manifest, result = _selected_legacy_fixture()
    reader = _LegacySelectedProfileReader(manifest, result)

    admitted = admit_execution_source_bounded(
        _NoFallbackStore(),
        ref,
        reader=reader,
    )

    assert admitted.mode == "legacy_profileless"
    assert admitted.source_read_bytes == 41
    assert reader.calls == ["manifest", "typed_model"]


def test_bounded_admission_refuses_profileless_input_before_any_store_read() -> None:
    ref, manifest, result = _selected_legacy_fixture()
    ref = ref.model_copy(update={"manifest_profile_sha256": None})
    reader = _LegacySelectedProfileReader(manifest, result)

    try:
        admit_execution_source_bounded(_NoFallbackStore(), ref, reader=reader)
    except ValueError as exc:
        assert str(exc) == "execution_source_selected_profile_missing"
    else:
        raise AssertionError("profileless source unexpectedly reached bounded admission")

    assert reader.calls == []


def test_bounded_admission_propagates_typed_budget_refusal_without_fallback() -> None:
    ref, _manifest, _result = _selected_legacy_fixture()

    class _BudgetRefusalReader:
        def read_selected_manifest(
            self,
            _ref: ArtifactRef,
        ) -> tuple[ArtifactManifest, int]:
            raise ExecutionSourceBoundedReadRefusal(
                "execution_source_read_budget_exhausted",
                observed_bytes=32,
                limit_bytes=32,
            )

        def read_edge_manifest(
            self,
            _edge: InputRef,
        ) -> tuple[ArtifactRef, ArtifactManifest, int]:
            raise AssertionError("budget refusal should stop before edge reads")

        def read_typed_model(
            self,
            _model: type[SimulationResult],
            _ref: ArtifactRef,
        ) -> tuple[ArtifactManifest, SimulationResult, int, int]:
            raise AssertionError("budget refusal should stop before payload reads")

    try:
        admit_execution_source_bounded(_NoFallbackStore(), ref, reader=_BudgetRefusalReader())
    except ExecutionSourceBoundedReadRefusal as exc:
        assert exc.observed_bytes == 32
        assert exc.limit_bytes == 32
        assert exc.reason == "execution_source_read_budget_exhausted"
    else:
        raise AssertionError("bounded read budget refusal was swallowed")
