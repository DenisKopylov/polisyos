"""Pure registration precedes real source acquisition without inventing values."""

from __future__ import annotations

import hashlib

import pytest

from polisyos.core.artifacts import artifact_ref_identity_key, load_core_json_artifact
from polisyos.core.contracts import load_model_input_obligation_set, load_variable_representation
from polisyos.core.registry import load_registry_bundle_content
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from tests._helpers import registered_derived_method_input as fixture
from tests._helpers.selected_method_input import prepare_selected_method_input_case
from tests._helpers.temporal_selected_method_input import constant_price_two_year_method_spec


def test_default_profile_wire_is_independent_of_unavailable_source_inputs(tmp_path, monkeypatch):
    first, metadata = prepare_selected_method_input_case(
        tmp_path / "omitted", method_class=PeriodFlowToStock
    )
    second, second_metadata = prepare_selected_method_input_case(
        tmp_path / "explicit-none", method_class=PeriodFlowToStock, money_unit=None
    )
    calls = []

    def unexpected(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("pure_profile_attempted_source_or_preflight")

    monkeypatch.setattr(fixture, "make_native_multivariable_active_projections", unexpected)
    monkeypatch.setattr(fixture, "_preflight", unexpected)
    try:
        setup = fixture.prepare_registered_method_input_profile(first, metadata)
        other = fixture.prepare_registered_method_input_profile(second, second_metadata)
        assert not calls
        assert (
            load_input_bindings(first.store, first.input_bindings_ref).selected_method_inputs
            is None
        )
        assert metadata["port"].physical_encoding.shape == ()
        assert metadata["money"].model_dump() == {
            "kind": "money",
            "currency": "USD",
            "nominal_year": 2024,
            "price_base": "current",
        }
        assert artifact_ref_identity_key(setup.profile_ref) == artifact_ref_identity_key(
            other.profile_ref
        )
        assert first.store.get_bytes(setup.profile_ref) == second.store.get_bytes(other.profile_ref)
        wire = load_core_json_artifact(first.store, setup.profile_ref)
        assert set(wire) == {
            "schema_version",
            "relation_profile",
            "registry_ref",
            "family_id",
            "method_version",
            "ratio_role",
            "denominator_role",
            "inputs",
            "output",
            "output_projection",
            "authority_purpose",
        }
        assert wire["schema_version"] == "2.0" and wire["output_projection"] == "scalar"
        assert wire["family_id"] == "registered.flow_from_share"
        assert wire["ratio_role"] == "rate_input" and wire["denominator_role"] == "scale_input"
        assert setup.role_aliases == {
            "rate_input": "provider.share_series",
            "scale_input": "provider.total_series",
        }
    finally:
        first.close()
        second.close()


def test_profile_requires_an_actual_selected_model_port(tmp_path, monkeypatch):
    case, metadata = prepare_selected_method_input_case(tmp_path, method_class=PeriodFlowToStock)

    def unexpected(*args, **kwargs):
        raise AssertionError("missing_profile_input_attempted_activation")

    monkeypatch.setattr(fixture, "make_native_multivariable_active_projections", unexpected)
    try:
        with pytest.raises(ValueError, match="registered_method_fixture_model_port_required"):
            fixture.prepare_registered_method_input_profile(case, {})
        with pytest.raises(ValueError, match="registered_method_fixture_model_port_required"):
            fixture.prepare_registered_method_input_profile(
                case, metadata, port=metadata["port"].model_copy(update={"port_id": "unselected"})
            )
    finally:
        case.close()


def test_default_source_year_keeps_the_legacy_fixture_identity(tmp_path, monkeypatch):
    case, metadata = prepare_selected_method_input_case(tmp_path, method_class=PeriodFlowToStock)
    captured = []

    def capture(path, **kwargs):
        captured.append((path, kwargs))
        raise RuntimeError("captured_legacy_native_boundary")

    monkeypatch.setattr(fixture, "make_native_multivariable_active_projections", capture)
    try:
        preflight = fixture.prepare_registered_method_input_preflight(case)
        selected_set, _ = load_model_input_obligation_set(case.store, preflight.obligation_set_ref)
        (obligation_ref,) = selected_set.obligation_refs
        with pytest.raises(RuntimeError, match="captured_legacy_native_boundary"):
            fixture.prepare_registered_method_input_request(
                case,
                metadata,
                preflight=preflight,
                model_input_obligation_ref=obligation_ref,
            )
        ((path, arguments),) = captured
        assert path.name == "registered-sources-c18a40d8247dda17"
        assert arguments["source_rows"][0]["year"] == 2024
    finally:
        case.close()


def test_fixed_price_basis_and_source_year_are_explicit_before_activation(tmp_path, monkeypatch):
    spec = constant_price_two_year_method_spec()
    case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        money_unit=spec.money_unit,
        scope=spec.scope,
        time_semantics=spec.time_semantics,
        period_step_profile=True,
    )
    captured = []

    def capture(path, **kwargs):
        captured.append((path, kwargs))
        raise RuntimeError("captured_native_boundary")

    monkeypatch.setattr(fixture, "make_native_multivariable_active_projections", capture)
    try:
        setup = fixture.prepare_registered_method_input_profile(case, metadata)
        registry = load_registry_bundle_content(case.store, case.registry_bundle_ref)
        assert registry.units_registry.units["usd"] == spec.money_unit
        assert metadata["money"] == spec.money_unit
        for source in setup.source_specs:
            representation = load_variable_representation(
                case.store, source["source_representation_ref"]
            )
            assert representation.money_unit == spec.money_unit
        preflight = fixture.prepare_registered_method_input_preflight(case, steps=(0, 1))
        selected_set, _ = load_model_input_obligation_set(case.store, preflight.obligation_set_ref)
        (obligation_ref,) = selected_set.obligation_refs
        for year in (2020, 2021):
            with pytest.raises(RuntimeError, match="captured_native_boundary"):
                fixture.prepare_registered_method_input_request(
                    case,
                    metadata,
                    preflight=preflight,
                    model_input_obligation_ref=obligation_ref,
                    binding_id="same-value-source",
                    source_year=year,
                )
        assert [kwargs["source_rows"][0]["year"] for _, kwargs in captured] == [2020, 2021]
        assert captured[0][0] != captured[1][0]
        legacy = (
            "registered-sources-"
            + hashlib.sha256(b"same-value-source:-0.03:200000000000").hexdigest()[:16]
        )
        assert all(path.name != legacy for path, _ in captured)
    finally:
        case.close()
