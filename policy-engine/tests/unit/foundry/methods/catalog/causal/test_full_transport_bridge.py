from __future__ import annotations

import pytest

from polisyos.foundry.methods.catalog.causal import full_transport_bridge as bridge


def test_normalize_symbolic_backend_mode_defaults_to_auto() -> None:
    assert bridge.normalize_symbolic_backend_mode(None) == "auto"
    assert bridge.normalize_symbolic_backend_mode("") == "auto"
    assert bridge.normalize_symbolic_backend_mode("unknown") == "auto"


def test_resolve_symbolic_backend_prefers_first_available(monkeypatch) -> None:
    def _fake_probe(name: str):
        if name == "y0":
            return True, None
        return False, "r_causaleffect_execution_adapter_not_implemented"

    monkeypatch.setattr(bridge, "probe_backend_availability", _fake_probe)
    resolved = bridge.resolve_symbolic_backend("full_auto")
    assert resolved.selected == "y0"
    assert resolved.order == ("y0", "r")
    assert resolved.unavailable_reasons == ()


def test_resolve_symbolic_backend_reports_no_available_backend(monkeypatch) -> None:
    monkeypatch.setattr(
        bridge,
        "probe_backend_availability",
        lambda name: (False, f"{name}_unavailable"),
    )
    resolved = bridge.resolve_symbolic_backend("auto")
    assert resolved.selected is None
    assert resolved.unavailable_reasons == ("y0_unavailable", "r_unavailable")


def test_normalize_transport_formula_extracts_tokens() -> None:
    normalized = bridge.normalize_transport_formula(
        "P*(Y|do(X))=∑_{M, Z} P*(M|X) * P(Y|M,X) * P(Z)"
    )
    assert normalized.formula_str == "P*(Y|do(X)) = Σ_{M,Z} P*(M|X) * P(Y|M,X) * P(Z)"
    assert normalized.stratification_variables == ("M", "Z")
    assert "P*(M|X)" in normalized.target_quantities


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (bridge.Y0_SURROGATE_DATA_PROFILE_ABSENT, "absent"),
        (None, "null"),
        ({"schema_version": "wrong", "populations": []}, "invalid"),
        (
            {
                "schema_version": "policyos.y0.surrogate-data-profile.v1",
                "populations": [
                    {"population_id": "pi1", "outcomes": ["Y"], "interventions": ["X"]}
                ],
            },
            "valid",
        ),
    ],
)
def test_y0_profile_parser_keeps_missing_null_malformed_and_valid_distinct(raw, expected) -> None:
    profile, state = bridge.parse_y0_surrogate_data_profile(raw)
    assert state == expected
    assert (profile is not None) is (expected == "valid")


def test_y0_profile_is_strict_and_graph_scoped() -> None:
    raw = {
        "schema_version": "policyos.y0.surrogate-data-profile.v1",
        "populations": [
            {"population_id": "pi1", "outcomes": ["Y"], "interventions": ["X"]}
        ],
    }
    profile, state = bridge.parse_y0_surrogate_data_profile(raw)
    assert state == "valid" and profile is not None
    assert bridge.profile_unknown_variables(profile, {"X", "M", "Y"}) == ()
    assert bridge.profile_unknown_variables(profile, {"X", "Y"}) == ()

    malformed = {**raw, "surprise": True}
    assert bridge.parse_y0_surrogate_data_profile(malformed) == (None, "invalid")
    malformed_list = {
        **raw,
        "populations": [
            {"population_id": "pi1", "outcomes": ["Y", 3], "interventions": ["X"]}
        ],
    }
    assert bridge.parse_y0_surrogate_data_profile(malformed_list) == (None, "invalid")


def test_y0_probe_requires_both_locked_algorithm_signatures() -> None:
    pytest.importorskip("y0")
    available, reason = bridge.probe_backend_availability("y0")
    assert available, reason
    assert bridge.probe_backend_availability("r") == (
        False,
        "r_causaleffect_execution_adapter_not_implemented",
    )


def test_capability_family_claims_do_not_follow_import_availability(monkeypatch) -> None:
    from polisyos.foundry.methods.catalog.causal import capabilities
    from polisyos.ir.analytics.causal_capabilities import (
        CausalBackendId,
        CausalIdentificationFamily,
    )

    monkeypatch.setattr(
        capabilities, "probe_backend_availability", lambda name: (name == "y0", None)
    )
    contract = capabilities.build_causal_capability_contract()

    y0 = contract.backend(CausalBackendId.Y0)
    r = contract.backend(CausalBackendId.R_CAUSALEFFECT)
    assert y0 is not None and y0.available
    assert set(y0.supported_families) == {
        CausalIdentificationFamily.DIRECT,
        CausalIdentificationFamily.TRSO,
    }
    assert contract.supports_family(CausalIdentificationFamily.TRSO)
    assert r is not None and r.supported_families == []
    for family in (
        CausalIdentificationFamily.FRONTDOOR,
        CausalIdentificationFamily.DO_CALCULUS_RULE2,
        CausalIdentificationFamily.DO_CALCULUS_RULE3,
        CausalIdentificationFamily.C_COMPONENT_FACTORIZATION,
    ):
        assert not contract.supports_family(family)
        assert contract.disabled_families[family.value] == "symbolic_family_execution_not_established"


def test_y0_profile_is_deeply_immutable_after_admission() -> None:
    raw = {
        "schema_version": "policyos.y0.surrogate-data-profile.v1",
        "populations": [
            {"population_id": "pi1", "outcomes": ["Y"], "interventions": ["X"]}
        ],
    }
    profile, state = bridge.parse_y0_surrogate_data_profile(raw)
    assert state == "valid" and profile is not None
    assert isinstance(profile.populations, tuple)
    assert isinstance(profile.populations[0].outcomes, tuple)
    with pytest.raises(AttributeError):
        profile.populations[0].outcomes.append("Z")
    with pytest.raises(AttributeError):
        profile.populations.append(profile.populations[0])
    assert bridge.parse_y0_surrogate_data_profile(raw)[0] == profile
