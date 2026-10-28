"""Integration coverage for the persisted N7 basis at served route intake."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from tests._helpers.acquisition_served_history import (
    REPO_ROOT,
    _produce_served_acquisition_history,
)

pytest_plugins = ("tests._helpers.acquisition_served_history",)


def _b09_semantic_basis(record: dict[str, object]) -> str:
    """Independently bind the selected rule and canonical row content.

    Observation IDs and request/event occurrence metadata are deliberately not
    part of this test oracle. The canonical row fields remain fully included.
    """
    import hashlib
    import json

    rule = record["rule_projection"]
    rows = record["rows"]
    assert isinstance(rule, dict)
    assert isinstance(rows, list)
    canonical_rows = []
    for row in rows:
        assert isinstance(row, dict)
        semantic_row = {key: value for key, value in row.items() if key != "observation_id"}
        canonical_rows.append(
            json.dumps(
                semantic_row,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        )
    payload = {
        "schema": "test-only.e02.b09.semantic-basis.v1",
        "rule": rule,
        "rows": sorted(canonical_rows),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def test_served_acquisition_binds_n7_compiler_and_planner_cas_before_reentry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway: object,
) -> None:
    """The ordinary served route consumes owner-read N7 reports and re-enters N5.

    The two missing-read probes keep every ref, schema marker, and embedded
    report intact while removing only the selected planner or compiler CAS
    bytes from the actual route resolver. The B09 pair compares the real
    generation-2 reentry with the generation-3 no-growth occurrence; it does
    not claim a second source fetch.
    """

    import json
    from pathlib import Path

    from polisyos.core import canon
    from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key
    from polisyos.core.contracts.runtime import RunCandidateSimulationAcquisitionHistoryEntry
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_requirement import DataRequirementCompilationReport
    from polisyos.runtime.quality.acquisition_planner import (
        load_acquisition_planner_report,
        validate_persisted_acquisition_planner_report,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionRouteClosureError,
        AcquisitionRouteLoop,
        AcquisitionRouteLoopReceipt,
        VerifiedAcquisitionRouteClosure,
    )
    from polisyos.runtime.quality.generation_cycle import AcquisitionOverlayReentryReceipt

    resolved: list[tuple[AcquisitionRouteLoop, VerifiedAcquisitionRouteClosure]] = []
    removal_controls: set[str] = set()
    original_resolve = AcquisitionRouteLoop.resolve_current_route

    def remove_one_cas_read(
        loop: AcquisitionRouteLoop,
        *,
        run_id: str,
        before_action_generation: int | None,
        action_job_id: str | None,
        target_ref: ArtifactRef,
        expected_code: str,
    ) -> None:
        target_id = target_ref.artifact_id
        target_identity = artifact_ref_identity_key(target_ref)
        original_get_bytes = loop._artifact_store.get_bytes

        def missing_selected_artifact(selector: object) -> bytes:
            selected_identity = (
                artifact_ref_identity_key(selector)
                if isinstance(selector, ArtifactRef)
                else str(selector)
            )
            if selected_identity == target_identity or selected_identity == str(target_id):
                raise FileNotFoundError("controlled_missing_bound_cas_object")
            return original_get_bytes(selector)

        with monkeypatch.context() as removal_patch:
            removal_patch.setattr(
                loop._artifact_store,
                "get_bytes",
                missing_selected_artifact,
            )
            with pytest.raises(AcquisitionRouteClosureError, match=expected_code):
                original_resolve(
                    loop,
                    run_id=run_id,
                    before_action_generation=before_action_generation,
                    action_job_id=action_job_id,
                )

    def capture_route(
        loop: AcquisitionRouteLoop,
        *,
        run_id: str,
        before_action_generation: int | None = None,
        action_job_id: str | None = None,
    ) -> VerifiedAcquisitionRouteClosure:
        closure = original_resolve(
            loop,
            run_id=run_id,
            before_action_generation=before_action_generation,
            action_job_id=action_job_id,
        )
        resolved.append((loop, closure))
        if not removal_controls:
            report = closure.planner_report
            basis_binding = report.requirement_basis_binding
            planner_ref = closure.route_source_cycle.acquisition_routing_report_ref
            assert basis_binding is not None
            assert planner_ref is not None
            assert report == closure.route_source_cycle.acquisition_routing_report

            with tenant_scope(None, tenant_id=closure.tenant_id, cell_id=closure.cell_id):
                assert (
                    validate_persisted_acquisition_planner_report(
                        loop._artifact_store,
                        planner_ref,
                        report,
                        expected_scenario_id=closure.design_problem.design_problem_id,
                        expected_compiled_requirement_ref=(
                            closure.planner_record.compiled_requirement_ref
                        ),
                    )
                    == ()
                )
                persisted_report = load_acquisition_planner_report(
                    loop._artifact_store,
                    planner_ref,
                )
                assert persisted_report == report
                compiler_report = DataRequirementCompilationReport.model_validate(
                    canon.from_canonical_bytes(
                        loop._artifact_store.get_bytes(basis_binding.compiler_report_ref)
                    )
                )

            assert type(compiler_report) is DataRequirementCompilationReport
            assert compiler_report.scenario_id == closure.design_problem.design_problem_id
            assert basis_binding.scenario_id == compiler_report.scenario_id
            assert basis_binding.producer_report_ref == compiler_report.producer_report_ref
            assert basis_binding.input_content_hash == compiler_report.input_content_hash
            assert basis_binding.resolution == compiler_report.requirement_basis
            assert f"run:{compiler_report.run_id}" in compiler_report.subject_refs
            assert f"scenario:{closure.design_problem.design_problem_id}" in (
                compiler_report.subject_refs
            )
            compiled_requirement_ids = {spec.requirement_id for spec in compiler_report.specs}
            assert closure.planner_record.compiled_requirement_ref in compiled_requirement_ids
            removal_controls.add("reports_bound_and_read_back")

            remove_one_cas_read(
                loop,
                run_id=run_id,
                before_action_generation=before_action_generation,
                action_job_id=action_job_id,
                target_ref=planner_ref,
                expected_code="acquisition_planner_report_readback_failed",
            )
            removal_controls.add("planner_cas_missing")
            remove_one_cas_read(
                loop,
                run_id=run_id,
                before_action_generation=before_action_generation,
                action_job_id=action_job_id,
                target_ref=basis_binding.compiler_report_ref,
                expected_code="n7_compiler_report_readback_failed",
            )
            removal_controls.add("compiler_cas_missing")
        return closure

    monkeypatch.setattr(AcquisitionRouteLoop, "resolve_current_route", capture_route)
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )

    source_inputs = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "served-candidate-source-root"
    )
    result = _produce_served_acquisition_history(
        tmp_path,
        monkeypatch,
        served_recorded_candidate_gateway,
        include_b09_evidence=True,
        source_owner_root=source_inputs.root,
        include_default_only_compiled_probe=True,
    )

    assert result is not None
    source_witness = json.loads(result["source_root_witness_json"])
    assert source_witness["source_root"] == str(source_inputs.root)
    assert Path(source_witness["selected_l1_dcat_path"]).is_relative_to(source_inputs.root)
    assert len(source_witness["selected_l1_dcat_sha256"]) == 64
    assert Path(source_witness["selected_l2_skg_path"]).is_relative_to(source_inputs.root)
    assert len(source_witness["selected_l2_source_sha256"]) == 64
    assert Path(source_witness["selected_l3_lex_path"]).is_relative_to(source_inputs.root)
    assert all(
        Path(source_witness["selected_l6_bundle_paths"][name]).is_relative_to(source_inputs.root)
        for name in (
            "intervention_knob_dictionary",
            "lex_intervention_map",
            "observation_to_contract_manifest",
        )
    )
    assert set(source_witness["selected_l3_row_counts"]) == {
        "lex_amendments",
        "lex_normative_ready_facts",
        "lex_reference_edges",
        "lex_rule_thresholds",
    }
    assert max(source_witness["selected_l3_row_counts"].values(), default=0) < 1000
    assert source_witness["selected_l6_bundle_content_hash"].startswith("sha256:")
    assert source_witness["catalog_selection"]["catalog_run_profile"] == "preflight_core"
    actual_krefs = source_witness["actual_kref_reads"]
    assert actual_krefs
    assert all(
        actual_kref["actual_build_repo_root"] == str(source_inputs.root)
        for actual_kref in actual_krefs
    )
    for actual_kref in actual_krefs:
        actual_catalog = actual_kref["l1_catalog"]
        assert actual_catalog["selection_owner"] == "catalog_serving_source_paths"
        assert actual_catalog["selection_basis"] == "explicit_path_candidate_only"
        assert actual_catalog["catalog_run_profile"] == "preflight_core"
        assert actual_catalog["source_database_path"] == source_witness["selected_l1_dcat_path"]
        assert actual_catalog["source_database_sha256"] == source_witness["selected_l1_dcat_sha256"]
        assert (
            actual_catalog["alignment_row_count"]
            == source_witness["selected_catalog_readback"]["alignment_row_count"]
        )
        assert (
            actual_catalog["alignment_rows_sha256"]
            == source_witness["selected_catalog_readback"]["alignment_rows_sha256"]
        )
        actual_l6 = actual_kref["l6_intervention"]
        assert actual_l6["actual_reader_witnesses"]
        assert (
            actual_l6["profile_bundle_content_hash"]
            == source_witness["selected_l6_bundle_content_hash"]
        )
        assert all(
            reader["bundle"] == source_witness["selected_l6_source_witness"]
            for reader in actual_l6["actual_reader_witnesses"]
        )
        assert all(
            reader["bundle"]["code_root"] == str(REPO_ROOT.resolve())
            and reader["bundle"]["source_owner_root"] == str(source_inputs.root)
            for reader in actual_l6["actual_reader_witnesses"]
        )
        assert actual_l6["candidate_input_counts"] == {
            "knob_dictionary": 0,
            "lex_intervention_map": 0,
            "observation_routes": 0,
        }
        assert (
            actual_l6["loaded_code_owner_authority"]["source_ref"]
            == (
                source_witness["selected_l6_source_witness"]["source_refs"][
                    "owner_authority_bindings"
                ]
            )
        )
        assert actual_l6["consumption_status"] == (
            "empty_candidate_data_no_kref_l6_projection_not_established"
        )
    assert removal_controls == {
        "reports_bound_and_read_back",
        "planner_cas_missing",
        "compiler_cas_missing",
    }
    assert resolved
    first_loop, initial = next(
        (loop, closure)
        for loop, closure in resolved
        if closure.source_cycle.cycle_index == closure.route_source_cycle_index
    )
    continued = max(
        (
            closure
            for _, closure in resolved
            if closure.source_cycle.cycle_index > closure.route_source_cycle_index
        ),
        key=lambda closure: closure.source_cycle.cycle_index,
    )
    assert continued.run_id == initial.run_id
    assert continued.route_id == initial.route_id
    assert continued.route_source_cycle == initial.source_cycle
    assert continued.source_cycle.cycle_index == initial.route_source_cycle_index + 1
    assert continued.source_cycle.selected_candidate_ref == (
        initial.source_cycle.selected_candidate_ref
    )
    prior_n5 = initial.source_cycle.simulation.candidate_simulation_n5_input_ref
    continued_n5 = continued.source_cycle.simulation.candidate_simulation_n5_input_ref
    prior_context = initial.source_cycle.simulation.candidate_simulation_context_job_ref
    continued_context = continued.source_cycle.simulation.candidate_simulation_context_job_ref
    assert prior_n5 is not None
    assert continued_n5 is not None
    assert prior_context is not None
    assert continued_context is not None
    assert artifact_ref_identity_key(prior_n5) != artifact_ref_identity_key(continued_n5)
    assert artifact_ref_identity_key(prior_context) != artifact_ref_identity_key(continued_context)
    assert first_loop._artifact_store is resolved[-1][0]._artifact_store

    import json

    b09 = json.loads(result["b09_evidence_json"])
    rule = b09["rule_projection"]
    rows = b09["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["canonical_var"] == "government.balance"
    assert row["source_watermark"]
    assert row["dataset_version"]
    assert b09["source_time_status"] == "not_established"
    assert "new_epoch_same_content_and_actual_changed_row_reissue_unrun" in (b09["limitations"])

    reentry = b09["occurrences"]["generation_2_reentry"]
    no_growth = b09["occurrences"]["generation_3_no_growth"]
    assert reentry["action_generation"] == 2
    assert no_growth["action_generation"] == 3
    assert reentry["route_receipt_ref"] != no_growth["route_receipt_ref"]
    assert reentry["route_manifest_created_at"] != no_growth["route_manifest_created_at"]
    assert reentry["n5_input_ref"] == no_growth["retained_n5_input_ref"]
    assert no_growth["new_n5_input_ref"] is None

    history_by_generation = {
        entry.action_generation: entry
        for entry in (
            RunCandidateSimulationAcquisitionHistoryEntry.model_validate(row)
            for row in b09["history_entries"]
        )
    }
    assert set(history_by_generation) == {1, 2, 3}
    route_views = {
        2: reentry["route_receipt_view"],
        3: no_growth["route_receipt_view"],
    }
    for generation, view in route_views.items():
        entry = history_by_generation[generation]
        route_ref = entry.route_receipt_ref
        assert route_ref.manifest_profile_sha256 is not None
        assert view["manifest_profile_sha256"] == route_ref.manifest_profile_sha256
        assert view["profile_bound_ref"] == route_ref.model_dump(mode="json")
        assert view["identity"] == list(artifact_ref_identity_key(route_ref))
        assert route_ref.kind == view["manifest_kind"]
        assert route_ref.media_type == view["manifest_media_type"]
        assert view["manifest_artifact_id"] == str(route_ref.artifact_id)
        assert view["payload_sha256"] == str(route_ref.artifact_id)
        assert view["receipt_action_generation"] == generation
        assert view["receipt_action_generation"] == entry.action_generation
        assert view["receipt_terminal_outcome"] == entry.terminal_outcome
        assert view["schema_name"] == (f"polisyos.runtime.{AcquisitionRouteLoopReceipt.__name__}")
        assert (
            view["schema_version"]
            == (
                AcquisitionRouteLoopReceipt.model_fields["schema_version"].default.rsplit("@", 1)[1]
            )
        )

    second_reentry_ref = history_by_generation[2].reentry_receipt_ref
    assert second_reentry_ref is not None
    reentry_view = reentry["reentry_receipt_view"]
    assert second_reentry_ref.manifest_profile_sha256 is not None
    assert reentry_view["manifest_profile_sha256"] == (second_reentry_ref.manifest_profile_sha256)
    assert reentry_view["profile_bound_ref"] == second_reentry_ref.model_dump(mode="json")
    assert reentry_view["identity"] == list(artifact_ref_identity_key(second_reentry_ref))
    assert reentry_view["manifest_artifact_id"] == str(second_reentry_ref.artifact_id)
    assert reentry_view["payload_sha256"] == str(second_reentry_ref.artifact_id)
    assert reentry_view["manifest_kind"] == second_reentry_ref.kind
    assert reentry_view["manifest_media_type"] == second_reentry_ref.media_type
    assert reentry_view["schema_name"] == (
        f"polisyos.runtime.{AcquisitionOverlayReentryReceipt.__name__}"
    )

    assert (
        "route_profile_is_reader_materialized_selected_manifest_view_not_producer_attestation"
        in (b09["limitations"])
    )
    assert no_growth["transport_call_count"] == 0
    assert no_growth["prior_growth_receipt_ref"] != no_growth["no_growth_receipt_ref"]

    generation_2_basis_record = {
        "rule_projection": rule,
        "rows": rows,
        "data_transaction_time": b09["data_transaction_time"],
        "occurrence": reentry,
    }
    generation_3_basis_record = {
        "rule_projection": rule,
        "rows": rows,
        "data_transaction_time": b09["data_transaction_time"],
        "occurrence": no_growth,
    }
    generation_2_basis = _b09_semantic_basis(generation_2_basis_record)
    assert generation_3_basis_record["occurrence"] != generation_2_basis_record["occurrence"]
    assert _b09_semantic_basis(generation_3_basis_record) == generation_2_basis

    # Oracle-only controls: occurrence ID/time do not change the basis, while
    # actual row-content and rule changes do. These controls are not producer
    # executions and do not establish a second acquisition or new-epoch path.
    later_occurrence_control = {
        **generation_3_basis_record,
        "rows": [
            {
                **row,
                "observation_id": row["observation_id"] + "-later-occurrence",
            }
        ],
        "data_transaction_time": b09["data_transaction_time"] + "-later",
        "occurrence": {
            **no_growth,
            "route_manifest_created_at": no_growth["route_manifest_created_at"] + "-later",
        },
    }
    assert _b09_semantic_basis(later_occurrence_control) == generation_2_basis

    content_change_control = {
        **generation_2_basis_record,
        "rows": [{**row, "value": float(row["value"]) + 0.5}],
    }
    assert _b09_semantic_basis(content_change_control) != generation_2_basis

    mapping = rule["candidate_refresh_mapping"]
    changed_mapping = {**mapping, "target_slot_id": mapping["target_slot_id"] + ".changed"}
    changed_rule_control = {
        **generation_2_basis_record,
        "rule_projection": {**rule, "candidate_refresh_mapping": changed_mapping},
    }
    assert _b09_semantic_basis(changed_rule_control) != generation_2_basis
