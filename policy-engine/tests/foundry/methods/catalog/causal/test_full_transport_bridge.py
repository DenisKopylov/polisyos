from __future__ import annotations

from polisyos.foundry.methods.catalog.causal import full_transport_bridge as bridge


def test_normalize_symbolic_backend_mode_defaults_to_auto() -> None:
    assert bridge.normalize_symbolic_backend_mode(None) == "auto"
    assert bridge.normalize_symbolic_backend_mode("") == "auto"
    assert bridge.normalize_symbolic_backend_mode("unknown") == "auto"


def test_resolve_symbolic_backend_prefers_first_available(monkeypatch) -> None:
    def _fake_probe(name: str):
        if name == "y0":
            return False, "y0_unavailable"
        if name == "r":
            return True, None
        return False, "unsupported"

    monkeypatch.setattr(bridge, "probe_backend_availability", _fake_probe)
    resolved = bridge.resolve_symbolic_backend("full_auto")
    assert resolved.selected == "r"
    assert resolved.order == ("y0", "r")
    assert resolved.unavailable_reasons == ("y0_unavailable",)


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
