"""Native preparation of explicitly synthetic fixed-price temporal inputs.

The source rows are declared local test data, not WDI GDP or another provider
series relabeled with a different price basis. The real Catalog/native epoch
machinery records those test-owned bytes without establishing empirical
currentness or production authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polisyos.core.artifacts import artifact_ref_identity_key, validate_core_model_json_artifact
from polisyos.core.contracts import (
    VariableSemanticDefinition,
    load_model_input_obligation_set,
    load_variable_representation,
)
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.runtime.quality.model_input_requirements import ProgramGraphInputPreflight
from polisyos.runtime.quality.model_input_step_materialization import (
    RegisteredDerivedModelInputStepRequest,
)
from tests._helpers.program_graph_tax_subsidy_input import ProgramGraphTaxSubsidyInputCase
from tests._helpers.registered_derived_method_input import (
    prepare_registered_method_input_preflight,
    prepare_registered_method_input_request,
)
from tests._helpers.selected_method_input import prepare_selected_method_input_case
from tests._helpers.temporal_selected_method_input import (
    TemporalSelectedMethodInputSpec,
    constant_price_two_year_method_spec,
)


@dataclass(frozen=True)
class TemporalRegisteredMethodInputs:
    """One actual model/prestate and its separately selected annual native rows."""

    case: ProgramGraphTaxSubsidyInputCase
    spec: TemporalSelectedMethodInputSpec
    preflight: ProgramGraphInputPreflight
    requests: tuple[RegisteredDerivedModelInputStepRequest, ...]
    metadata_by_step: dict[int, dict[str, Any]]


def _require_synthetic_local_source_profile(
    case: ProgramGraphTaxSubsidyInputCase,
    metadata: dict[str, Any],
    spec: TemporalSelectedMethodInputSpec,
    *,
    source_year: int,
) -> None:
    """Keep fixture price coordinates attached to their actual local sources."""
    for native in metadata["native_sources"].values():
        passport = native["passport"]
        entry = passport.source_authority_entry
        basis = native["source_basis"]
        if (
            passport.source_lane != "local_lift"
            or passport.live_source_execution is not None
            or entry is None
            or entry.source_lane != "local_lift"
            or entry.source_semantic_definition_ref is None
            or entry.source_representation_ref is None
            or entry.temporal_start != str(source_year)
            or entry.temporal_end != str(source_year)
            or passport.field_binding.unit_transform != "identity"
            or passport.field_binding.raw_unit != passport.field_binding.canonical_unit
        ):
            raise ValueError("temporal_fixture_synthetic_local_source_required")
        if artifact_ref_identity_key(
            entry.source_semantic_definition_ref
        ) != artifact_ref_identity_key(basis.semantic_definition_ref) or artifact_ref_identity_key(
            entry.source_representation_ref
        ) != artifact_ref_identity_key(basis.representation_ref):
            raise ValueError("temporal_fixture_source_basis_mismatch")
        definition = validate_core_model_json_artifact(
            VariableSemanticDefinition, case.store, basis.semantic_definition_ref
        )
        representation = load_variable_representation(case.store, basis.representation_ref)
        if (
            definition.namespace != "fixture"
            or any(
                ref.kind != "fixture.semantic_definition"
                for ref in definition.definition_evidence_refs
            )
            or representation.money_unit != spec.money_unit
        ):
            raise ValueError("temporal_fixture_declared_test_price_basis_required")


def prepare_temporal_registered_method_inputs(
    tmp_path: Path,
    *,
    spec: TemporalSelectedMethodInputSpec | None = None,
    method_class: type[PeriodFlowToStock] = PeriodFlowToStock,
) -> TemporalRegisteredMethodInputs:
    """Prepare annual model inputs with source roles on a common fixed-price basis.

    Canonical shared helpers own the actual compiler, native activation and
    occurrence producers. This helper chooses literal local test rows and
    fixture-only source definitions with a common declared monetary basis;
    it does not transform real current-USD GDP into constant-price GDP or
    fabricate certificates, bindings, numerical results or provider provenance.
    """
    spec = constant_price_two_year_method_spec() if spec is None else spec
    case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=method_class,
        period_step_profile=True,
        time_semantics=spec.time_semantics,
        scope=spec.scope,
        money_unit=spec.money_unit,
    )
    try:
        preflight = prepare_registered_method_input_preflight(
            case, steps=tuple(row.step for row in spec.rows)
        )
        selected_set, _ = load_model_input_obligation_set(case.store, preflight.obligation_set_ref)
        (obligation_ref,) = selected_set.obligation_refs
        assert selected_set.required_step_scopes is not None
        scopes = {scope.step: scope for scope in selected_set.required_step_scopes}
        requests = []
        metadata_by_step = {}
        for row in spec.rows:
            request = prepare_registered_method_input_request(
                case,
                metadata,
                preflight=preflight,
                model_input_obligation_ref=obligation_ref,
                ratio_value=row.ratio,
                denominator_value=row.denominator,
                binding_id=f"selected-flow-{row.year}",
                source_year=row.year,
            )
            _require_synthetic_local_source_profile(case, metadata, spec, source_year=row.year)
            requests.append(
                RegisteredDerivedModelInputStepRequest(step_scope=scopes[row.step], request=request)
            )
            metadata_by_step[row.step] = dict(metadata)
        return TemporalRegisteredMethodInputs(
            case=case,
            spec=spec,
            preflight=preflight,
            requests=tuple(requests),
            metadata_by_step=metadata_by_step,
        )
    except BaseException:
        case.close()
        raise
