"""Selected source bases enter registered method profiles before acquisition."""

from __future__ import annotations

from typing import Any

import pytest

from polisyos.core.artifacts import (
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.compiler.report import CompileReport
from polisyos.core.contracts.model_input_requirements import (
    load_model_input_obligation_set,
    load_model_input_port_declaration,
)
from polisyos.core.contracts.semantic_composition_binding import (
    RegisteredDerivationRoleBasis,
    RegisteredSemanticBasis,
    load_registered_derived_input_profile,
)
from polisyos.core.contracts.variable_binding import (
    VariableSemanticDefinition,
    VariableSemanticDefinitionRef,
    load_variable_representation,
)
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from tests._helpers import registered_derived_method_input as fixture
from tests._helpers.selected_method_input import prepare_selected_method_input_case
from tests.unit.core.contracts.test_semantic_derived_binding import (
    _put_contract,
    _representation,
    _selected,
)


def _definition_ref(store: Any, *, stable_id: str, meaning: str) -> VariableSemanticDefinitionRef:
    evidence_bytes = (
        f"stable_id: {stable_id}\nmeaning: {meaning}\n"
        "scope: controlled candidate-only semantic fixture; empirical truth and authority not established."
    ).encode()
    evidence = _selected(
        store,
        store.put_bytes(
            evidence_bytes,
            PutOptions(kind="fixture.semantic_definition", media_type="text/plain"),
        ),
    )
    definition = VariableSemanticDefinition(
        namespace="fixture",
        stable_id=stable_id,
        revision="1",
        meaning=meaning,
        definition_evidence_refs=(evidence,),
    )
    selected = _put_contract(
        store,
        definition,
        inputs=(input_ref_from_artifact_ref(evidence, role="definition_evidence"),),
    )
    return VariableSemanticDefinitionRef.model_validate(selected.model_dump())


def _selected_fiscal_input_case(tmp_path, *, definition_refs=None):
    store = FileSystemCAS(tmp_path / "cas")
    target_ref = _definition_ref(
        store,
        stable_id="fixture.government_fiscal_flow",
        meaning=(
            "Annual total government fiscal flow in current USD for one model period. "
            "This is a candidate model input, not cash-on-hand or an empirical fiscal claim."
        ),
    )
    selected_refs = {"period_flow": target_ref} if definition_refs is None else definition_refs
    case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        store=store,
        model_input_definition_refs=selected_refs,
    )
    return case, metadata, store, target_ref


def _source_bases(case: Any, metadata: dict[str, Any]):
    port = metadata["port"]
    target = load_variable_representation(case.store, port.representation_ref)
    ratio_definition = _definition_ref(
        case.store,
        stable_id="fixture.government_fiscal_share_of_gdp",
        meaning=(
            "Annual government fiscal flow as a signed share of annual nominal GDP; "
            "numerator is the selected government flow and denominator is nominal GDP. "
            "Controlled candidate-only semantics; empirical truth is not established."
        ),
    )
    gdp_definition = _definition_ref(
        case.store,
        stable_id="fixture.nominal_gdp_current_usd",
        meaning=(
            "Annual nominal gross domestic product for the economy in current USD. "
            "Controlled candidate-only semantics; empirical truth is not established."
        ),
    )
    ratio_representation, _ = _representation(
        case.store,
        ratio_definition,
        population=port.scope.population_ref,
        money=target.money_unit,
        numerator_ref=port.semantic_definition_ref,
        denominator_ref=gdp_definition,
    )
    gdp_representation, _ = _representation(
        case.store,
        gdp_definition,
        population="population:economy",
        money=target.money_unit,
    )
    return (
        RegisteredDerivationRoleBasis(
            role="rate_input",
            basis=RegisteredSemanticBasis(
                semantic_definition_ref=ratio_definition,
                representation_ref=ratio_representation,
                binding_profile_ref=port.binding_profile_ref,
            ),
        ),
        RegisteredDerivationRoleBasis(
            role="scale_input",
            basis=RegisteredSemanticBasis(
                semantic_definition_ref=gdp_definition,
                representation_ref=gdp_representation,
                binding_profile_ref=port.binding_profile_ref,
            ),
        ),
    )


def test_explicit_source_bases_are_selected_before_profile_persistence(tmp_path, monkeypatch):
    case, metadata, store, target_ref = _selected_fiscal_input_case(tmp_path)
    try:
        assert case.model_input_port_declaration_ref is not None
        declaration = load_model_input_port_declaration(
            store, case.model_input_port_declaration_ref
        )
        (declared_port,) = declaration.ports
        assert artifact_ref_identity_key(declared_port.semantic_definition_ref) == (
            artifact_ref_identity_key(target_ref)
        )
        assert artifact_ref_identity_key(metadata["port"].semantic_definition_ref) == (
            artifact_ref_identity_key(target_ref)
        )
        target_definition = validate_core_model_json_artifact(
            VariableSemanticDefinition, store, target_ref
        )
        assert "Annual total government fiscal flow" in target_definition.meaning
        trinity_manifest = store.get_manifest(case.trinity_ref)
        declaration_input = input_ref_from_artifact_ref(
            case.model_input_port_declaration_ref,
            role="model_input_port_declaration",
        )
        assert declaration_input in trinity_manifest.inputs
        compile_report = validate_core_model_json_artifact(
            CompileReport, store, case.compile_report_ref
        )
        assert compile_report.ok is True
        assert compile_report.policy_ref is not None
        assert compile_report.program_graph_ref is not None
        assert compile_report.exec_plan_ref is not None
        assert artifact_ref_identity_key(compile_report.policy_ref) == artifact_ref_identity_key(
            case.trinity_ref
        )
        assert artifact_ref_identity_key(compile_report.program_graph_ref) == (
            artifact_ref_identity_key(case.program_graph_ref)
        )
        assert artifact_ref_identity_key(compile_report.exec_plan_ref) == (
            artifact_ref_identity_key(case.exec_plan_ref)
        )
        source_bases = _source_bases(case, metadata)

        def unexpected(*_args, **_kwargs):
            raise AssertionError("explicit_source_basis_fell_back_to_generic_definitions")

        monkeypatch.setattr(fixture, "_definition", unexpected)
        monkeypatch.setattr(fixture, "_representation", unexpected)
        setup = fixture.prepare_registered_method_input_profile(
            case, metadata, source_bases=source_bases
        )
        selected_profile = load_registered_derived_input_profile(store, setup.profile_ref)
        assert artifact_ref_identity_key(selected_profile.output.semantic_definition_ref) == (
            artifact_ref_identity_key(target_ref)
        )
        ratio_representation = load_variable_representation(
            store, source_bases[0].basis.representation_ref
        )
        assert artifact_ref_identity_key(ratio_representation.numerator_ref) == (
            artifact_ref_identity_key(target_ref)
        )

        inputs = {item.role: item.basis for item in setup.profile.inputs}
        assert tuple(item.role for item in setup.profile.inputs) == ("rate_input", "scale_input")
        assert inputs["rate_input"] == source_bases[0].basis
        assert inputs["scale_input"] == source_bases[1].basis
        assert setup.source_specs[0]["source_semantic_definition_ref"] == (
            source_bases[0].basis.semantic_definition_ref
        )
        assert setup.source_specs[0]["source_representation_ref"] == (
            source_bases[0].basis.representation_ref
        )
        assert setup.source_specs[0]["canonical_unit"] == "ratio"
        assert setup.source_specs[0]["source_measure_scope"]["population"] == (
            metadata["port"].scope.population_ref
        )
        assert setup.source_specs[1]["canonical_unit"] == "usd"
        assert setup.source_specs[1]["source_measure_scope"]["population"] == ("population:economy")
        assert setup.source_specs[1]["source_measure_scope"]["temporal_granularity"] == ("annual")
    finally:
        case.close()


def test_request_reuses_the_explicit_source_bases_before_native_rows(tmp_path, monkeypatch):
    case, metadata, store, _target_ref = _selected_fiscal_input_case(tmp_path)
    captured: list[dict[str, Any]] = []

    def capture(_path, **kwargs):
        captured.append(kwargs)
        raise RuntimeError("captured_before_native_source_rows")

    try:
        source_bases = _source_bases(case, metadata)
        preflight = fixture.prepare_registered_method_input_preflight(case)
        selected_set, _ = load_model_input_obligation_set(case.store, preflight.obligation_set_ref)
        (obligation_ref,) = selected_set.obligation_refs
        monkeypatch.setattr(
            fixture,
            "_definition",
            lambda *_args, **_kwargs: pytest.fail("default source definitions used"),
        )
        monkeypatch.setattr(
            fixture,
            "_representation",
            lambda *_args, **_kwargs: pytest.fail("default source representations used"),
        )
        monkeypatch.setattr(fixture, "make_native_multivariable_active_projections", capture)

        with pytest.raises(RuntimeError, match="captured_before_native_source_rows"):
            fixture.prepare_registered_method_input_request(
                case,
                metadata,
                preflight=preflight,
                model_input_obligation_ref=obligation_ref,
                source_bases=source_bases,
            )

        (arguments,) = captured
        specs = arguments["variable_specs"]
        assert tuple(spec["source_semantic_definition_ref"] for spec in specs) == tuple(
            item.basis.semantic_definition_ref for item in source_bases
        )
        assert tuple(spec["source_representation_ref"] for spec in specs) == tuple(
            item.basis.representation_ref for item in source_bases
        )
    finally:
        case.close()


def test_explicit_ratio_must_name_the_selected_denominator(tmp_path):
    case, metadata, store, _target_ref = _selected_fiscal_input_case(tmp_path)
    try:
        source_bases = _source_bases(case, metadata)
        wrong_denominator = _definition_ref(
            case.store,
            stable_id="fixture.other_denominator",
            meaning="A distinct annual economy flow, not nominal GDP.",
        )
        target = load_variable_representation(case.store, metadata["port"].representation_ref)
        wrong_ratio_representation, _ = _representation(
            case.store,
            source_bases[0].basis.semantic_definition_ref,
            population=metadata["port"].scope.population_ref,
            money=target.money_unit,
            numerator_ref=metadata["port"].semantic_definition_ref,
            denominator_ref=wrong_denominator,
        )
        malformed = (
            source_bases[0].model_copy(
                update={
                    "basis": source_bases[0].basis.model_copy(
                        update={"representation_ref": wrong_ratio_representation}
                    )
                }
            ),
            source_bases[1],
        )
        with pytest.raises(
            ValueError, match="registered_method_fixture_source_basis_relation_mismatch"
        ):
            fixture.prepare_registered_method_input_profile(case, metadata, source_bases=malformed)
    finally:
        case.close()


def test_selected_method_requires_definition_mapping_for_each_input_slot(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    target_ref = _definition_ref(
        store,
        stable_id="fixture.government_fiscal_flow",
        meaning="Annual total government fiscal flow in current USD; candidate-only fixture.",
    )
    for missing_or_wrong in ({}, {"different_input": target_ref}):
        with pytest.raises(
            ValueError, match="selected_method_fixture_definition_slot_scope_mismatch"
        ):
            prepare_selected_method_input_case(
                tmp_path,
                method_class=PeriodFlowToStock,
                store=store,
                model_input_definition_refs=missing_or_wrong,
            )
