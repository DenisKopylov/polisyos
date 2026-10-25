from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import TYPE_CHECKING

import pytest

from polisyos.ir.analytics import dependent_sensitivity, distributional, sensitivity

if TYPE_CHECKING:
    from pathlib import Path

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.dependent_sensitivity import (
    DependentSensitivityIndex,
    DependentSensitivityResult,
    load_dependent_sensitivity_result,
    persist_dependent_sensitivity_result,
)
from polisyos.ir.analytics.distributional import (
    CohortDimension,
    CohortImpact,
    DimensionBreakdown,
    DiscreteDistributionSummary,
    DistributionalReport,
    DistributionBin,
    ImpactDirection,
    load_discrete_distribution_summary,
    load_distributional_report,
    persist_discrete_distribution_summary,
    persist_distributional_report,
)
from polisyos.ir.analytics.sensitivity import (
    SensitivityResult,
    load_sensitivity_result,
    persist_sensitivity_result,
)
from polisyos.ir.analytics.uncertainty import (
    IntervalSemantics,
    PersistedUncertaintyAdmission,
    UncertaintyEnvelope,
    UncertaintySource,
    load_simulation_result_uncertainty_admission,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from polisyos.ir.artifacts import get_json_artifact, put_json_artifact
from polisyos.ir.artifacts.io import _get_owned_json_artifact_with_bytes
from polisyos.ir.migrations import base as migrations_base
from polisyos.ir.model_layer.canon import CanonSpec


def _distribution_summary() -> DiscreteDistributionSummary:
    return DiscreteDistributionSummary(
        outcome_name="unseen-resource",
        sample_size=10,
        total_weight=10.0,
        weighting_mode="uniform",
        mean_value=2.0,
        min_value=1.0,
        max_value=3.0,
        bins=[
            DistributionBin(
                index=0,
                lower_edge=0.0,
                upper_edge=2.0,
                midpoint=1.0,
                probability=0.4,
                sample_count=4,
            ),
            DistributionBin(
                index=1,
                lower_edge=2.0,
                upper_edge=4.0,
                midpoint=3.0,
                probability=0.6,
                sample_count=6,
            ),
        ],
    )


def _report() -> DistributionalReport:
    return DistributionalReport(
        breakdowns=[
            DimensionBreakdown(
                dimension=CohortDimension.CUSTOM,
                dimension_label="unseen policy cohort slice",
                cohorts=[
                    CohortImpact(
                        cohort_id="a",
                        cohort_label="A",
                        population_share=0.5,
                        metric_deltas={"benefit": 1.0},
                        impact_direction=ImpactDirection.POSITIVE,
                    ),
                    CohortImpact(
                        cohort_id="b",
                        cohort_label="B",
                        population_share=0.5,
                        metric_deltas={"benefit": -1.0},
                        impact_direction=ImpactDirection.NEGATIVE,
                    ),
                ],
                primary_metric="benefit",
            )
        ],
        methodology="unseen-resource-route",
    )


def _envelope() -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=0.4,
        confidence_interval=(0.2, 0.6),
        source=UncertaintySource.MANUAL,
        confidence_level=None,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
    )


def test_four_analytics_families_use_real_owner_cas_producer_and_consumer(tmp_path: Path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "families"))
    cases = (
        (
            persist_discrete_distribution_summary,
            load_discrete_distribution_summary,
            _distribution_summary(),
        ),
        (
            persist_sensitivity_result,
            load_sensitivity_result,
            SensitivityResult(e_value=1.5, interpretation="candidate"),
        ),
        (
            persist_dependent_sensitivity_result,
            load_dependent_sensitivity_result,
            DependentSensitivityResult(
                output_name="benefit",
                variance={"total": 1.0},
                indices=[DependentSensitivityIndex(input="uptake")],
            ),
        ),
        (persist_uncertainty_envelope, load_uncertainty_envelope, _envelope()),
    )
    for write, read, value in cases:
        ref = write(store, value)
        assert ref.manifest_profile_sha256 is not None
        assert store.get_manifest(ref).artifact_schema.version
        assert read(store, ref) == value


def test_unseen_distributional_report_uses_existing_family_route(tmp_path: Path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "unseen-resource"))
    value = _report()
    ref = persist_distributional_report(store, value)
    assert load_distributional_report(store, ref) == value


def test_registered_nondefault_schema_reuses_current_wire_law_through_family_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = {
        artifact: dict(versions) for artifact, versions in migrations_base._SCHEMA_REGISTRY.items()
    }
    monkeypatch.setattr(migrations_base, "_SCHEMA_REGISTRY", registry)
    from polisyos.ir.analytics import distributional

    owner = distributional._DISTRIBUTIONAL_OWNERS[distributional.DistributionalReport]
    wire_policy_ref, wire_policy_revision = owner.accepted_wire_policies[0]
    migrations_base.register_schema_version(
        owner.registry_key,
        "1.2",
        compatibility=migrations_base.CompatibilityMode.NONE,
        notes=("Test-only registered nondefault tuple reusing current wire law.",),
    )
    migrations_base.register_ir_representation(
        registry_key=owner.registry_key,
        owner_ref=owner.contract_id,
        dto_abi=owner.dto_fqn,
        wire_policy_ref=wire_policy_ref,
        wire_policy_revision=wire_policy_revision,
        schema_name=owner.registry_key,
        schema_version="1.2",
        payload_version="1.0",
        profile_ref=None,
        readable=True,
        writable=True,
        current=False,
        default_write=False,
    )

    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "registered-1-2"))
    value = _report()
    ref = persist_distributional_report(store, value, schema_version="1.2")
    assert store.get_manifest(ref).artifact_schema.version == "1.2"
    read = _get_owned_json_artifact_with_bytes(store, ref, owner=owner)
    assert read.admission.compatibility_kind is migrations_base.IRCompatibilityKind.DIRECT
    assert read.admission.source_registration.schema_version == "1.2"
    assert read.admission.current_registration.schema_version == "1.0"
    assert read.admission.source_registration.payload_version == "1.0"
    assert read.value == value
    assert load_distributional_report(store, ref) == value


def test_unknown_distributional_history_remains_opaque(tmp_path: Path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "unknown-history"))
    payload = _report().model_dump(mode="json")
    unknown = put_json_artifact(
        store,
        payload,
        kind="ir.distributional_report",
        schema_name="ir.distributional_report",
        schema_version="9.9",
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    from polisyos.ir.registry.refs import DistributionalReportRef

    ref = DistributionalReportRef.model_validate(unknown)
    assert get_json_artifact(store, ref) == payload
    with pytest.raises(ValueError, match="ir_owned_artifact_representation_unregistered"):
        load_distributional_report(store, ref)


def test_registered_manifest_with_mismatched_payload_version_refuses_typed_projection(
    tmp_path: Path,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "payload-version-mismatch"))
    payload = _report().model_dump(mode="json")
    payload["schema_version"] = "9.9"
    forged = put_json_artifact(
        store,
        payload,
        kind="ir.distributional_report",
        schema_name="ir.distributional_report",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    from polisyos.ir.registry.refs import DistributionalReportRef

    ref = DistributionalReportRef.model_validate(forged)
    assert get_json_artifact(store, ref) == payload
    with pytest.raises(ValueError, match="ir_owned_artifact_representation_unreadable"):
        load_distributional_report(store, ref)


def test_registration_removal_refuses_before_payload_while_dto_markers_remain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "removed-owner"))
    ref = persist_distributional_report(store, _report())
    from polisyos.ir.analytics import distributional

    owner = distributional._DISTRIBUTIONAL_OWNERS[distributional.DistributionalReport]
    registry = {
        artifact: dict(versions) for artifact, versions in migrations_base._SCHEMA_REGISTRY.items()
    }
    rule = registry[owner.registry_key]["1.0"]
    registry[owner.registry_key]["1.0"] = replace(
        rule,
        representations=tuple(
            row for row in rule.representations if row.owner_ref != owner.contract_id
        ),
    )
    monkeypatch.setattr(migrations_base, "_SCHEMA_REGISTRY", registry)

    def refuse_payload_read(*_args: object, **_kwargs: object) -> bytes:
        pytest.fail("removed owner row must refuse before payload bytes are read")

    monkeypatch.setattr(FileSystemCAS, "get_bytes", refuse_payload_read)
    with pytest.raises(ValueError, match="ir_owned_artifact_representation_unregistered"):
        load_distributional_report(store, ref)


def test_unknown_distributional_write_override_refuses_before_cas_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "unknown-write"))

    def refuse_write(*_args: object, **_kwargs: object) -> object:
        pytest.fail("unregistered schema override reached the CAS writer")

    monkeypatch.setattr(FileSystemCAS, "put_json", refuse_write)
    with pytest.raises(ValueError, match="ir_owned_artifact_write_override_unregistered"):
        persist_distributional_report(store, _report(), schema_version="9.9")


def test_existing_analytics_public_star_imports_are_preserved() -> None:
    expected_exports = {
        "polisyos.ir.analytics.distributional": (
            "CausalAssumptionCard",
            "CohortDimension",
            "CohortImpact",
            "CouplingDiagnostics",
            "DimensionBreakdown",
            "DiscreteDistributionSummary",
            "DistributionBin",
            "DistributionalBoundUniformity",
            "DistributionalBoundsBundle",
            "DistributionalBoundsMethodSummary",
            "DistributionalCouplingStatus",
            "DistributionalDualBoundWitness",
            "DistributionalDualCertificate",
            "DistributionalEffectBundle",
            "DistributionalFunctional",
            "DistributionalFunctionalParameters",
            "DistributionalJustification",
            "DistributionalProofArtifact",
            "DistributionalProofTarget",
            "DistributionalReport",
            "DistributionalSupportDomain",
            "FunctionalBounds",
            "GridAxis",
            "ImpactDirection",
            "MetricUnit",
            "OTCouplingSummary",
            "OrdinalPovertyEstimate",
            "OrdinalPovertyReport",
            "QuantileShiftEntry",
            "QuantileShiftSummary",
            "SubgroupDistributionComparison",
            "TailRiskDeltaEntry",
            "TailRiskDeltaSummary",
            "WinnersLosersEntry",
            "WinnersLosersTable",
            "attach_distributional_dual_certificate_ref",
            "load_causal_assumption_card",
            "load_discrete_distribution_summary",
            "load_distributional_bounds_bundle",
            "load_distributional_dual_certificate",
            "load_distributional_effect_bundle",
            "load_distributional_proof_artifact",
            "load_distributional_report",
            "load_ordinal_poverty_report",
            "load_ot_coupling_summary",
            "load_quantile_shift_summary",
            "load_subgroup_distribution_comparison",
            "load_tail_risk_delta_summary",
            "persist_causal_assumption_card",
            "persist_discrete_distribution_summary",
            "persist_distributional_bounds_bundle",
            "persist_distributional_dual_certificate",
            "persist_distributional_effect_bundle",
            "persist_distributional_proof_artifact",
            "persist_distributional_report",
            "persist_ordinal_poverty_report",
            "persist_ot_coupling_summary",
            "persist_quantile_shift_summary",
            "persist_subgroup_distribution_comparison",
            "persist_tail_risk_delta_summary",
        ),
        "polisyos.ir.analytics.sensitivity": (
            "BenchmarkResult",
            "EValueResult",
            "SensitivityAnalysisBundle",
            "SensitivityAnalysisIndex",
            "SensitivityResult",
            "load_sensitivity_analysis_bundle",
            "load_sensitivity_result",
            "persist_sensitivity_analysis_bundle",
            "persist_sensitivity_result",
            "sensitivity_analysis_bundle_from_result",
        ),
        "polisyos.ir.analytics.dependent_sensitivity": (
            "ConditionalSamplerSpec",
            "ContributionMode",
            "CopulaFamily",
            "CopulaFitSpec",
            "CopulaParameterSpec",
            "CopulaSpec",
            "CopulaSupportPolicy",
            "DependentEstimatorBudgetSpec",
            "DependentEstimatorComputationalOptions",
            "DependentEstimatorFamily",
            "DependentEstimatorSpec",
            "DependentEstimatorUncertaintySpec",
            "DependentSensitivityAnalysisBundle",
            "DependentSensitivityAnalysisBundleRef",
            "DependentSensitivityIndex",
            "DependentSensitivityModel",
            "DependentSensitivityResult",
            "DependentSensitivityResultRef",
            "DiagnosticSpec",
            "EdgeContribution",
            "Estimate",
            "IdentifiabilityAssumptionSpec",
            "InputMarginalSpec",
            "InputVariableSpec",
            "JointInputDistributionSpec",
            "OutputSpec",
            "PairCopulaSpec",
            "ReferenceCopulaSpec",
            "ReproducibilitySpec",
            "StructuralClaimLevel",
            "StructuralGraphEdgeSpec",
            "StructuralGraphSpec",
            "load_dependent_sensitivity_bundle",
            "load_dependent_sensitivity_result",
            "persist_dependent_sensitivity_bundle",
            "persist_dependent_sensitivity_result",
        ),
    }
    modules = {
        distributional.__name__: distributional,
        sensitivity.__name__: sensitivity,
        dependent_sensitivity.__name__: dependent_sensitivity,
    }
    assert set(modules) == set(expected_exports)
    for module_name, module in modules.items():
        expected = expected_exports[module_name]
        assert tuple(module.__all__) == expected
        assert all(hasattr(module, name) for name in expected)
        assert not {"ArtifactOwnerDeclaration", "register_ir_representation"} & set(module.__all__)


def test_uncertainty_resolver_returns_immutable_typed_early_refusal() -> None:
    class NoReadStore:
        def get_manifest(self, *_args: object, **_kwargs: object) -> object:
            pytest.fail("kind refusal must precede manifest access")

    selector = {
        "artifact_id": "sha256:" + "0" * 64,
        "kind": "not-a-simulation-result",
        "media_type": "application/json",
    }
    admission = load_simulation_result_uncertainty_admission(NoReadStore(), selector, "metric")

    assert type(admission) is PersistedUncertaintyAdmission
    assert admission.envelope is None
    assert admission.limitation_codes == ("simulation_result_kind_mismatch",)
    assert not admission.admitted
    with pytest.raises(FrozenInstanceError):
        admission.limitation_codes = ()
