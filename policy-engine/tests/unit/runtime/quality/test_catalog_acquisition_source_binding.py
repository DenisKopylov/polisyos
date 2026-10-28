"""Selected-source identity is consumed by the real acquisition gateway."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.data_forge.read_api import catalog as catalog_api
from polisyos.fabric.retrieval.service import RetrievalService
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionPlannerBindingError,
    RealAcquisitionOwnerGateway,
    plan_requirement_gap_acquisition,
    requirement_gaps_from_compiled_specs,
)
from polisyos.runtime.quality.substrate_registry import (
    catalog_serving_source_scope,
)
from tests._helpers.catalog_source_admission import admit_fixture_catalog_source
from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner
from tests.unit.runtime.quality.test_acquisition_planner import (
    _catalog_capture_scope_profile,
    _compiled_requirement_specs,
    _install_recorded_file_catalog_supplier,
)


def _compiled_request() -> tuple[dict[str, Any], Any]:
    """Use an actual typed requirement and existing planner for the resolve-only call."""
    spec = _compiled_requirement_specs()[0].model_dump(mode="json")
    spec.update(
        {
            "requirement_id": "data-requirement:c32-selected-catalog",
            "claim_id": "claim:c32-selected-catalog",
            "required_data_families": ("metric.test",),
        }
    )
    spec["metadata"]["scope_profile"] = _catalog_capture_scope_profile()
    gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(spec,))[0]
    report = plan_requirement_gap_acquisition(
        run_id="c32-selected-catalog",
        requirement_gaps=(gap,),
        generated_at=datetime(2026, 7, 17, tzinfo=UTC),
    )
    assert len(report.acquisition_records) == 1
    return spec, report.acquisition_records[0]


@contextmanager
def _actual_graphs(tmp_path: Path):
    """Retain native owner bytes; admit an existing member without copying it."""
    with (
        build_recorded_file_fetch_owner(
            tmp_path / "selected", canonicalize_catalog_source=True, with_catalog_profile=True
        ) as owner,
        build_recorded_file_fetch_owner(
            tmp_path / "foreign", canonicalize_catalog_source=True, with_catalog_profile=True
        ) as foreign,
    ):
        source = admit_fixture_catalog_source(
            repo_root=tmp_path / "selected", database_path=owner.graph.database_path
        )
        selected_graph = catalog_api.DatasetCatalogGraph(
            source.database_path,
            source.index_dir,
            overlay_path=source.overlay_path,
        )
        foreign_graph = catalog_api.DatasetCatalogGraph(
            foreign.graph.database_path,
            foreign.index_dir,
            overlay_path=source.overlay_path,
        )
        different_overlay = catalog_api.DatasetCatalogGraph(
            source.database_path,
            source.index_dir,
            overlay_path=tmp_path / "other-absent-overlay.duckdb",
        )
        try:
            yield owner, foreign, source, selected_graph, foreign_graph, different_overlay
        finally:
            selected_graph.close()
            foreign_graph.close()
            different_overlay.close()


def _observe_actual_consumers(monkeypatch: pytest.MonkeyPatch) -> tuple[list[Any], list[Any]]:
    """Observe actual methods without replacing their result or source selection."""
    native_bindings: list[Any] = []
    resolutions: list[Any] = []
    original_bindings = catalog_api.DatasetCatalogGraph.resolve_metric_bindings
    original_resolve = RetrievalService.resolve

    def observe_bindings(self, metric_name, *, top_k=20):
        entry = {"path": self.database_path, "metric": metric_name, "rows": None}
        native_bindings.append(entry)
        rows = original_bindings(self, metric_name, top_k=top_k)
        entry["rows"] = tuple(rows)
        return rows

    def observe_resolution(self, request, *, run_profile=None):
        entry = {"request": request, "run_profile": run_profile, "response": None}
        resolutions.append(entry)
        response = original_resolve(self, request, run_profile=run_profile)
        entry["response"] = response
        return response

    monkeypatch.setattr(
        catalog_api.DatasetCatalogGraph, "resolve_metric_bindings", observe_bindings
    )
    monkeypatch.setattr(RetrievalService, "resolve", observe_resolution)
    return native_bindings, resolutions


def test_selected_actual_graph_is_consumed_by_real_acquisition_gateway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A selected owner reaches real native Catalog rows, with no fetch or authority claim."""
    _install_recorded_file_catalog_supplier(monkeypatch)
    spec, record = _compiled_request()
    with _actual_graphs(tmp_path) as (owner, foreign, source, graph, _other, _overlay):
        assert graph.read_source_identity == source.read_source_identity
        native_bindings, resolutions = _observe_actual_consumers(monkeypatch)
        factory_inputs: list[tuple[Path, Path]] = []

        def graph_factory(database_path: Path, index_dir: Path) -> object:
            factory_inputs.append((database_path, index_dir))
            return graph

        gateway = RealAcquisitionOwnerGateway(
            repo_root=source.repo_root,
            dataset_catalog_factory=graph_factory,
            catalog_serving_source=source,
            catalog_run_profile=source.catalog_run_profile,
        )
        with catalog_serving_source_scope(source):
            artifact = gateway.acquire(record=record, compiled_requirement_spec=spec)
        assert artifact is not None
        assert factory_inputs == [(source.database_path, source.database_path.parent)]
        assert len(resolutions) == 1
        request = resolutions[0]["request"]
        run_profile = resolutions[0]["run_profile"]
        actual_response = resolutions[0]["response"]
        assert actual_response is not None
        assert run_profile == source.catalog_run_profile
        assert tuple(need.metric for need in request.data_needs) == ("metric.test",)
        assert native_bindings
        assert all(entry["path"] == source.database_path for entry in native_bindings)
        assert all(entry["rows"] is not None for entry in native_bindings)
        actual_rows = [
            row
            for entry in native_bindings
            if entry["metric"] == "metric.test"
            for row in entry["rows"]
        ]
        assert {row.catalog_dataset_id for row in actual_rows} == {
            "catalog-primary",
            "catalog-fallback",
        }
        response = artifact.payload["owner_response"]
        assert response["owner_response_kind"] == "fabric_catalog_resolution"
        assert response["families"] == ["metric.test"]
        assert response["candidate_only"] is True
        assert response["fetch_plan_count"] == len(actual_response.fetch_plans)
        assert response["candidate_count"] == len(actual_response.candidates)
        assert artifact.payload["acquired_substrate_registrations"] == []
        assert artifact.payload["candidate_bindings"] == []
        assert gateway.network_counter.network_calls == 0
        assert owner.requests == foreign.requests == []


@pytest.mark.parametrize(
    ("substitution", "expected_code"),
    [
        ("foreign_native", "catalog_source_graph_binding_mismatch"),
        ("different_overlay", "catalog_source_graph_binding_mismatch"),
        ("forged_owner", "catalog_source_graph_owner_unverified"),
    ],
)
def test_real_acquisition_gateway_refuses_unbound_graph_before_any_consumer_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, substitution: str, expected_code: str
) -> None:
    """Foreign native owners and shape-matching imposters cannot enter resolution."""
    _install_recorded_file_catalog_supplier(monkeypatch)
    spec, record = _compiled_request()
    with _actual_graphs(tmp_path) as (owner, foreign, source, _graph, other, overlay):

        class PathAndIdentityImposter:
            """Keep selected markers but delegate real reads to a foreign native owner."""

            database_path = source.database_path
            database_identity = source.read_source_identity[0]
            read_source_identity = source.read_source_identity
            overlay_path = source.overlay_path

            def __getattr__(self, name: str) -> Any:
                return getattr(other, name)

        graph = {
            "foreign_native": other,
            "different_overlay": overlay,
            "forged_owner": PathAndIdentityImposter(),
        }[substitution]
        native_bindings, resolutions = _observe_actual_consumers(monkeypatch)
        gateway = RealAcquisitionOwnerGateway(
            repo_root=source.repo_root,
            dataset_catalog_factory=lambda _database, _index: graph,
            catalog_serving_source=source,
            catalog_run_profile=source.catalog_run_profile,
        )
        refusal: AcquisitionPlannerBindingError | None = None
        artifact = None
        with catalog_serving_source_scope(source):
            try:
                artifact = gateway.acquire(record=record, compiled_requirement_spec=spec)
            except AcquisitionPlannerBindingError as exc:
                refusal = exc
        # With the guard removed, real resolution may return a limited candidate;
        # that is still a forbidden use of an unbound source, never a PASS here.
        assert refusal is not None, {
            "message": "selected graph binding must refuse before real consumer use",
            "native_binding_calls": len(native_bindings),
            "resolution_calls": len(resolutions),
            "native_paths": tuple(str(entry["path"]) for entry in native_bindings),
            "owner_response_kind": (
                None
                if artifact is None
                else artifact.payload["owner_response"]["owner_response_kind"]
            ),
        }
        assert refusal.source_refusal_code == expected_code
        assert artifact is None
        assert native_bindings == []
        assert resolutions == []
        assert gateway.network_counter.network_calls == 0
        assert owner.requests == foreign.requests == []


@pytest.mark.parametrize("capture_mode", ["resolve_only", "persisted_capture"])
@pytest.mark.parametrize(
    ("fault", "expected_code"),
    [
        ("wal", "catalog_read_source_checkpoint_required"),
        ("missing", "catalog_read_source_unavailable"),
        ("closed", "catalog_read_native_query_unavailable"),
    ],
)
def test_real_gateway_preserves_source_fault_after_selection_before_actual_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
    expected_code: str,
    capture_mode: str,
) -> None:
    """A real file-state change after the gateway guard cannot become empty data."""
    _install_recorded_file_catalog_supplier(monkeypatch)
    spec, record = _compiled_request()
    if capture_mode == "persisted_capture":
        spec["metadata"]["fabric_capture_mode"] = "persisted_payload"
    with _actual_graphs(tmp_path) as (owner, foreign, source, graph, _other, _overlay):
        original_resolve = RetrievalService.resolve
        entered: list[str] = []
        retained = tmp_path / "retained-source-fault"
        wal = source.database_path.with_name(source.database_path.name + ".wal")

        def disturb_only_the_actual_read(self, request, *, run_profile=None):
            entered.append(fault)
            if fault == "wal":
                wal.write_bytes(b"controlled uncheckpointed owner state")
            elif fault == "missing":
                source.database_path.replace(retained)
            else:
                graph.close()
            try:
                return original_resolve(self, request, run_profile=run_profile)
            finally:
                if fault == "wal":
                    wal.replace(retained)
                elif fault == "missing":
                    retained.replace(source.database_path)

        monkeypatch.setattr(RetrievalService, "resolve", disturb_only_the_actual_read)
        gateway = RealAcquisitionOwnerGateway(
            repo_root=source.repo_root,
            artifact_store=FileSystemCAS(tmp_path / "capture-cas"),
            dataset_catalog_factory=lambda _database, _index: graph,
            catalog_serving_source=source,
            catalog_run_profile=source.catalog_run_profile,
        )
        failure = None
        with catalog_serving_source_scope(source):
            try:
                gateway.acquire(record=record, compiled_requirement_spec=spec)
            except Exception as exc:
                failure = exc
        assert entered == [fault]
        assert isinstance(failure, AcquisitionPlannerBindingError), {
            "message": "actual gateway source fault must use the binding-error adapter",
            "actual_exception_type": None if failure is None else type(failure).__name__,
            "actual_source_code": getattr(failure, "code", None),
        }
        assert failure.source_refusal_code == expected_code
        assert isinstance(failure.__cause__, catalog_api.CatalogReadSourceError)
        assert failure.__cause__.code == expected_code
        assert owner.requests == foreign.requests == []
        assert gateway.network_counter.network_calls == 0


@pytest.mark.parametrize("capture_mode", ["resolve_only", "persisted_capture"])
def test_actual_gateway_keeps_unrelated_provider_failure_behavior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capture_mode: str,
) -> None:
    """A provider's code-shaped label cannot become a typed Catalog source refusal."""
    _install_recorded_file_catalog_supplier(monkeypatch)
    spec, record = _compiled_request()
    if capture_mode == "persisted_capture":
        spec["metadata"]["fabric_capture_mode"] = "persisted_payload"

    class MisleadingProviderError(RuntimeError):
        code = "catalog_read_source_unavailable"

    failure = MisleadingProviderError("unrelated optional provider unavailable")
    entered = []

    def unrelated_provider(self, request, *, run_profile=None):
        entered.append((request, run_profile))
        raise failure

    monkeypatch.setattr(RetrievalService, "resolve", unrelated_provider)
    with _actual_graphs(tmp_path) as (owner, foreign, source, graph, _other, _overlay):
        gateway = RealAcquisitionOwnerGateway(
            repo_root=source.repo_root,
            artifact_store=FileSystemCAS(tmp_path / "capture-cas"),
            dataset_catalog_factory=lambda _database, _index: graph,
            catalog_serving_source=source,
            catalog_run_profile=source.catalog_run_profile,
        )
        with catalog_serving_source_scope(source):
            if capture_mode == "persisted_capture":
                assert gateway.acquire(record=record, compiled_requirement_spec=spec) is None
            else:
                with pytest.raises(RuntimeError) as caught:
                    gateway.acquire(record=record, compiled_requirement_spec=spec)
                assert caught.value is failure
                assert not isinstance(caught.value, AcquisitionPlannerBindingError)
        assert len(entered) == 1
        assert owner.requests == foreign.requests == []
        assert gateway.network_counter.network_calls == 0
