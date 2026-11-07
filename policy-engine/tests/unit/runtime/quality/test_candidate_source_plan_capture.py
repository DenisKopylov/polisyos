"""Exercise source-candidate constraints at the real local fetch owner boundary."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, PutOptions
from polisyos.runtime.quality.acquisition_planner import (
    RealAcquisitionOwnerGateway,
    acquisition_report_inputs,
    persist_and_verify_data_requirement_compilation_report,
    plan_requirement_gap_acquisition,
    requirement_gaps_from_compiled_specs,
)
from polisyos.runtime.quality.capability_index import CapabilitySourceAsset
from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
from tests.unit.fabric.catalog.test_data_requirement_adapter import _source_candidate_spec
from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner
from tests.unit.runtime.quality.test_acquisition_planner import (
    _install_recorded_file_catalog_supplier,
)


def test_actual_compiler_basis_writer_and_planner_edge_preserve_selected_profile(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts import input_ref_from_artifact_ref, load_core_json_artifact
    from polisyos.data_requirement import DataRequirementCompiler

    scenario = {
        "scenario_id": "declared-source-basis",
        "text": "Use declared annual country context for a candidate policy model.",
        "domain": "education_policy",
        "scope_profile": {
            "profile_id": "source:usa-2024",
            "jurisdiction": "USA",
            "population": "national_economy",
            "entity_scope": "country",
            "time_window": {"start": "2024-01-01", "end": "2024-12-31"},
            "time_role": "observation_time",
            "granularity": "annual",
            "required_constructs": ["economic.gdp"],
        },
    }
    compiler = DataRequirementCompiler(
        capability_resolver=RequirementToCapabilityResolver.governed_fixture(),
        require_capability_index=True,
    )
    compilation = compiler.compile_for_scenario(scenario)
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-source", cell_id="cell-source")
    basis = persist_and_verify_data_requirement_compilation_report(
        store, compilation, expected_scenario_id=scenario["scenario_id"]
    )
    assert basis.compiler_report_ref.manifest_profile_sha256 is not None
    fresh = load_core_json_artifact(
        FileSystemCAS(tmp_path / "cas").for_tenant("tenant-source", cell_id="cell-source"),
        basis.compiler_report_ref,
    )
    assert fresh["input_content_hash"] == compilation.input_content_hash
    planner = plan_requirement_gap_acquisition(
        run_id="run-bound-source",
        requirement_gaps=requirement_gaps_from_compiled_specs(
            data_requirement_specs=compilation.specs
        ),
        requirement_basis_binding=basis,
    )
    compiler_edges = [
        edge
        for edge in acquisition_report_inputs(planner)
        if edge.role == "data_requirement_compiler_report"
    ]
    assert compiler_edges == [
        input_ref_from_artifact_ref(
            basis.compiler_report_ref, role="data_requirement_compiler_report"
        )
    ]
    assert (
        compiler_edges[0].manifest_profile_sha256
        == basis.compiler_report_ref.manifest_profile_sha256
    )


@pytest.mark.parametrize(
    ("wrong_declared_target", "corrupt_lineage"),
    [(False, None), (True, None), (False, "fetched_payload"), (False, "catalog_binding")],
    ids=["positive", "wrong_source", "payload_profile_removed", "binding_profile_removed"],
)
def test_actual_local_fetch_consumes_declared_source_and_preserves_candidate_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    wrong_declared_target: bool,
    corrupt_lineage: str | None,
) -> None:
    """Metadata from discovery cannot silently select another actual source."""

    from polisyos.fabric.catalog.source_bindings import SourceBinding, SourceBindingCollection
    from polisyos.fabric.connectors import FileTabularConnector
    from polisyos.fabric.connectors.base import ConnectionConfig
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.fabric.connectors.sources import file_tabular
    from polisyos.fabric.retrieval.service import RetrievalService

    _install_recorded_file_catalog_supplier(monkeypatch)
    store_path = tmp_path / "runtime-cas"
    store = FileSystemCAS(store_path).for_tenant("tenant-candidate", cell_id="cell-candidate")

    class ReceiptMutationService(RetrievalService):
        """Delegate real execution, then present one validly stored corrupt manifest."""

        def execute_persisted_fetch_capture(self, plans, *, preflight, postflight):
            def inspect_receipt(view):
                if corrupt_lineage is None:
                    return postflight(view)
                metric = view.metrics[0]
                selected = metric.fetch_receipt_ref
                assert selected is not None
                ref = ArtifactRef(
                    artifact_id=selected.artifact_id,
                    kind=selected.kind,
                    media_type=selected.media_type,
                    manifest_profile_sha256=selected.manifest_profile_sha256,
                )
                manifest = store.get_manifest(ref)
                assert all(edge.manifest_profile_sha256 for edge in manifest.inputs)
                corrupted = store.put_bytes(
                    store.get_bytes(ref),
                    PutOptions(
                        kind=manifest.kind,
                        media_type=manifest.media_type,
                        schema=manifest.artifact_schema,
                        producer=manifest.producer,
                        inputs=[
                            edge.model_copy(update={"manifest_profile_sha256": None})
                            if edge.role == corrupt_lineage
                            else edge
                            for edge in manifest.inputs
                        ],
                    ),
                    return_selected_profile=True,
                )
                assert corrupted.artifact_id == ref.artifact_id
                assert corrupted.manifest_profile_sha256 != ref.manifest_profile_sha256
                changed_metric = replace(
                    metric,
                    fetch_receipt_ref=replace(
                        selected, manifest_profile_sha256=corrupted.manifest_profile_sha256
                    ),
                )
                return postflight(replace(view, metrics=(changed_metric,)))

            return super().execute_persisted_fetch_capture(
                plans, preflight=preflight, postflight=inspect_receipt
            )

    with build_recorded_file_fetch_owner(
        tmp_path / "source", canonicalize_catalog_source=True, catalog_connector_params={}
    ) as owner:
        # The capture policy requires the canonical connector class. Observe
        # actual file reads without substituting a successful connector result.
        registry = ConnectorRegistry()
        registry.register(FileTabularConnector, config=ConnectionConfig(url=str(owner.csv_path)))
        providers = replace(owner.providers, registry=registry)
        reads = []
        original_read = file_tabular.read_location_bytes

        async def observe_read(config, *args, **kwargs):
            reads.append(config.url)
            return await original_read(config, *args, **kwargs)

        monkeypatch.setattr(file_tabular, "read_location_bytes", observe_read)
        # Exercise the existing standalone curated-binding route. The separate
        # full Catalog publisher/currentness contract is not a premise here.
        # This is actual resolver input, not a patched successful resolve().
        curated = tmp_path / "production_data"
        curated.mkdir()
        (curated / "source_bindings.json").write_text(
            SourceBindingCollection(
                bindings=[
                    SourceBinding(
                        metric_id="metric.test",
                        connector_id="files.tabular",
                        dataset_id=str(owner.csv_path),
                        geography_patterns=["USA"],
                        granularity=["annual"],
                    )
                ]
            ).model_dump_json(),
            encoding="utf-8",
        )
        resolver = RequirementToCapabilityResolver.governed_fixture(
            Path(__file__).resolve().parents[4]
        )
        template = next(
            capability
            for capability in resolver.capabilities
            if capability.construct_id == "economic.gdp"
        )
        declared_target = str(owner.csv_path) + (".different" if wrong_declared_target else "")
        source = template.model_copy(
            update={
                "capability_id": "capability:controlled-local-file-candidate",
                "construct_id": "fixture.quantity",
                "scope": template.scope.model_copy(update={"population": "controlled_rows"}),
                "source_assets": (
                    CapabilitySourceAsset(
                        ref=owner.csv_path.as_uri(),
                        source_layer="controlled_test_fixture",
                        asset_type="test_owned_file",
                        role="source_candidate",
                        metadata={
                            "catalog_fetch_binding": {
                                "metric_id": "metric.test",
                                "connector_id": "files.tabular",
                                "dataset_id": declared_target,
                                "profile_id": None,
                            }
                        },
                    ),
                ),
                "limitations": ("Controlled test rows are not GDP or external source authority.",),
            }
        )
        payload = _source_candidate_spec(
            construct="fixture.quantity",
            family="controlled_file_family",
            population="controlled_rows",
            resolver=RequirementToCapabilityResolver(
                capabilities=(source,), capability_index_ref="capability-index:controlled-file"
            ),
        )
        payload["metadata"]["fabric_capture_mode"] = "persisted_payload"
        report = plan_requirement_gap_acquisition(
            run_id="run-declared-source",
            requirement_gaps=requirement_gaps_from_compiled_specs(
                data_requirement_specs=(payload,)
            ),
            generated_at=datetime(2026, 11, 3, tzinfo=UTC),
        )
        gateway = RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            artifact_store=store,
            dataset_catalog_factory=lambda _database, _index: owner.graph,
            retrieval_service_factory=lambda curated, artifact_store, graph: ReceiptMutationService(
                curated_dir=curated,
                artifact_store=artifact_store,
                dataset_catalog=graph,
                providers=providers,
            ),
            catalog_run_profile="prod_full",
            captured_at=datetime(2026, 11, 3, tzinfo=UTC),
        )

        artifact = gateway.acquire(
            record=report.acquisition_records[0], compiled_requirement_spec=payload
        )

        if wrong_declared_target:
            assert artifact is None
            assert reads == []
            assert "catalog_candidate_source_fetch_binding_mismatch" in caplog.text
            return
        if corrupt_lineage is not None:
            assert artifact is None
            assert reads
            assert "fabric_fetch_capture_receipt_lineage_mismatch" in caplog.text
            return
        assert artifact is not None, caplog.text
        response = artifact.payload["owner_response"]
        assert response["candidate_only"] is True
        assert (
            response["requirement_projection"]["candidate_discovery_satisfies_claim_evidence"]
            is False
        )
        assert response["candidate_count"] >= 1
        assert response["captured_fetch_count"] == 1
        captured = response["captured_fetches"][0]
        assert captured["plan"]["metric_id"] == "metric.test"
        assert captured["plan"]["dataset_id"] == declared_target
        assert reads and all(path == str(owner.csv_path) for path in reads)
        payload_ref = ArtifactRef.model_validate(captured["payload_ref"])
        first_bytes = store.get_bytes(payload_ref.artifact_id)
        fresh_store = FileSystemCAS(store_path).for_tenant(
            "tenant-candidate", cell_id="cell-candidate"
        )
        assert fresh_store.get_bytes(payload_ref.artifact_id) == first_bytes
        assert artifact.payload["acquired_substrate_registrations"] == []
        assert artifact.payload["candidate_bindings"] == []
