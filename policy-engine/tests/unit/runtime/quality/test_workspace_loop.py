from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.data_forge.read_api.catalog import build_slice0_fixture_catalog_graph
from polisyos.foundry.methods.catalog.causal._id_contracts import RequiredDataSpec
from polisyos.pdc import (
    ArtifactRef,
    CompositionCertificate,
    OperationClass,
    SearchLedger,
    SubDesignContract,
)
from polisyos.runtime.quality.data_forge_binding import MeasurementRootBindingError
from polisyos.runtime.quality.design_axes.coupling_composition import (
    CouplingEdge,
    CouplingGraph,
    build_coupling_graph,
)
from polisyos.runtime.quality.workspace import loop as workspace_loop
from polisyos.runtime.quality.workspace.loop import (
    ACTIVE_WORKSPACE_OPERATIONS,
    AcquisitionPlanner,
    ConnectorAdmissionGate,
    DataRequirementAdmissionGate,
    FormalGate,
    MeasurementRootProducer,
    SearchExitDecisionInputs,
    SemanticAdequacyGate,
    WorkspaceInvariantError,
    WorkspaceLoop,
    build_workspace_operation_registry,
    load_gy_semantic_benchmark,
    load_workspace_fixture_manifest,
    select_search_terminal,
)
from polisyos.scientist.agent.protocols import DataNeedSpec


def _observed_independent_graph(
    *,
    parent_workspace_id: str,
    children: list[SubDesignContract],
) -> CouplingGraph:
    source, target = (child.workspace_id for child in children[:2])
    return build_coupling_graph(
        design_ref=f"design://{parent_workspace_id}",
        module_refs=[child.workspace_id for child in children],
        module_discovery_ref=f"discovery://{parent_workspace_id}",
        interaction_edges=(
            CouplingEdge(
                boundary_ref=f"boundary://{parent_workspace_id}/observed-independent",
                source_module_ref=source,
                target_module_ref=target,
                relation="observed_independent_measurement",
                interaction_strength="none",
                evidence_ref=f"evidence://{parent_workspace_id}/independence",
            ),
        ),
        evidence_state="observed",
        rule_version_ref="policyos.gy.composition.test.v1",
    )


def test_workspace_loop_uses_canonical_slice0_catalog_builder() -> None:
    assert not hasattr(workspace_loop, "_InMemoryWorkspaceCatalogGraph")


def test_workspace_loop_search_ledger_extends_canonical_search_ledger() -> None:
    contract = WorkspaceLoop().run_fixture("ua_msme_credit_worldbank_measurement")

    assert isinstance(contract.search_ledger, SearchLedger)
    assert contract.search_ledger.ledger_ref
    assert contract.search_ledger.deterministic_replay_key


def test_slice0_fixture_manifest_drives_groundable_expectations() -> None:
    manifest = load_workspace_fixture_manifest("ua_msme_credit_worldbank_measurement")

    assert manifest.fixture_id == "ua_msme_credit_worldbank_measurement"
    assert manifest.expected_terminal == "grounded_partial_admissible"
    assert "grounded_admissible" in manifest.forbidden_terminals
    assert manifest.expected_connector_profile == "worldbank"
    assert manifest.expected_producer_root_kind == "measurement"


def test_slice0_catalog_builder_uses_representative_dataset_graph(tmp_path: Path) -> None:
    catalog = build_slice0_fixture_catalog_graph(tmp_path)
    hits = catalog.search_datasets(
        "Ukraine MSME credit access World Bank firm measurement",
        top_k=20,
        explain=True,
    )

    assert len(hits) >= 6
    assert len({hit.source for hit in hits}) >= 4
    assert {
        "catalog://worldbank/enterprise-surveys/ukraine/msme-credit-access",
        "catalog://worldbank/global-findex/ukraine-account-credit",
        "catalog://ilo/sme-finance/ukraine-credit-constraints",
    }.issubset({hit.id for hit in hits})
    assert {"tourism_attraction_reviews", "synthetic_llm_only_credit_claim"}.issubset(
        {hit.id for hit in hits}
    )


def test_slice0_registry_has_only_bind_estimate_verify_active() -> None:
    registry = build_workspace_operation_registry()

    assert registry.active_operation_classes() == ACTIVE_WORKSPACE_OPERATIONS
    assert registry.get("slice0.bind.catalog").executable is True
    assert registry.get("slice0.estimate.measurement_summary").executable is True
    assert registry.get("slice0.verify.authority").executable is True
    acquisition = registry.get("slice0.acquire.costed_plan")
    assert acquisition.executable is False
    assert acquisition.operation_class.value == "ACQUIRE"
    assert acquisition.fail_closed_reason
    assert acquisition.discovery_evidence["adapter_conformance"]["passed"] is True
    assert registry.get("slice0.discover.stub").fail_closed_reason
    assert registry.get("slice0.decompose.workspace_tree").executable is True
    assert registry.get("slice0.compose.certificate").executable is True
    assert OperationClass.DECOMPOSE not in registry.active_operation_classes()
    assert OperationClass.COMPOSE not in registry.active_operation_classes()

    for operation_id in (
        "slice0.bind.catalog",
        "slice0.estimate.measurement_summary",
        "slice0.verify.authority",
        "slice0.acquire.costed_plan",
    ):
        registration = registry.get(operation_id)
        assert registration.discovered_from.startswith("engine_registry:")
        assert registration.discovery_evidence["source_kind"] in {
            "data_forge_catalog_source_registry",
            "foundry_method_registry",
            "pdc_contract_registry",
            "scientist_data_need_protocol",
        }
        assert registration.discovery_evidence["source_ref"]
        assert registration.discovery_evidence["adapter_conformance"]["passed"] is True
        assert registration.contract.formal_preconditions


def test_workspace_loop_decomposes_children_and_composes_certificate() -> None:
    loop = WorkspaceLoop()
    children = loop.decompose_fixture(
        parent_workspace_id="ws-gyg-independent",
        child_fixture_ids=[
            "ua_msme_credit_worldbank_measurement",
            "ua_msme_credit_worldbank_measurement",
        ],
    )
    graph = _observed_independent_graph(
        parent_workspace_id="ws-gyg-independent",
        children=children,
    )
    certificate = loop.compose_subdesigns(
        parent_workspace_id="ws-gyg-independent",
        subdesigns=children,
        graph=graph,
        claims=[],
    )

    assert all(isinstance(child, SubDesignContract) for child in children)
    assert isinstance(certificate, CompositionCertificate)
    assert certificate.verdict == "composable"
    assert certificate.composition_receipt_ref
    assert certificate.coupling_gate["verdict"] == "valid"


def test_child_acquisition_required_forces_parent_to_fund_cap_or_escalate() -> None:
    loop = WorkspaceLoop()
    children = loop.decompose_fixture(
        parent_workspace_id="ws-recursive-parent",
        child_fixture_ids=[
            "ua_msme_credit_worldbank_measurement",
            "tourism_local_development_ceiling_probe",
        ],
    )
    graph = _observed_independent_graph(
        parent_workspace_id="ws-recursive-parent",
        children=children,
    )
    certificate = loop.compose_subdesigns(
        parent_workspace_id="ws-recursive-parent",
        subdesigns=children,
        graph=graph,
        claims=[],
    )

    assert certificate.verdict == "not_composable"
    assert certificate.authority_flow == []
    assert "child_acquisition_required" in {
        obligation.obligation_type for obligation in certificate.unresolved_obligations
    }


def test_slice0_groundable_fixture_exits_partial_without_design_candidate() -> None:
    contract = WorkspaceLoop().run_fixture("ua_msme_credit_worldbank_measurement")

    assert contract.terminal_state["kind"] == "grounded_partial_admissible"
    assert contract.authority_boundary is not None
    assert contract.authority_boundary.evidence_kind == "measurement"
    assert contract.authority_boundary.decision_grade == "descriptive_only"
    assert contract.authority_boundary.decision_grade != "decision_admissible"
    assert "publication_without_limitation" in contract.authority_boundary.may_not_use_for
    assert "Slice-0 estimate-port authority only." in contract.authority_boundary.known_limits
    assert contract.frontier_snapshot.promoted_candidates
    assert contract.search_ledger.replay_levels == ["A", "B", "C"]
    assert all(result.checked_preconditions for result in contract.search_ledger.applicability_results)
    assert {result.status for result in contract.search_ledger.applicability_results} == {"applicable"}
    assert {
        item["predicate_id"]
        for result in contract.search_ledger.applicability_results
        for item in result.checked_preconditions
    } >= {
        "slice0.catalog_binding_expected",
        "slice0.estimate_input_dataset",
        "slice0.verify_authority_boundary",
    }
    assert all(ref.artifact_type != "DesignCandidate" for ref in contract.output_artifacts)


def test_formal_gate_fails_without_required_runtime_facts() -> None:
    registry = build_workspace_operation_registry()
    registration = registry.get("slice0.bind.catalog")

    result = FormalGate().evaluate(
        registration=registration,
        invocation_id="invoke-bind",
        result_id="applicability-bind",
        facts={
            "slice0.catalog_binding_expected": {
                "passed": True,
                "evidence_ref": "manifest:ua_msme_credit_worldbank_measurement",
            }
        },
    )

    assert result.status == "repair_required"
    assert result.failed_preconditions == [
        {
            "predicate_id": "slice0.source_contract_facets_complete",
            "reason": "missing_runtime_fact",
            "severity": "hard",
        }
    ]


def test_slice0_tourism_fixture_exits_search_ceiling() -> None:
    contract = WorkspaceLoop().run_fixture("tourism_local_development_ceiling_probe")

    assert contract.terminal_state["kind"] == "acquisition_required"
    assert contract.authority_boundary is None
    assert contract.incompleteness_record.ceiling_classification == "search_ceiling"
    assert contract.terminal_state["costed_plan"]["missing_distribution"] == (
        "local_tourism_site_traffic"
    )


def test_loop_terminal_precedence_blocks_acquisition_when_ceiling_is_unrepaired() -> None:
    contract = WorkspaceLoop().run_fixture(
        "tourism_local_development_ceiling_probe",
        search_quality_override={
            "recall_at_known_seeds": 0.0,
            "known_seeds_missed": ["forced-missed-seed"],
            "freshness_ok": False,
        },
        acquisition_policy="auto",
    )

    assert contract.terminal_state["kind"] == "search_ceiling_repair_required"
    assert contract.voi_audit.selected_terminal == "search_ceiling_repair_required"
    assert contract.next_best_actions[0]["costed_plan"]["missing_distribution"] == (
        "local_tourism_site_traffic"
    )


def test_slice0_poor_recall_routes_to_search_ceiling_repair_required() -> None:
    contract = WorkspaceLoop().run_fixture(
        "ua_msme_credit_worldbank_measurement",
        search_quality_override={
            "recall_at_known_seeds": 0.0,
            "known_seeds_missed": [
                "catalog://worldbank/enterprise-surveys/ukraine/msme-credit-access"
            ],
        },
    )

    assert contract.terminal_state["kind"] == "search_ceiling_repair_required"
    assert contract.authority_boundary is None
    assert contract.incompleteness_record.search_quality["known_seeds_missed"]
    assert "search_quality.min_recall_at_known_seeds" in contract.budget_ledger["exhausted"]


def test_slice0_semantic_benchmark_feeds_incompleteness_record(tmp_path: Path) -> None:
    catalog = build_slice0_fixture_catalog_graph(tmp_path)
    contract = WorkspaceLoop(catalog_graph=catalog).run_fixture(
        "ua_msme_credit_worldbank_measurement"
    )

    benchmark_run = contract.incompleteness_record.search_quality["semantic_benchmark_run"]

    assert benchmark_run["benchmark_id"] == "layer3_gy_slice0_semantic_adequacy_v1"
    assert benchmark_run["benchmark_ref"] == "architecture/policy_design_case/layer3_gy_semantic_benchmark.json"
    assert benchmark_run["benchmark_version"] == "policyos.policy_design_case.layer3_gy.semantic_benchmark.v1"
    assert benchmark_run["label_owner"] == "team-runtime-quality"
    assert benchmark_run["reviewer"] == "policy-design-case-verifier"
    assert benchmark_run["queries"] == ["Ukraine MSME credit access World Bank firm measurement"]
    assert benchmark_run["returned_hits"]
    assert benchmark_run["threshold_disposition"] == "pass"
    assert benchmark_run["recall_at_known_seeds"] == 1.0


def test_slice0_acquire_continuation_emits_costed_acquisition_required_terminal() -> None:
    contract = WorkspaceLoop().run_fixture("tourism_local_development_ceiling_probe")

    assert contract.terminal_state["kind"] == "acquisition_required"
    assert contract.terminal_state["costed_plan"]["rung"] == 7
    assert (
        contract.terminal_state["costed_plan"]["missing_distribution"]
        == "local_tourism_site_traffic"
    )
    assert contract.voi_audit.selected_terminal == "acquisition_required"
    assert contract.voi_audit.deterministic_voi_inputs["missing_distribution"] == (
        "local_tourism_site_traffic"
    )
    assert (
        contract.voi_audit.selected_action["operation_proposal_ref"]
        == "slice0.acquire.costed_plan"
    )
    assert contract.voi_audit.cost_basis["money_usd"] == 3640.0
    assert contract.voi_audit.cost_basis["basis_ref"] == (
        "gap-cost-basis:local_tourism_site_traffic:v1"
    )
    assert contract.next_best_actions[0]["data_need_spec"]["metric"] == "local_tourism_site_traffic"
    assert OperationClass.ACQUIRE.value not in contract.incompleteness_record.coverage[
        "operations_attempted"
    ]
    assert all(
        invocation.operation_id != "slice0.acquire.costed_plan"
        for invocation in contract.search_ledger.invocations
    )
    assert all(
        event.operation_invocation_ref != "invoke-acquire"
        for event in contract.search_ledger.events
    )


def test_slice0_groundable_contract_carries_authority_derivation_trace() -> None:
    contract = WorkspaceLoop().run_fixture("ua_msme_credit_worldbank_measurement")

    assert contract.authority_derivation_traces
    trace = contract.authority_derivation_traces[0]
    assert trace.computed_evidence_kind == "measurement"
    assert trace.computed_decision_grade == "descriptive_only"
    assert trace.transform_mismatch_disposition == "downgraded"
    assert trace.output_artifact_ref.artifact_type == "Estimate"
    assert trace.resulting_authority_boundary_ref == contract.authority_boundary.boundary_id


def test_search_ceiling_does_not_mint_measurement_authority() -> None:
    class _NoHitCatalog:
        def search_datasets(self, *_args, **_kwargs):
            return []

    contract = WorkspaceLoop(catalog_graph=_NoHitCatalog()).run_fixture(
        "ua_msme_credit_worldbank_measurement"
    )

    assert contract.terminal_state["kind"] == "search_ceiling_repair_required"
    assert contract.authority_boundary is None
    assert contract.evidence_kind is None
    assert contract.decision_grade == "unsupported"
    assert contract.evidence_ladder_rung == "none"
    assert contract.incompleteness_record.search_quality["known_seeds_missed"]
    assert contract.authority_derivation_traces == []
    assert not any(
        root.artifact_type == "MeasurementRoot"
        for envelope in contract.artifact_envelopes
        for root in envelope.producer_roots
    )


def test_anytime_terminal_precedence_prefers_spec_gap_then_search_ceiling() -> None:
    spec_gap = select_search_terminal(
        SearchExitDecisionInputs(
            verifier_gap=True,
            poor_recall=True,
            acquisition_required=True,
            positive_terminal="grounded_partial_admissible",
        )
    )
    assert spec_gap.kind == "a_spec_gap"

    poor_recall = select_search_terminal(
        SearchExitDecisionInputs(
            recall_at_known_seeds=0.2,
            recall_threshold=0.8,
            freshness_ok=True,
            acquisition_required=True,
            positive_terminal="grounded_abstention",
        )
    )
    assert poor_recall.kind == "search_ceiling_repair_required"


def test_slice0_rejects_non_active_operation_execution() -> None:
    loop = WorkspaceLoop()

    with pytest.raises(WorkspaceInvariantError, match="non-active operation"):
        loop.run_fixture(
            "ua_msme_credit_worldbank_measurement",
            forced_operation_classes=["BIND", "ACQUIRE", "VERIFY"],
        )

    with pytest.raises(WorkspaceInvariantError, match="non-active operation"):
        loop.operation_registry.executable_for_class(OperationClass.ACQUIRE)


def test_slice0_rejects_design_candidate_output_at_exit_boundary(monkeypatch) -> None:
    original = WorkspaceLoop._build_artifacts

    def _build_design_candidate(self, manifest, terminal_kind):
        artifacts = original(self, manifest, terminal_kind)
        design_ref = ArtifactRef.from_payload(
            artifact_id="design-probe",
            artifact_type="DesignCandidate",
            payload={"fixture_id": manifest.fixture_id},
            schema_ref="policyos.gy.probe.v1",
            uri="gy://slice0/probe/design-candidate",
            version="v1",
        )
        artifacts["estimate"] = artifacts["estimate"].model_copy(update={"ref": design_ref})
        return artifacts

    monkeypatch.setattr(WorkspaceLoop, "_build_artifacts", _build_design_candidate)

    with pytest.raises(WorkspaceInvariantError, match="DesignCandidate"):
        WorkspaceLoop().run_fixture("ua_msme_credit_worldbank_measurement")


def test_slice0_contract_materializes_workspace_certificate_and_obligation() -> None:
    groundable = WorkspaceLoop().run_fixture("ua_msme_credit_worldbank_measurement")

    assert groundable.workspace_contract.workspace_id == groundable.workspace_id
    assert groundable.workspace_contract_ref.startswith("sha256:")
    certified = next(
        envelope
        for envelope in groundable.artifact_envelopes
        if envelope.ref.artifact_type == "Estimate"
    )
    assert certified.certified_operation_envelope is not None
    assert certified.certified_operation_envelope.certified_for == [
        "slice0_estimate_port_authority"
    ]
    assert certified.verification.latest_applicability_result == "applicability-verify"

    ceiling = WorkspaceLoop().run_fixture("tourism_local_development_ceiling_probe")

    assert ceiling.obligation_records
    assert ceiling.obligation_records[0].obligation_type == "acquisition_required"
    assert ceiling.obligation_records[0].status == "open"


def test_slice0_rejects_agent_or_playbook_planner() -> None:
    loop = WorkspaceLoop()

    with pytest.raises(WorkspaceInvariantError, match="SeedTrajectoryPlanner"):
        loop.run_fixture("ua_msme_credit_worldbank_measurement", planner_kind="agent")


def test_measurement_root_producer_resolves_catalog_and_persists_cas(tmp_path: Path) -> None:
    catalog = build_slice0_fixture_catalog_graph(tmp_path)
    store = FileSystemCAS(tmp_path / "cas")
    manifest = load_workspace_fixture_manifest("ua_msme_credit_worldbank_measurement")

    envelope = MeasurementRootProducer(artifact_store=store).produce_from_catalog(
        manifest,
        catalog,
    )

    assert envelope.ref.artifact_type == "BaseDataset"
    assert envelope.payload_ref.startswith("sha256:")
    assert envelope.producer_roots
    assert envelope.producer_roots[0].artifact_type == "MeasurementRoot"
    assert (
        envelope.created_by["component"]
        == "polisyos.runtime.quality.data_forge_binding.MeasurementRootProducer"
    )
    assert envelope.producer_operation["operation_id"] == "slice0.bind.catalog"

    payload = json.loads(store.get_bytes(envelope.payload_ref))
    assert payload["data_requirement_spec"]["schema_version"] == "policyos.data_requirement_spec.v1"
    assert payload["source_contract_requirement"]["facet_values"]["connector"] == "worldbank.wdi"
    assert payload["source_contract_requirement"]["facet_values"]["variables"] == [
        "country_code",
        "year",
        "formal_borrowing",
        "account_ownership",
    ]
    assert all(
        not str(value).startswith("facet:")
        for value in payload["source_contract_requirement"]["facet_values"].values()
        if isinstance(value, str)
    )
    assert payload["measurement_rows"]
    assert payload["measurement_rows"][0]["evidence_kind"] == "measurement"
    assert payload["measurement_rows"][0]["source_ref"].startswith("https://api.worldbank.org/")


def test_measurement_root_producer_rejects_fabricated_source_contract_before_cas(
    tmp_path: Path,
) -> None:
    manifest = load_workspace_fixture_manifest("ua_msme_credit_worldbank_measurement")
    store = FileSystemCAS(tmp_path / "cas")

    class FakeRecord:
        id = manifest.expected_catalog_binding_refs[0]
        source = "worldbank"
        execution_tier = "transport_ready"
        connector_type = "worldbank.wdi"

        def model_dump(self, *, mode: str) -> dict[str, object]:
            return {
                "id": self.id,
                "source": self.source,
                "execution_tier": self.execution_tier,
                "connector_type": self.connector_type,
                "source_dataset_id": "",
                "variables": [],
                "coverage": {},
                "quality": {},
                "access": {},
                "license": "",
                "update_frequency": "",
            }

    class FakeDistribution:
        def model_dump(self, *, mode: str) -> dict[str, object]:
            return {
                "connector_type": "worldbank.wdi",
                "source_locator": "",
                "quality_score": None,
            }

    class FakeGraph:
        def search_datasets(self, query: str, *, top_k: int, explain: bool) -> list[FakeRecord]:
            return [FakeRecord()]

        def get_distributions(self, dataset_id: str) -> list[FakeDistribution]:
            return [FakeDistribution()]

        def resolve_fetch_target(self, dataset_id: str) -> object | None:
            return None

    with pytest.raises(MeasurementRootBindingError, match="source-contract admission failed"):
        MeasurementRootProducer(artifact_store=store).produce_from_catalog(
            manifest=manifest,
            catalog_graph=FakeGraph(),
        )

    assert not any(path.is_file() for path in (tmp_path / "cas").rglob("*"))


def test_connector_and_source_contract_admission_fail_closed() -> None:
    connector_gate = ConnectorAdmissionGate()

    assert connector_gate.evaluate("worldbank.wdi").status == "applicable"
    assert connector_gate.evaluate("rest.json").status == "repair_required"
    assert connector_gate.evaluate("unpd").status == "repair_required"
    assert connector_gate.evaluate("ukons").status == "repair_required"

    admission = DataRequirementAdmissionGate().evaluate(
        {
            "requirement_id": "req-incomplete",
            "claim_id": "claim-tourism",
            "mandatory_facets": ["construct", "scope", "source_contract"],
            "facet_refs": {"construct": "facet:tourism"},
        }
    )

    assert admission.status == "repair_required"
    assert {item["facet"] for item in admission.failed_preconditions} >= {
        "scope",
        "source_contract",
    }


def test_source_contract_admission_rejects_refs_only_full_facet_set() -> None:
    facets = (
        "authority_profile",
        "connector",
        "construct",
        "coverage",
        "freshness",
        "granularity",
        "jurisdiction",
        "license",
        "lineage",
        "population",
        "quality_floor",
        "rule_version",
        "scope",
        "source_class",
        "source_contract",
        "time_horizon",
        "variables",
    )
    admission = DataRequirementAdmissionGate().evaluate(
        {
            "requirement_id": "req-refs-only",
            "claim_id": "claim-refs-only",
            "mandatory_facets": list(facets),
            "metadata": {
                "gy_source_contract": {
                    "facet_refs": {facet: f"facet:{facet}" for facet in facets},
                    "facet_values": {},
                }
            },
        }
    )

    assert admission.status == "repair_required"
    assert {item["reason"] for item in admission.failed_preconditions} == {
        "missing_semantic_source_contract_value"
    }


def test_semantic_adequacy_benchmark_rejects_negative_control_and_records_recall() -> None:
    benchmark = load_gy_semantic_benchmark()
    run = SemanticAdequacyGate(benchmark).evaluate(
        construct_scope="ua_msme_credit_worldbank_measurement",
        returned_hits=[
            {
                "dataset_id": "tourism_attraction_reviews",
                "calibrated_relevance": 0.95,
            }
        ],
    )

    assert benchmark.label_owner
    assert benchmark.reviewer
    assert benchmark.catalog_corpus_kind == "slice0_representative_fixture_corpus"
    assert benchmark.closure_scope == "slice0_gate_only"
    assert {"F4", "F7"}.issubset(set(benchmark.open_production_findings))
    assert run.catalog_corpus_kind == "slice0_representative_fixture_corpus"
    assert run.closure_scope == "slice0_gate_only"
    assert run.threshold_disposition == "fail"
    assert run.negative_controls_passed == ["tourism_attraction_reviews"]
    assert run.recall_at_known_seeds == 0.0


def test_semantic_benchmark_uses_multiple_known_seeds_and_negative_controls() -> None:
    benchmark = load_gy_semantic_benchmark()
    credit_label = next(
        label
        for label in benchmark.labels
        if label["fixture_id"] == "ua_msme_credit_worldbank_measurement"
    )

    assert len(credit_label["known_admissible_dataset_ids"]) >= 3
    assert len(credit_label["negative_control_dataset_ids"]) >= 3


def test_acquisition_planner_reuses_data_need_spec_for_required_data() -> None:
    plan = AcquisitionPlanner().plan_from_required_data(
        RequiredDataSpec(
            missing_distributions=("local_tourism_site_traffic",),
            suggested_experiment="site-count intercept survey",
        ),
        workspace_id="ws-tourism",
    )

    assert isinstance(plan.data_need_spec, DataNeedSpec)
    assert plan.terminal_state["kind"] == "acquisition_required"
    assert plan.costed_plan["missing_distribution"] == "local_tourism_site_traffic"
    assert plan.voi_audit.selected_terminal == "acquisition_required"


def test_acquisition_voi_and_cost_move_by_gap_and_zero_voi_is_not_selected() -> None:
    tourism = AcquisitionPlanner().plan_from_required_data(
        RequiredDataSpec(
            missing_distributions=("local_tourism_site_traffic",),
            suggested_experiment="site-count intercept survey",
            alternative_identification="mobile-footfall panel",
        ),
        workspace_id="ws-tourism",
    )
    administrative = AcquisitionPlanner().plan_from_required_data(
        RequiredDataSpec(
            missing_distributions=("administrative_tax_receipts",),
            suggested_experiment="municipal registry extract",
            alternative_identification="treasury time-series proxy",
        ),
        workspace_id="ws-tax",
    )
    zero = AcquisitionPlanner().plan_from_required_data(
        RequiredDataSpec(
            missing_distributions=("local_tourism_site_traffic",),
            suggested_experiment="site-count intercept survey",
        ),
        workspace_id="ws-zero-voi",
        voi=0.0,
    )

    assert tourism.costed_plan["estimated_cost"] != administrative.costed_plan["estimated_cost"]
    assert (
        tourism.voi_audit.candidates[0]["estimated_voi"]
        != administrative.voi_audit.candidates[0]["estimated_voi"]
    )
    assert tourism.voi_audit.authority_gain_basis["missing_distribution"] == (
        "local_tourism_site_traffic"
    )
    assert administrative.voi_audit.cost_basis["missing_distribution"] == (
        "administrative_tax_receipts"
    )
    assert zero.voi_audit.candidates[0]["estimated_voi"] == 0.0
    assert zero.voi_audit.selected_action_ref is None
    assert zero.voi_audit.selected_action == {}


def test_groundable_estimate_consumes_measurement_rows_not_synthetic_stub(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    contract = WorkspaceLoop(artifact_store=store).run_fixture(
        "ua_msme_credit_worldbank_measurement"
    )
    estimate = next(
        envelope
        for envelope in contract.artifact_envelopes
        if envelope.ref.artifact_type == "Estimate"
    )
    payload = json.loads(store.get_bytes(estimate.payload_ref))

    assert payload["evidence_kind"] == "measurement"
    assert payload["measurement_rows"]
    assert payload["measurement_rows"][0]["value"] is not None
    assert payload["measurement_root_ref"] in {
        root.uri
        for envelope in contract.artifact_envelopes
        for root in envelope.producer_roots
    }
    assert "synthetic" not in json.dumps(payload).lower()


def test_estimate_adapter_conformance_fails_with_zero_foundry_candidates() -> None:
    with patch.object(workspace_loop, "_foundry_registry_estimate_candidates", return_value=[]):
        registry = build_workspace_operation_registry()

    evidence = registry.get("slice0.estimate.measurement_summary").discovery_evidence
    assert evidence["adapter_conformance"]["passed"] is False
    assert "no_foundry_estimate_candidate" in evidence["adapter_conformance"]["failures"]


def test_acquisition_planner_delegates_to_canonical_requirement_gap_planner() -> None:
    from polisyos.runtime.quality import acquisition_planner as canonical_acquisition

    original = canonical_acquisition.plan_requirement_gap_acquisition
    with patch.object(
        canonical_acquisition,
        "plan_requirement_gap_acquisition",
        wraps=original,
    ) as planner:
        plan = AcquisitionPlanner().plan_from_required_data(
            RequiredDataSpec(
                missing_distributions=("local_tourism_site_traffic",),
                suggested_experiment="site-count intercept survey",
            ),
            workspace_id="ws-tourism",
        )

    planner.assert_called_once()
    assert plan.costed_plan["canonical_planner_report"]["status"] in {"pass", "warn", "blocked"}


def test_gy_acquisition_adapter_is_owned_by_canonical_acquisition_module() -> None:
    source = Path(workspace_loop.__file__).read_text(encoding="utf-8")

    assert "class AcquisitionPlanner" not in source
    assert AcquisitionPlanner.__module__ == "polisyos.runtime.quality.acquisition_planner"


def test_formal_gate_is_owned_by_adapter_contracts_module() -> None:
    source = Path(workspace_loop.__file__).read_text(encoding="utf-8")

    assert "class FormalGate" not in source
    assert FormalGate.__module__ == "polisyos.runtime.quality.adapter_contracts"


def test_admission_gates_are_owned_by_adapter_contracts_module() -> None:
    source = Path(workspace_loop.__file__).read_text(encoding="utf-8")

    assert "class ConnectorAdmissionGate" not in source
    assert "class DataRequirementAdmissionGate" not in source
    assert ConnectorAdmissionGate.__module__ == "polisyos.runtime.quality.adapter_contracts"
    assert DataRequirementAdmissionGate.__module__ == "polisyos.runtime.quality.adapter_contracts"


def test_semantic_adequacy_gate_is_owned_by_semantic_binding_module() -> None:
    source = Path(workspace_loop.__file__).read_text(encoding="utf-8")

    assert "class SemanticAdequacyGate" not in source
    assert "class GySemanticBenchmark" not in source
    assert "class SemanticBenchmarkRun" not in source
    assert SemanticAdequacyGate.__module__ == "polisyos.runtime.quality.semantic_binding"


def test_measurement_root_producer_is_owned_by_data_forge_binding_module() -> None:
    source = Path(workspace_loop.__file__).read_text(encoding="utf-8")

    assert "class MeasurementRootProducer" not in source
    assert MeasurementRootProducer.__module__ == "polisyos.runtime.quality.data_forge_binding"
